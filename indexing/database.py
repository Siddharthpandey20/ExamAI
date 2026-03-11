"""
database.py — SQLAlchemy engine, session factory, and dependency provider.

Production patterns:
  - Engine created once at module level (connection pooling)
  - sessionmaker factory bound to that engine
  - get_db() is a generator that yields a session and guarantees cleanup
  - init_db() creates all tables on first run

Concurrency:
  - SQLite WAL mode + busy_timeout=30s prevents "database is locked" errors
  - NullPool: each thread gets its own connection (no cross-thread sharing)
  - Short-lived sessions: open → work → commit → close (no long holds)

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

from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import Session, sessionmaker

from indexing.config import SQLITE_DB_URL
from indexing.models import Base

log = logging.getLogger(__name__)

# ── Engine ───────────────────────────────────────────────────────────────
# SQLite concurrency strategy:
#   - NullPool: each thread gets its own fresh connection (no sharing)
#   - check_same_thread=False for multi-threaded pipelines
#   - timeout=30 → SQLite retries for 30s before raising "database is locked"
#   - WAL mode allows concurrent readers with one writer
#   - busy_timeout=30000ms as safety net for write contention

engine = create_engine(
    SQLITE_DB_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    },
    poolclass=NullPool,
)

# Enable WAL mode, foreign keys, and busy timeout for every new SQLite connection
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.execute("PRAGMA synchronous=NORMAL")
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


def get_db_dep() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a session.

    Usage:
        @router.get("/...")
        def endpoint(db: Session = Depends(get_db_dep)):
            ...
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


def _safe_alter(eng, sql):
    """Run an ALTER TABLE, silently ignoring 'column already exists' errors."""
    with eng.connect() as conn:
        try:
            conn.execute(text(sql))
            conn.commit()
        except Exception:
            pass


def init_db():
    """Create all tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)
    # Dev migration: ensure query_cache has content_fingerprint column
    with engine.connect() as conn:
        try:
            conn.execute(text("SELECT content_fingerprint FROM query_cache LIMIT 1"))
        except Exception:
            try:
                conn.execute(text(
                    "ALTER TABLE query_cache ADD COLUMN content_fingerprint TEXT"
                ))
                conn.commit()
            except Exception:
                pass

    # Dev migration: ensure job_phases has progress columns
    _safe_alter(engine, "ALTER TABLE job_phases ADD COLUMN progress_pct INTEGER DEFAULT 0")
    _safe_alter(engine, "ALTER TABLE job_phases ADD COLUMN progress_detail TEXT")

    log.info(f"[Database] Tables ensured at {SQLITE_DB_URL}")
