"""
routes/subjects.py — Subject management endpoints.

GET  /api/subjects          — list all subjects with stats
POST /api/subjects          — create a new subject
GET  /api/subjects/{name}   — single subject with detailed stats
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from indexing.database import get_db_dep
from indexing.models import Subject, Document, Slide, PYQQuestion
from indexing.config import ensure_subject_dirs

router = APIRouter()


# ── Request / Response schemas ───────────────────────────────────────────

class SubjectCreate(BaseModel):
    name: str


class SubjectStats(BaseModel):
    name: str
    created_at: str
    documents: int
    slides: int
    pyq_papers: int
    pyq_questions: int
    has_pyq: bool


class SubjectDetail(SubjectStats):
    document_list: list[dict]


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("", response_model=list[SubjectStats])
def list_subjects(db: Session = Depends(get_db_dep)):
    """List all subjects with summary stats."""
    subjects = db.query(Subject).order_by(Subject.name).all()
    result = []
    for s in subjects:
        doc_count = (
            db.query(func.count(Document.id))
            .filter(Document.subject == s.name)
            .scalar()
        )
        slide_count = (
            db.query(func.count(Slide.id))
            .filter(Slide.subject == s.name)
            .scalar()
        )
        pyq_q_count = (
            db.query(func.count(PYQQuestion.id))
            .filter(PYQQuestion.subject == s.name)
            .scalar()
        )
        pyq_papers = (
            db.query(func.count(func.distinct(PYQQuestion.source_file)))
            .filter(PYQQuestion.subject == s.name)
            .scalar()
        )
        result.append(SubjectStats(
            name=s.name,
            created_at=s.created_at.isoformat() if s.created_at else "",
            documents=doc_count,
            slides=slide_count,
            pyq_papers=pyq_papers,
            pyq_questions=pyq_q_count,
            has_pyq=pyq_q_count > 0,
        ))
    return result


@router.post("", response_model=SubjectStats, status_code=201)
def create_subject(body: SubjectCreate, db: Session = Depends(get_db_dep)):
    """Create a new subject and its data directories."""
    name = body.name.strip().upper()
    if not name:
        raise HTTPException(status_code=400, detail="Subject name cannot be empty.")

    existing = db.query(Subject).filter(Subject.name == name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Subject '{name}' already exists.")

    subject = Subject(name=name, created_at=datetime.now(timezone.utc))
    db.add(subject)
    db.flush()

    # Create data directories
    ensure_subject_dirs(name)

    return SubjectStats(
        name=subject.name,
        created_at=subject.created_at.isoformat(),
        documents=0,
        slides=0,
        pyq_papers=0,
        pyq_questions=0,
        has_pyq=False,
    )


@router.get("/{name}", response_model=SubjectDetail)
def get_subject(name: str, db: Session = Depends(get_db_dep)):
    """Get detailed info for a specific subject."""
    subject = db.query(Subject).filter(Subject.name == name).first()
    if not subject:
        raise HTTPException(status_code=404, detail=f"Subject '{name}' not found.")

    docs = (
        db.query(Document)
        .filter(Document.subject == name)
        .order_by(Document.processed_at.desc())
        .all()
    )
    slide_count = (
        db.query(func.count(Slide.id))
        .filter(Slide.subject == name)
        .scalar()
    )
    pyq_q_count = (
        db.query(func.count(PYQQuestion.id))
        .filter(PYQQuestion.subject == name)
        .scalar()
    )
    pyq_papers = (
        db.query(func.count(func.distinct(PYQQuestion.source_file)))
        .filter(PYQQuestion.subject == name)
        .scalar()
    )

    doc_list = [
        {
            "id": d.id,
            "filename": d.filename,
            "status": d.status,
            "total_slides": d.total_slides,
            "core_topics": d.core_topics,
            "processed_at": d.processed_at.isoformat() if d.processed_at else None,
        }
        for d in docs
    ]

    return SubjectDetail(
        name=subject.name,
        created_at=subject.created_at.isoformat() if subject.created_at else "",
        documents=len(docs),
        slides=slide_count,
        pyq_papers=pyq_papers,
        pyq_questions=pyq_q_count,
        has_pyq=pyq_q_count > 0,
        document_list=doc_list,
    )
