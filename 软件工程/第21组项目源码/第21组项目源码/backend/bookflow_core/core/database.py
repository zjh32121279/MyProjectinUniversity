from __future__ import annotations

from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from bookflow_core.core.config import project_root, settings
from bookflow_core.db.ai_kernel_schema import ensure_ai_kernel_schema
from bookflow_core.db.catalog_schema import ensure_catalog_schema
from bookflow_core.db.reader_schema import ensure_reader_schema
from bookflow_core.db.views import create_views, drop_views
from bookflow_core.models import Base

_engine = None
_SessionLocal = None


def _normalize_database_url(url: str) -> str:
    if url.startswith("sqlite:///./"):
        relative = url.removeprefix("sqlite:///./")
        return f"sqlite:///{(project_root() / relative).as_posix()}"
    return url


def get_engine(database_url: str | None = None):
    global _engine, _SessionLocal
    url = _normalize_database_url(database_url or settings.database_url)
    if _engine is None or str(_engine.url) != url.replace("sqlite:///", "sqlite:"):
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=connect_args, future=True)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _set_sqlite_pragmas(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
            ensure_ai_kernel_schema(_engine)
            ensure_catalog_schema(_engine)
            ensure_reader_schema(_engine)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


def create_db(database_url: str | None = None) -> None:
    """Create the explicit BookFlow schema and read-only aggregate views."""
    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    ensure_ai_kernel_schema(engine)
    ensure_catalog_schema(engine)
    ensure_reader_schema(engine)
    create_views(engine)


def ensure_schema(database_url: str | None = None) -> None:
    """Ensure the explicit BookFlow schema exists for app startup."""
    create_db(database_url)


def drop_db(database_url: str | None = None) -> None:
    engine = get_engine(database_url)
    drop_views(engine)
    Base.metadata.drop_all(bind=engine)


def get_session() -> Session:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal()


@contextmanager
def session_scope():
    db = get_session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()
