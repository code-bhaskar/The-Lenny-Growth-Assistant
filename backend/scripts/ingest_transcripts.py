from app.db.session import get_session_factory, init_db
from app.services.knowledge import TranscriptIngestionService

if __name__ == "__main__":
    init_db()
    db = get_session_factory()()
    try:
        print(TranscriptIngestionService().ingest(db))
    finally:
        db.close()
