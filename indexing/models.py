"""
models.py — SQLAlchemy ORM table definitions.

All tables are defined here using the declarative base.
The indexing pipeline uses these models exclusively — no raw SQL.

Tables:
  documents     — one row per source file (keyed by MD5 file_hash)
  slides        — one row per slide, FK → documents
  pyq_questions — past-year questions (populated in later stages)
  pyq_matches   — PYQ ↔ slide similarity links (populated later)
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all models."""
    pass


class Subject(Base):
    __tablename__ = "subjects"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    documents = relationship("Document", back_populates="subject_rel")

    def __repr__(self):
        return f"<Subject id={self.id} name='{self.name}'>"


class Document(Base):
    __tablename__ = "documents"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    filename     = Column(String, nullable=False)
    file_hash    = Column(String, nullable=False, unique=True, index=True)
    processed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    status       = Column(String, nullable=False, default="pending")

    # User-assigned subject (matches subjects.name)
    subject      = Column(String, index=True)
    subject_id   = Column(Integer, ForeignKey("subjects.id"), nullable=True, index=True)

    # Document-level metadata (from structuring pipeline)
    ai_subject   = Column(String)           # AI-extracted subject (from Agent 1)
    summary      = Column(Text)
    core_topics  = Column(Text)          # comma-separated topic list
    chapters_json = Column(Text)         # JSON array: [{name, slide_range, topics}, ...]
    total_slides = Column(Integer, default=0)

    slides = relationship("Slide", back_populates="document", cascade="all, delete-orphan")
    subject_rel = relationship("Subject", back_populates="documents")

    def __repr__(self):
        return f"<Document id={self.id} filename='{self.filename}' status='{self.status}'>"


class Slide(Base):
    __tablename__ = "slides"
    __table_args__ = (
        UniqueConstraint("doc_id", "page_number", name="uq_slide_doc_page"),
    )

    id               = Column(Integer, primary_key=True, autoincrement=True)
    doc_id           = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    page_number      = Column(Integer, nullable=False)
    slide_type       = Column(String)
    exam_signal      = Column(Boolean, default=False)
    raw_text         = Column(Text)
    summary          = Column(Text)
    concepts         = Column(Text)
    chapter          = Column(String)
    subject          = Column(String, index=True)
    is_embedded      = Column(Boolean, default=False)
    pyq_hit_count    = Column(Integer, default=0)
    importance_score = Column(Float, default=0.0)

    document = relationship("Document", back_populates="slides")
    pyq_matches = relationship("PYQMatch", back_populates="slide", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Slide id={self.id} doc={self.doc_id} page={self.page_number}>"


class PYQQuestion(Base):
    __tablename__ = "pyq_questions"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    question_text = Column(Text, nullable=False)
    source_file   = Column(String)
    subject       = Column(String, index=True)
    embedding_id  = Column(String)

    matches = relationship("PYQMatch", back_populates="question", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PYQQuestion id={self.id}>"


class PYQMatch(Base):
    __tablename__ = "pyq_matches"

    pyq_id           = Column(Integer, ForeignKey("pyq_questions.id"), primary_key=True)
    slide_id         = Column(Integer, ForeignKey("slides.id"), primary_key=True)
    similarity_score = Column(Float, nullable=False)

    question = relationship("PYQQuestion", back_populates="matches")
    slide    = relationship("Slide", back_populates="pyq_matches")

    def __repr__(self):
        return f"<PYQMatch pyq={self.pyq_id} slide={self.slide_id} sim={self.similarity_score:.3f}>"


class QueryCache(Base):
    """Cache LLM responses to avoid redundant API calls for repeated queries."""
    __tablename__ = "query_cache"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    subject       = Column(String, nullable=False, index=True)
    query_hash    = Column(String, nullable=False, unique=True, index=True)
    query_text    = Column(Text, nullable=False)
    endpoint      = Column(String, nullable=False)   # search / coverage / study-plan / revision
    response_json = Column(Text, nullable=False)      # full JSON response
    model_used    = Column(String)
    created_at    = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    # "doc_count:slide_count:pyq_count" — invalidate when content changes
    content_fingerprint = Column(String, nullable=True)

    def __repr__(self):
        return f"<QueryCache id={self.id} subject='{self.subject}' endpoint='{self.endpoint}'>"
