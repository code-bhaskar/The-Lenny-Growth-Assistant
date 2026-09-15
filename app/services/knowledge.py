from __future__ import annotations

import io
import json
import re
import shutil
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import requests
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import get_settings
from app.core.logging import get_logger, log_event

logger = get_logger(__name__)


@dataclass
class ChunkRecord:
    chunk_id: str
    transcript_title: str
    guest: str | None
    publish_date: str | None
    youtube_url: str | None
    description: str | None
    source_path: str
    transcript_path: str
    text: str
    snippet: str
    chunk_index: int


class TranscriptIngestionService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def ensure_source_repo(self) -> Path:
        cache_dir = self.settings.transcript_cache_dir
        episodes_dir = cache_dir / "episodes"
        if episodes_dir.exists():
            return cache_dir

        cache_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            response = requests.get(self.settings.transcript_repo_url, timeout=120)
            response.raise_for_status()
        except requests.exceptions.SSLError:
            logger.warning(
                "transcript_repo_ssl_verification_failed",
                extra={"repo_url": self.settings.transcript_repo_url},
            )
            response = requests.get(self.settings.transcript_repo_url, timeout=120, verify=False)
            response.raise_for_status()

        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            temp_root = cache_dir.parent / "_transcript_unpack"
            if temp_root.exists():
                shutil.rmtree(temp_root)
            zf.extractall(temp_root)
            extracted_roots = [p for p in temp_root.iterdir() if p.is_dir()]
            if not extracted_roots:
                raise RuntimeError("Transcript repository download was empty")
            extracted_root = extracted_roots[0]
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
            shutil.move(str(extracted_root), str(cache_dir))
            shutil.rmtree(temp_root, ignore_errors=True)

        log_event(logger, "transcript_repo_downloaded", cache_dir=str(cache_dir))
        return cache_dir

    def load_transcript_files(self) -> list[Path]:
        fixture_files = sorted(self.settings.transcript_fixture_dir.glob("episodes/*/transcript.md"))
        cache_dir = self.settings.transcript_cache_dir
        episodes_dir = cache_dir / "episodes"

        if episodes_dir.exists():
            files = sorted(episodes_dir.glob("*/transcript.md"))
            if files:
                return files

        if self.settings.env == "test" and fixture_files:
            return fixture_files

        try:
            root = self.ensure_source_repo()
            files = sorted(root.glob("episodes/*/transcript.md"))
            if files:
                return files
        except Exception as exc:
            logger.warning("transcript_repo_download_failed", extra={"error": str(exc)})

        return fixture_files

    def build_index(self) -> dict[str, Any]:
        files = self.load_transcript_files()
        chunks: list[ChunkRecord] = []
        for path in files:
            metadata, body = self._parse_transcript(path)
            chunks.extend(self._chunk_transcript(path, metadata, body))

        if not chunks:
            raise RuntimeError("No transcripts found to index")

        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
        matrix = vectorizer.fit_transform([chunk.text for chunk in chunks])

        self.settings.processed_index_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"vectorizer": vectorizer, "matrix": matrix}, self.settings.processed_index_path)
        self.settings.processed_manifest_path.write_text(
            json.dumps([asdict(chunk) for chunk in chunks], indent=2, default=str), encoding="utf-8"
        )

        log_event(
            logger,
            "knowledge_index_built",
            transcripts_indexed=len(files),
            chunks_indexed=len(chunks),
            index_path=str(self.settings.processed_index_path),
        )
        return {
            "transcripts_indexed": len(files),
            "chunks_indexed": len(chunks),
            "source_dir": str(files[0].parents[2] if files else self.settings.transcript_fixture_dir),
        }

    def _parse_transcript(self, path: Path) -> tuple[dict[str, Any], str]:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                metadata = yaml.safe_load(parts[1]) or {}
                body = parts[2].strip()
                return metadata, body
        return {}, raw

    def _chunk_transcript(self, path: Path, metadata: dict[str, Any], text: str) -> list[ChunkRecord]:
        normalized = re.sub(r"\n{3,}", "\n\n", text).strip()
        paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
        chunk_size = self.settings.retrieval_chunk_size
        overlap = self.settings.retrieval_chunk_overlap
        chunks: list[str] = []
        current = ""

        for paragraph in paragraphs:
            if len(current) + len(paragraph) + 2 <= chunk_size:
                current = f"{current}\n\n{paragraph}".strip()
            else:
                if current:
                    chunks.append(current)
                    tail = current[-overlap:]
                    current = f"{tail}\n\n{paragraph}".strip()
                else:
                    chunks.append(paragraph[:chunk_size])
                    current = paragraph[max(0, chunk_size - overlap) :]
        if current:
            chunks.append(current)

        title = metadata.get("title") or path.parent.name.replace("-", " ").title()
        guest = metadata.get("guest")
        publish_date_raw = metadata.get("publish_date")
        publish_date = str(publish_date_raw) if publish_date_raw is not None else None
        youtube_url = metadata.get("youtube_url")
        description = metadata.get("description")

        records: list[ChunkRecord] = []
        for index, chunk in enumerate(chunks):
            snippet = re.sub(r"\s+", " ", chunk)[:320]
            relative_path = str(path.relative_to(path.parents[2])) if len(path.parents) >= 3 else str(path)
            records.append(
                ChunkRecord(
                    chunk_id=f"{path.parent.name}-{index}",
                    transcript_title=title,
                    guest=guest,
                    publish_date=publish_date,
                    youtube_url=youtube_url,
                    description=description,
                    source_path=relative_path,
                    transcript_path=str(path),
                    text=chunk,
                    snippet=snippet,
                    chunk_index=index,
                )
            )
        return records


class RetrievalService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._index: dict[str, Any] | None = None
        self._chunks: list[dict[str, Any]] | None = None

    def ensure_index(self) -> None:
        if self.settings.processed_index_path.exists() and self.settings.processed_manifest_path.exists():
            return
        TranscriptIngestionService().build_index()

    def load(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if self._index is None or self._chunks is None:
            self.ensure_index()
            self._index = joblib.load(self.settings.processed_index_path)
            self._chunks = json.loads(self.settings.processed_manifest_path.read_text(encoding="utf-8"))
        return self._index, self._chunks

    def refresh(self) -> dict[str, Any]:
        self._index = None
        self._chunks = None
        return TranscriptIngestionService().build_index()

    def search(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        index, chunks = self.load()
        top_k = top_k or self.settings.max_chunks_per_answer
        vectorizer = index["vectorizer"]
        matrix = index["matrix"]
        query_vector = vectorizer.transform([query])
        similarities = cosine_similarity(query_vector, matrix).flatten()
        scored = [
            {**chunk, "score": float(score)}
            for chunk, score in zip(chunks, similarities, strict=False)
            if float(score) > 0
        ]
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    def summarize_search(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        if not results:
            return {"matched_chunks": 0, "top_score": 0.0, "status": "empty"}
        top_score = max(item["score"] for item in results)
        status = "grounded" if top_score >= self.settings.retrieval_score_threshold else "weak_match"
        return {"matched_chunks": len(results), "top_score": round(top_score, 4), "status": status}

    def health(self) -> str:
        try:
            self.load()
            return "ready"
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("knowledge_base_unavailable", extra={"error": str(exc)})
            return "missing"
