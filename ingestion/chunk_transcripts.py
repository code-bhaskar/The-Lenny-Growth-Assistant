from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.knowledge import TranscriptIngestionService  # noqa: E402


if __name__ == "__main__":
    service = TranscriptIngestionService()
    files = service.transcript_files()
    if not files:
        print("No transcript files found")
    else:
        metadata, body = service._parse_transcript(files[0])
        chunks = service._chunk_text(body)
        print({"file": str(files[0]), "chunk_count": len(chunks), "title": metadata.get('title')})
