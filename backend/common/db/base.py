"""SQLite engine + session. `core` is the sole writer (design decision D4).

WAL mode so future read-only peeks from other processes don't block. Milestone 1
uses `create_all`; Alembic migrations get wired in when the schema starts moving.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def init_db(db_path: Path) -> None:
    """Create the engine, enable WAL, and create tables. Call once at startup."""
    global _engine, _SessionLocal
    _engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(_engine, "connect")
    def _set_pragmas(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)

    # import models so they register on Base.metadata before create_all
    from . import models  # noqa: F401

    Base.metadata.create_all(_engine)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on error."""
    if _SessionLocal is None:
        raise RuntimeError("init_db() must be called before using the database")
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_session() -> Session:
    """FastAPI dependency — yields a session, closes it after the request."""
    if _SessionLocal is None:
        raise RuntimeError("init_db() must be called before using the database")
    s = _SessionLocal()
    try:
        yield s
    finally:
        s.close()
