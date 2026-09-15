from __future__ import annotations

import io
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger, info, warning
from app.db.models import Source, TranscriptChunk

logger = get_logger(__name__)


@dataclass
class SearchResult:
    source_id: str
    transcript_title: str
    source_path: str
    source_url: str | None
    guest: str | None
    publish_date: str | None
    snippet: str
    chunk_index: int
    content: str
    score: float


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
            warning(logger, "transcript_repo_ssl_verification_failed", url=self.settings.transcript_repo_url)
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

        info(logger, "transcript_repo_downloaded", cache_dir=str(cache_dir))
        return cache_dir

    def transcript_files(self) -> list[Path]:
        fixture_files = sorted(self.settings.transcript_fixture_dir.glob("episodes/*/transcript.md"))
        cache_dir = self.settings.transcript_cache_dir
        if (cache_dir / "episodes").exists():
            files = sorted(cache_dir.glob("episodes/*/transcript.md"))
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
            warning(logger, "transcript_repo_download_failed", error=str(exc))
        return fixture_files

    def ingest(self, db: Session) -> dict[str, Any]:
        files = self.transcript_files()
        if not files:
            raise RuntimeError("No transcript files available for ingestion")

        db.execute(delete(TranscriptChunk))
        db.execute(delete(Source))
        db.flush()

        total_chunks = 0
        for path in files:
            metadata, body = self._parse_transcript(path)
            relative_path = self._relative_source_path(path)
            source = Source(
                title=metadata.get("title") or path.parent.name.replace("-", " ").title(),
                url=metadata.get("youtube_url"),
                metadata_json={
                    "guest": metadata.get("guest"),
                    "publish_date": str(metadata.get("publish_date")) if metadata.get("publish_date") else None,
                    "description": metadata.get("description"),
                    "source_path": relative_path,
                },
            )
            db.add(source)
            db.flush()
            chunks = self._chunk_text(body)
            for idx, chunk in enumerate(chunks):
                db.add(
                    TranscriptChunk(
                        source_id=source.id,
                        chunk_index=idx,
                        content=chunk,
                        metadata_json={
                            "source_path": relative_path,
                            "guest": metadata.get("guest"),
                            "publish_date": str(metadata.get("publish_date")) if metadata.get("publish_date") else None,
                            "youtube_url": metadata.get("youtube_url"),
                            "description": metadata.get("description"),
                            "title": source.title,
                            "snippet": re.sub(r"\s+", " ", chunk)[:320],
                        },
                        embedding=None,
                    )
                )
                total_chunks += 1
        db.commit()
        info(
            logger,
            "transcripts_ingested",
            sources_indexed=len(files),
            chunks_indexed=total_chunks,
        )
        return {
            "sources_indexed": len(files),
            "chunks_indexed": total_chunks,
            "source_dir": str(files[0].parents[2]),
            "timestamp": datetime.now(timezone.utc),
        }

    def _parse_transcript(self, path: Path) -> tuple[dict[str, Any], str]:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                metadata = yaml.safe_load(parts[1]) or {}
                return metadata, parts[2].strip()
        return {}, raw

    def _chunk_text(self, text: str) -> list[str]:
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
                    current = f"{current[-overlap:]}\n\n{paragraph}".strip()
                else:
                    chunks.append(paragraph[:chunk_size])
                    current = paragraph[max(0, chunk_size - overlap) :]
        if current:
            chunks.append(current)
        return chunks or [normalized]

    def _relative_source_path(self, path: Path) -> str:
        for root in (self.settings.transcript_cache_dir, self.settings.transcript_fixture_dir):
            try:
                return str(path.relative_to(root))
            except ValueError:
                continue
        return str(path)


