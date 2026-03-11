"""
routes/documents.py — Document-level endpoints.

Users see concepts, PYQ matches, and priorities grouped by document first,
then drill down to slides.  This matches how students think: "which file
has the important stuff?" → then "which pages?".

GET  /api/documents/{subject}                     — list uploaded documents
GET  /api/documents/{subject}/{doc_id}            — document detail + chapter map
GET  /api/documents/{subject}/{doc_id}/concepts   — concepts from this document
GET  /api/documents/{subject}/{doc_id}/pyq        — PYQ matches for this document
GET  /api/documents/{subject}/{doc_id}/priorities  — priority slides from this doc
GET  /api/documents/{subject}/{doc_id}/summary     — AI-generated document summary
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from indexing.database import get_db_dep
from indexing.models import Subject, Document, Slide, PYQQuestion, PYQMatch
from engine.config import HIGH_PRIORITY_THRESHOLD, MEDIUM_PRIORITY_THRESHOLD

router = APIRouter()
log = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────

def _require_subject(name: str, db: Session) -> Subject:
    subj = db.query(Subject).filter(Subject.name == name.upper()).first()
    if not subj:
        raise HTTPException(404, f"Subject '{name}' not found.")
    return subj


def _require_document(doc_id: int, subject: str, db: Session) -> Document:
    doc = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.subject == subject)
        .first()
    )
    if not doc:
        raise HTTPException(404, f"Document #{doc_id} not found in subject '{subject}'.")
    return doc


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/{subject}")
def list_documents(subject: str, db: Session = Depends(get_db_dep)):
    """
    List all processed documents for a subject with per-document stats.

    Each document shows: slide count, concept count, PYQ hit count,
    average importance, chapter list, and top concepts.
    """
    _require_subject(subject, db)
    subject = subject.strip().upper()

    docs = (
        db.query(Document)
        .filter(Document.subject == subject)
        .order_by(Document.processed_at.desc())
        .all()
    )

    result = []
    for doc in docs:
        slides = db.query(Slide).filter(Slide.doc_id == doc.id).all()
        embedded_count = sum(1 for s in slides if s.is_embedded)
        total_pyq_hits = sum(s.pyq_hit_count or 0 for s in slides)
        avg_importance = (
            sum(s.importance_score or 0 for s in slides) / len(slides)
            if slides else 0
        )
        high_priority = sum(
            1 for s in slides
            if (s.importance_score or 0) >= HIGH_PRIORITY_THRESHOLD
        )

        # Collect unique concepts across all slides
        all_concepts = set()
        for s in slides:
            for c in (s.concepts or "").split(","):
                c = c.strip()
                if c:
                    all_concepts.add(c.lower())

        # Parse chapters
        chapters = []
        if doc.chapters_json:
            try:
                chapters = json.loads(doc.chapters_json)
            except (json.JSONDecodeError, TypeError):
                pass

        result.append({
            "id": doc.id,
            "filename": doc.filename,
            "status": doc.status,
            "subject": doc.subject,
            "ai_subject": doc.ai_subject,
            "summary": doc.summary or "",
            "core_topics": doc.core_topics or "",
            "total_slides": doc.total_slides or len(slides),
            "embedded_slides": embedded_count,
            "total_pyq_hits": total_pyq_hits,
            "avg_importance": round(avg_importance, 3),
            "high_priority_slides": high_priority,
            "unique_concepts": len(all_concepts),
            "top_concepts": sorted(all_concepts)[:15],
            "chapters": chapters,
            "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
        })

    return {"subject": subject, "total": len(result), "documents": result}


@router.get("/{subject}/{doc_id}")
def document_detail(
    subject: str, doc_id: int, db: Session = Depends(get_db_dep),
):
    """
    Full document detail: metadata, chapter map, and all slides.
    """
    _require_subject(subject, db)
    subject = subject.strip().upper()
    doc = _require_document(doc_id, subject, db)

    slides = (
        db.query(Slide)
        .filter(Slide.doc_id == doc.id)
        .order_by(Slide.page_number)
        .all()
    )

    chapters = []
    if doc.chapters_json:
        try:
            chapters = json.loads(doc.chapters_json)
        except (json.JSONDecodeError, TypeError):
            pass

    slide_list = []
    for sl in slides:
        slide_list.append({
            "slide_id": sl.id,
            "page_number": sl.page_number,
            "slide_type": sl.slide_type or "other",
            "chapter": sl.chapter or "",
            "concepts": sl.concepts or "",
            "summary": sl.summary or "",
            "exam_signal": bool(sl.exam_signal),
            "pyq_hit_count": sl.pyq_hit_count or 0,
            "importance_score": sl.importance_score or 0.0,
            "is_embedded": sl.is_embedded,
        })

    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "subject": doc.subject,
        "ai_subject": doc.ai_subject,
        "summary": doc.summary or "",
        "core_topics": doc.core_topics or "",
        "chapters": chapters,
        "total_slides": len(slides),
        "slides": slide_list,
    }


@router.get("/{subject}/{doc_id}/concepts")
def document_concepts(
    subject: str,
    doc_id: int,
    q: str | None = Query(None, description="Filter concepts by keyword"),
    db: Session = Depends(get_db_dep),
):
    """
    Concepts extracted from a specific document, with frequency and slide locations.

    This is the document-first view: "what concepts does this file teach?" —
    then the student can drill into specific slides.
    """
    _require_subject(subject, db)
    subject = subject.strip().upper()
    doc = _require_document(doc_id, subject, db)

    slides = (
        db.query(Slide)
        .filter(Slide.doc_id == doc.id, Slide.concepts.isnot(None), Slide.concepts != "")
        .all()
    )

    freq: dict[str, int] = {}
    locations: dict[str, list[dict]] = {}

    for sl in slides:
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
                "page_number": sl.page_number,
                "slide_type": sl.slide_type or "other",
                "importance_score": sl.importance_score or 0.0,
                "pyq_hit_count": sl.pyq_hit_count or 0,
            })

    sorted_concepts = sorted(freq.items(), key=lambda x: x[1], reverse=True)

    return {
        "subject": subject,
        "doc_id": doc.id,
        "filename": doc.filename,
        "total": len(sorted_concepts),
        "concepts": [
            {
                "concept": c,
                "frequency": f,
                "slides": locations.get(c, []),
            }
            for c, f in sorted_concepts
        ],
    }


@router.get("/{subject}/{doc_id}/pyq")
def document_pyq_matches(
    subject: str, doc_id: int, db: Session = Depends(get_db_dep),
):
    """
    PYQ questions that match slides in this specific document.

    Shows each matching question with its matched slides from this document,
    similarity scores, and the specific concepts/pages involved.
    """
    _require_subject(subject, db)
    subject = subject.strip().upper()
    doc = _require_document(doc_id, subject, db)

    # Get all slide IDs for this document
    doc_slide_ids = {
        sl.id for sl in db.query(Slide.id).filter(Slide.doc_id == doc.id).all()
    }
    if not doc_slide_ids:
        return {
            "subject": subject,
            "doc_id": doc.id,
            "filename": doc.filename,
            "total_questions": 0,
            "questions": [],
        }

    # Find PYQ matches that hit this document's slides
    matches = (
        db.query(PYQMatch, PYQQuestion, Slide)
        .join(PYQQuestion, PYQMatch.pyq_id == PYQQuestion.id)
        .join(Slide, PYQMatch.slide_id == Slide.id)
        .filter(PYQMatch.slide_id.in_(doc_slide_ids))
        .order_by(desc(PYQMatch.similarity_score))
        .all()
    )

    # Group by question
    questions_map: dict[int, dict] = {}
    for m, q, sl in matches:
        if q.id not in questions_map:
            questions_map[q.id] = {
                "question_id": q.id,
                "question_text": q.question_text,
                "source_file": q.source_file or "",
                "matched_slides": [],
            }
        questions_map[q.id]["matched_slides"].append({
            "slide_id": sl.id,
            "page_number": sl.page_number,
            "chapter": sl.chapter or "",
            "concepts": sl.concepts or "",
            "summary": sl.summary or "",
            "similarity_score": round(m.similarity_score, 4),
        })

    questions = sorted(questions_map.values(), key=lambda x: len(x["matched_slides"]), reverse=True)

    return {
        "subject": subject,
        "doc_id": doc.id,
        "filename": doc.filename,
        "total_questions": len(questions),
        "total_matches": sum(len(q["matched_slides"]) for q in questions),
        "questions": questions,
    }


@router.get("/{subject}/{doc_id}/priorities")
def document_priorities(
    subject: str, doc_id: int, db: Session = Depends(get_db_dep),
):
    """
    Priority tiers for slides within a specific document.

    Classifies slides into High / Medium / Low based on importance_score.
    Includes chapter-level aggregation so students see which chapters
    in this file matter most.
    """
    _require_subject(subject, db)
    subject = subject.strip().upper()
    doc = _require_document(doc_id, subject, db)

    slides = (
        db.query(Slide)
        .filter(Slide.doc_id == doc.id, Slide.is_embedded == True)
        .order_by(desc(Slide.importance_score))
        .all()
    )

    high, medium, low = [], [], []
    chapter_scores: dict[str, dict] = {}

    for sl in slides:
        d = {
            "slide_id": sl.id,
            "page_number": sl.page_number,
            "slide_type": sl.slide_type or "other",
            "chapter": sl.chapter or "",
            "concepts": sl.concepts or "",
            "summary": sl.summary or "",
            "importance_score": sl.importance_score or 0.0,
            "pyq_hit_count": sl.pyq_hit_count or 0,
        }

        if (sl.importance_score or 0) >= HIGH_PRIORITY_THRESHOLD:
            high.append(d)
        elif (sl.importance_score or 0) >= MEDIUM_PRIORITY_THRESHOLD:
            medium.append(d)
        else:
            low.append(d)

        # Chapter-level aggregation
        ch = sl.chapter or "Uncategorized"
        if ch not in chapter_scores:
            chapter_scores[ch] = {
                "chapter": ch,
                "slide_count": 0,
                "high_count": 0,
                "total_importance": 0.0,
                "total_pyq_hits": 0,
            }
        chapter_scores[ch]["slide_count"] += 1
        if (sl.importance_score or 0) >= HIGH_PRIORITY_THRESHOLD:
            chapter_scores[ch]["high_count"] += 1
        chapter_scores[ch]["total_importance"] += sl.importance_score or 0
        chapter_scores[ch]["total_pyq_hits"] += sl.pyq_hit_count or 0

    # Average importance per chapter
    for ch_data in chapter_scores.values():
        n = ch_data["slide_count"]
        ch_data["avg_importance"] = round(ch_data["total_importance"] / n, 3) if n else 0

    chapters_ranked = sorted(
        chapter_scores.values(),
        key=lambda x: x["avg_importance"],
        reverse=True,
    )

    return {
        "subject": subject,
        "doc_id": doc.id,
        "filename": doc.filename,
        "high": high,
        "medium": medium,
        "low": low,
        "stats": {
            "high_count": len(high),
            "medium_count": len(medium),
            "low_count": len(low),
            "total": len(slides),
        },
        "chapters_ranked": chapters_ranked,
    }


@router.get("/{subject}/{doc_id}/summary")
def document_summary(
    subject: str, doc_id: int, db: Session = Depends(get_db_dep),
):
    """
    Comprehensive summary of a document: overview, key stats,
    chapter breakdown, most important concepts, and exam-relevant highlights.

    No LLM call — built entirely from indexed metadata.
    """
    _require_subject(subject, db)
    subject = subject.strip().upper()
    doc = _require_document(doc_id, subject, db)

    slides = db.query(Slide).filter(Slide.doc_id == doc.id).all()

    # Slide type distribution
    type_dist: dict[str, int] = {}
    for sl in slides:
        t = sl.slide_type or "other"
        type_dist[t] = type_dist.get(t, 0) + 1

    # Exam signals
    exam_slides = [sl for sl in slides if sl.exam_signal]

    # Top concepts by frequency
    concept_freq: dict[str, int] = {}
    for sl in slides:
        for c in (sl.concepts or "").split(","):
            c = c.strip().lower()
            if c:
                concept_freq[c] = concept_freq.get(c, 0) + 1
    top_concepts = sorted(concept_freq.items(), key=lambda x: x[1], reverse=True)[:20]

    # PYQ coverage for this doc
    doc_slide_ids = [sl.id for sl in slides]
    pyq_matches = (
        db.query(PYQMatch)
        .filter(PYQMatch.slide_id.in_(doc_slide_ids))
        .count()
    ) if doc_slide_ids else 0
    unique_questions = (
        db.query(func.count(func.distinct(PYQMatch.pyq_id)))
        .filter(PYQMatch.slide_id.in_(doc_slide_ids))
        .scalar()
    ) if doc_slide_ids else 0

    # Numerical problems in this doc
    numerical_slides = [
        {"slide_id": sl.id, "page_number": sl.page_number, "summary": sl.summary or ""}
        for sl in slides
        if sl.slide_type == "numerical_example"
    ]

    # Chapters
    chapters = []
    if doc.chapters_json:
        try:
            chapters = json.loads(doc.chapters_json)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "subject": subject,
        "doc_id": doc.id,
        "filename": doc.filename,
        "overview": doc.summary or "",
        "core_topics": doc.core_topics or "",
        "total_slides": len(slides),
        "chapters": chapters,
        "slide_type_distribution": type_dist,
        "exam_signal_count": len(exam_slides),
        "exam_signal_slides": [
            {"slide_id": s.id, "page_number": s.page_number, "summary": s.summary or ""}
            for s in exam_slides
        ],
        "top_concepts": [{"concept": c, "frequency": f} for c, f in top_concepts],
        "pyq_coverage": {
            "total_matches": pyq_matches,
            "unique_questions_matched": unique_questions,
        },
        "numerical_problems": numerical_slides,
        "numerical_count": len(numerical_slides),
    }
