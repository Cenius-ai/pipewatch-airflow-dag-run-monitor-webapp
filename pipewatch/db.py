"""Engine + session plumbing for the embedded SQLite datastore."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from . import config
from .models import Base

_lock = threading.Lock()
_engine: Engine | None = None
_session_factory: sessionmaker | None = None


def _ensure_sqlite_directory(url: str) -> None:
    """SQLite will not create a missing parent directory for us."""
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return
    raw_path = url[len(prefix) :]
    if not raw_path or raw_path == ":memory:":
        return
    Path(raw_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def get_engine() -> Engine:
    global _engine, _session_factory
    with _lock:
        if _engine is None:
            url = config.database_url()
            _ensure_sqlite_directory(url)
            connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
            engine = create_engine(url, future=True, connect_args=connect_args)
            if url.startswith("sqlite"):
                event.listen(engine, "connect", _enable_sqlite_foreign_keys)
            _engine = engine
            _session_factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
        return _engine


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """One short-lived session per unit of work (safe across request threads)."""
    get_engine()
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    get_engine()
    Base.metadata.create_all(get_engine())


def bootstrap_database() -> None:
    """Create the schema and idempotently seed demo data on the normal boot path."""
    from .seed import seed_if_empty

    init_db()
    seed_if_empty()


def dispose_engine() -> None:
    """Test helper: drop the cached engine so DATABASE_URL changes take effect."""
    global _engine, _session_factory
    with _lock:
        if _engine is not None:
            _engine.dispose()
        _engine = None
        _session_factory = None