class RetrievalService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._cache_signature: tuple[int, int] | None = None
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._rows: list[dict[str, Any]] = []

    def refresh_cache(self, db: Session) -> None:
        rows = self._fetch_rows(db)
        signature = (len(rows), sum(len(row["content"]) for row in rows))
        if self._cache_signature == signature and self._vectorizer is not None and self._matrix is not None:
            return
        self._rows = rows
        self._cache_signature = signature
        if rows:
            self._vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
            self._matrix = self._vectorizer.fit_transform([row["content"] for row in rows])
        else:
            self._vectorizer = None
            self._matrix = None

    def search(self, db: Session, query: str, top_k: int | None = None) -> list[SearchResult]:
        self.refresh_cache(db)
        if not self._rows or self._vectorizer is None or self._matrix is None:
            return []
        top_k = top_k or self.settings.max_chunks_per_answer
        query_vector = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vector, self._matrix).flatten()
        paired = []
        for row, score in zip(self._rows, scores, strict=False):
            if float(score) <= 0:
                continue
            paired.append((row, float(score)))
        paired.sort(key=lambda item: item[1], reverse=True)
        results: list[SearchResult] = []
        for row, score in paired[:top_k]:
            results.append(
                SearchResult(
                    source_id=row["source_id"],
                    transcript_title=row["transcript_title"],
                    source_path=row["source_path"],
                    source_url=row.get("source_url"),
                    guest=row.get("guest"),
                    publish_date=row.get("publish_date"),
                    snippet=row["snippet"],
                    chunk_index=row["chunk_index"],
                    content=row["content"],
                    score=score,
                )
            )
        return results

    def summarize(self, results: list[SearchResult]) -> dict[str, Any]:
        if not results:
            return {"matched_chunks": 0, "top_score": 0.0, "status": "empty"}
        top_score = max(item.score for item in results)
        status = "grounded" if top_score >= self.settings.retrieval_score_threshold else "weak_match"
        return {"matched_chunks": len(results), "top_score": round(top_score, 4), "status": status}

    def health(self, db: Session) -> str:
        rows = self._fetch_rows(db)
        return "ready" if rows else "missing"

    def build_context_block(self, results: list[SearchResult]) -> str:
        blocks = []
        for idx, item in enumerate(results, start=1):
            blocks.append(
                "\n".join(
                    [
                        f"[S{idx}] {item.transcript_title}",
                        f"Guest: {item.guest or 'Unknown'}",
                        f"Publish date: {item.publish_date or 'Unknown'}",
                        f"Source path: {item.source_path}",
                        f"Source URL: {item.source_url or 'Unknown'}",
                        "Transcript excerpt:",
                        item.content,
                    ]
                )
            )
        return "\n\n".join(blocks)

    def to_citations(self, results: list[SearchResult]) -> list[dict[str, Any]]:
        return [
            {
                "source_id": item.source_id,
                "transcript_title": item.transcript_title,
                "source_path": item.source_path,
                "source_url": item.source_url,
                "guest": item.guest,
                "publish_date": item.publish_date,
                "snippet": item.snippet,
                "chunk_index": item.chunk_index,
                "score": round(item.score, 4),
            }
            for item in results
        ]

    def _fetch_rows(self, db: Session) -> list[dict[str, Any]]:
        query = (
            select(TranscriptChunk, Source)
            .join(Source, TranscriptChunk.source_id == Source.id)
            .order_by(Source.title.asc(), TranscriptChunk.chunk_index.asc())
        )
        rows = []
        for chunk, source in db.execute(query).all():
            meta = chunk.metadata_json or {}
            source_meta = source.metadata_json or {}
            rows.append(
                {
                    "source_id": source.id,
                    "transcript_title": source.title,
                    "source_path": meta.get("source_path") or source_meta.get("source_path") or "",
                    "source_url": source.url,
                    "guest": meta.get("guest") or source_meta.get("guest"),
                    "publish_date": meta.get("publish_date") or source_meta.get("publish_date"),
                    "snippet": meta.get("snippet") or re.sub(r"\s+", " ", chunk.content)[:320],
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                }
            )
        return rows
