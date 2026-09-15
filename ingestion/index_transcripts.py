from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import get_session_factory, init_db  # noqa: E402
from app.services.knowledge import RetrievalService, TranscriptIngestionService  # noqa: E402


if __name__ == "__main__":
    init_db()
    db = get_session_factory()()
    try:
        print(TranscriptIngestionService().ingest(db))
        retrieval = RetrievalService()
        retrieval.refresh_cache(db)
        print({"status": "ready", "rows": len(retrieval._rows)})
    finally:
        db.close()
