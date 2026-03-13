"""
db_sqlite.py — Repository layer for SQLite operations.

All database access goes through plain functions that accept a
SQLAlchemy Session. This keeps the DB logic decoupled from session
lifecycle management (which lives in database.py).

The file_hash column enables fast skip-if-already-processed logic:
  upload → MD5 → check SQLite → skip re-processing if hash exists.
"""

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from indexing.models import Document, Slide

log = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────

def md5_file(filepath: str) -> str:
    """Return the hex MD5 digest of a file."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── Document operations ──────────────────────────────────────────────────

def get_document_by_hash(session: Session, file_hash: str) -> Document | None:
    """Return the Document for a given hash, or None."""
    return session.query(Document).filter(Document.file_hash == file_hash).first()


def insert_document(
    session: Session,
    filename: str,
    file_hash: str,
    subject: str = "",
    ai_subject: str = "",
    subject_id: int | None = None,
    summary: str = "",
    core_topics: str = "",
    chapters_json: str = "",
    total_slides: int = 0,
    original_filename: str = "",
) -> Document:
    """Insert a new document record with metadata. Returns the ORM object."""
    doc = Document(
        filename=filename,
        original_filename=original_filename or None,
        file_hash=file_hash,
        processed_at=datetime.now(timezone.utc),
        status="processed",
        subject=subject,
        ai_subject=ai_subject,
        subject_id=subject_id,
        summary=summary,
        core_topics=core_topics,
        chapters_json=chapters_json,
        total_slides=total_slides,
    )
    session.add(doc)
    session.flush()
    return doc


# ── Slide operations ─────────────────────────────────────────────────────

def upsert_slide(
    session: Session,
    doc_id: int,
    page_number: int,
    slide_type: str,
    exam_signal: bool,
    raw_text: str,
    summary: str,
    concepts: str,
    chapter: str,
    subject: str = "",
) -> Slide:
    """Insert or update a slide record. Returns the ORM object."""
    slide = (
        session.query(Slide)
        .filter(Slide.doc_id == doc_id, Slide.page_number == page_number)
        .first()
    )
    if slide:
        slide.slide_type = slide_type
        slide.exam_signal = exam_signal
        slide.raw_text = raw_text
        slide.summary = summary
        slide.concepts = concepts
        slide.chapter = chapter
        slide.subject = subject
        slide.is_embedded = False
    else:
        slide = Slide(
            doc_id=doc_id,
            page_number=page_number,
            slide_type=slide_type,
            exam_signal=exam_signal,
            raw_text=raw_text,
            summary=summary,
            concepts=concepts,
            chapter=chapter,
            subject=subject,
            is_embedded=False,
        )
        session.add(slide)

    session.flush()
    return slide


def mark_slides_embedded(session: Session, slide_ids: list[int]):
    """Bulk-flag slides as embedded in ChromaDB."""
    session.query(Slide).filter(Slide.id.in_(slide_ids)).update(
        {Slide.is_embedded: True}, synchronize_session="fetch"
    )


def get_unembedded_slides(session: Session, doc_id: int) -> list[Slide]:
    """Return slides not yet embedded for a document."""
    return (
        session.query(Slide)
        .filter(Slide.doc_id == doc_id, Slide.is_embedded == False)
        .all()
    )


def get_all_slides(session: Session, doc_id: int) -> list[Slide]:
    """Return all slides for a document, ordered by page number."""
    return (
        session.query(Slide)
        .filter(Slide.doc_id == doc_id)
        .order_by(Slide.page_number)
        .all()
    )


def get_slide_count(session: Session, doc_id: int) -> int:
    return session.query(func.count(Slide.id)).filter(Slide.doc_id == doc_id).scalar()
