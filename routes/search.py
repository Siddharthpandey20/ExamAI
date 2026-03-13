"""
routes/search.py — Phase 7: Search & Retrieval endpoints.

POST /query       — Hybrid search (fast or reasoning mode)
POST /coverage    — Topic coverage detection ("is X in my slides?")
GET  /slides      — Filtered slide listing (by type, chapter, importance)
GET  /concepts    — Concept browser with frequency and slide locations
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Literal
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from agents import trace

from indexing.database import get_db_dep
from indexing.models import Subject, Slide, Document
from engine.fast_mode import fast_search, fast_coverage
from engine.reasoning_mode import run_reasoning

log = logging.getLogger(__name__)
router = APIRouter()
load_dotenv()
    
# ── Request schemas ──────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    subject: str
    mode: str = "fast"   # "fast" or "reasoning"


class CoverageRequest(BaseModel):
    topic: str
    subject: str

SlideType = Literal[
    "definition",
    "syntax/code",
    "comparison",
    "numerical_example",
    "diagram_explanation",
    "summary",
    "concept",
    "example",
    "table",
    "other"
]


# ── Helpers ──────────────────────────────────────────────────────────────

def _require_subject(name: str, db: Session) -> Subject:
    subj = db.query(Subject).filter(Subject.name == name.upper()).first()
    if not subj:
        raise HTTPException(
            status_code=404,
            detail=f"Subject '{name}' not found. Create it first via POST /api/subjects",
        )
    return subj


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/")
def root():
    return {"status": "ok", "router": "search"}

@router.post("/query")
async def search_query(
    body: SearchRequest,
    force: bool = Query(False, description="Bypass cache and force a fresh LLM response"),
    db: Session = Depends(get_db_dep),
):
    """
    Search slides for a query.

    *mode*:
      - **fast** — single hybrid search → Groq-formatted answer (1 LLM call)
      - **reasoning** — AI agent with tools, multi-step analysis (N LLM calls)
    """
    with trace(f"search_query:{body.subject}:{body.mode}"):
        _require_subject(body.subject, db)
        subject = body.subject.strip().upper()

        if body.mode == "reasoning":
            return await run_reasoning(body.query, subject, force=force)
        return await fast_search(body.query, subject, force=force)


@router.post("/coverage")
async def topic_coverage(
    body: CoverageRequest,
    force: bool = Query(False, description="Bypass cache and force a fresh LLM response"),
    db: Session = Depends(get_db_dep),
):
    """
    Check if a topic is covered in the student's slides.

    Returns a YES/NO/PARTIAL verdict with confidence level,
    specific slide references, and closest alternatives if not covered.
    """
    with trace(f"topic_coverage:{body.subject}:{body.topic[:40]}"):
        _require_subject(body.subject, db)
        subject = body.subject.strip().upper()
        return await fast_coverage(body.topic, subject, force=force)


@router.get("/slides/{subject}")
def filter_slides(
    subject: str,
    search: str | None = Query(None, description="Keyword search across summary, concepts, and chapter"),
    slide_type: SlideType | None = Query(None, alias="type", description="Slide type filter (choose from dropdown)"),
    chapter: str | None = Query(None, description="Chapter name (partial match)"),
    doc_id: int | None = Query(None, description="Filter by specific document ID"),
    min_importance: float = Query(0.0, description="Minimum importance score"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db_dep),
):
    """
    List slides with optional filters.

    Useful for browsing numerical problems, definitions, or slides from a
    specific chapter.  Results are sorted by importance score (descending).

    **search** — keyword search across summary, concepts, and chapter name.
    **type** — exact slide type (definition, concept, numerical_example, etc.).
    **chapter** — partial match on chapter name.
    **doc_id** — filter slides from a specific document.
    """
    _require_subject(subject, db)
    subject = subject.strip().upper()
    q = db.query(Slide).filter(Slide.subject == subject, Slide.is_embedded == True)
    if doc_id:
        q = q.filter(Slide.doc_id == doc_id)
    if slide_type:
        q = q.filter(func.lower(Slide.slide_type) == slide_type.strip().lower())
    if chapter:
        q = q.filter(Slide.chapter.ilike(f"%{chapter}%"))
    if min_importance > 0:
        q = q.filter(Slide.importance_score >= min_importance)
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            Slide.summary.ilike(pattern)
            | Slide.concepts.ilike(pattern)
            | Slide.chapter.ilike(pattern)
        )
    slides = q.order_by(Slide.importance_score.desc()).limit(limit).all()
    rows: list[dict] = []
    for sl in slides:
        doc = db.query(Document).filter(Document.id == sl.doc_id).first()
        rows.append({
            "slide_id": sl.id,
            "doc_id": sl.doc_id,
            "page_number": sl.page_number,
            "filename": (doc.original_filename or doc.filename) if doc else "",
            "slide_type": sl.slide_type,
            "chapter": sl.chapter,
            "concepts": sl.concepts,
            "summary": sl.summary,
            "exam_signal": sl.exam_signal,
            "importance_score": sl.importance_score,
            "pyq_hit_count": sl.pyq_hit_count,
        })
    return {"subject": subject, "total": len(rows), "slides": rows}



@router.get("/concepts/{subject}")
def browse_concepts(
    subject: str,
    q: str | None = Query(None, description="Filter concepts by keyword"),
    doc_id: int | None = Query(None, description="Filter by specific document ID"),
    db: Session = Depends(get_db_dep),
):
    """
    Browse extracted concepts for a subject with frequency counts.

    Each concept entry includes the slides it appears on, sorted by
    frequency (most common first).

    **doc_id** — optionally filter to concepts from a single document.
    """
    _require_subject(subject, db)
    subject = subject.strip().upper()

    slide_q = db.query(Slide).filter(
        Slide.subject == subject,
        Slide.concepts.isnot(None),
        Slide.concepts != "",
    )
    if doc_id:
        slide_q = slide_q.filter(Slide.doc_id == doc_id)
    slides = slide_q.all()

    freq: dict[str, int] = {}
    locations: dict[str, list[dict]] = {}

    for sl in slides:
        doc = db.query(Document).filter(Document.id == sl.doc_id).first()
        for raw_concept in sl.concepts.split(","):
            concept = raw_concept.strip()
            if not concept:
                continue
            key = concept.lower()
            if q and q.lower() not in key:
                continue
            freq[key] = freq.get(key, 0) + 1
            locations.setdefault(key, []).append({
                "slide_id": sl.id,
                "doc_id": sl.doc_id,
                "page_number": sl.page_number,
                "summary": sl.summary,
                "pyq_hit_count": sl.pyq_hit_count,
                "filename": (doc.original_filename or doc.filename) if doc else "",
            })

    sorted_concepts = sorted(freq.items(), key=lambda x: x[1], reverse=True)

    return {
        "subject": subject,
        "total": len(sorted_concepts),
        "concepts": [
            {
                "concept": c,
                "frequency": f,
                "slides": locations.get(c, [])[:10],
            }
            for c, f in sorted_concepts
        ],
    }
