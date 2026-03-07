"""
database.py — SQLAlchemy engine, session factory, and dependency provider.

Production patterns:
  - Engine created once at module level (connection pooling)
  - sessionmaker factory bound to that engine
  - get_db() is a generator that yields a session and guarantees cleanup
  - init_db() creates all tables on first run

Usage in pipeline:
    from indexing.database import get_db, init_db

    init_db()                          # call once at startup

    with get_db() as session:          # context-manager style
        repo.insert_document(session, ...)

Usage as a dependency (FastAPI-style):
    def some_endpoint(db: Session = Depends(get_db)):
        ...
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from indexing.config import SQLITE_DB_URL
from indexing.models import Base

log = logging.getLogger(__name__)

# ── Engine ───────────────────────────────────────────────────────────────};
# SQLite-specific: check_same_thread=False for multi-threaded pipelines,
# pool_pre_ping guards against stale connections.

engine = create_engine(
    SQLITE_DB_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args={"check_same_thread": False},
)

# Enable WAL mode and foreign keys for every new SQLite connection
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ── Session factory ──────────────────────────────────────────────────────

SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# ── Dependency provider ──────────────────────────────────────────────────

@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Yield a SQLAlchemy session and guarantee cleanup.

    Usage:
        with get_db() as session:
            ...

    On success the session is committed; on exception it is rolled back.
    The session is always closed at the end.
    """
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ── Bootstrap ────────────────────────────────────────────────────────────

def init_db():
    """Create all tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)
    log.info(f"[Database] Tables ensured at {SQLITE_DB_URL}")
