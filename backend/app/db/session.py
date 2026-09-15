from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        _engine = create_engine(settings.database_url, future=True, pool_pre_ping=True, connect_args=connect_args)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Iterator[Session]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
