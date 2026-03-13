"""
engine/tools.py — Core query functions for search and exam intelligence.

These functions are shared by both Fast Mode and Reasoning Mode.
Each function takes a SQLAlchemy session (+ other deps) and returns plain dicts
so they can be serialised to JSON for the LLM or returned directly to the API.
"""

import json
import logging
import re

from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from rank_bm25 import BM25Okapi

from indexing.models import Document, Slide, PYQQuestion, PYQMatch
from indexing.db_chroma import ChromaStore
from indexing.embedder import Embedder
from engine.config import (
    SEARCH_TOP_K,
    CONTEXT_MAX_SLIDES,
    MIN_SLIDE_TEXT_LEN,
    HIGH_PRIORITY_THRESHOLD,
    MEDIUM_PRIORITY_THRESHOLD,
    RRF_K,
)

log = logging.getLogger(__name__)


# ── Slide helpers ────────────────────────────────────────────────────────

def is_substantive(slide: Slide) -> bool:
    """Return True if the slide has meaningful content (not just a heading)."""
    text_len = len((slide.raw_text or "").strip())
    summary_len = len((slide.summary or "").strip())
    if text_len < MIN_SLIDE_TEXT_LEN and summary_len < 20:
        return False
    if slide.slide_type in ("other",) and summary_len < 15:
        return False
    return True


def slide_to_dict(slide: Slide, doc: Document | None = None, include_raw: bool = False) -> dict:
    """Convert a Slide ORM object to a plain dict safe for JSON.

    By default raw_text is excluded — callers already have the AI-processed
    summary and concepts from the structuring phase.  Pass include_raw=True
    for the rare case where you need the original text (e.g. get_slide_detail).
    """
    d = {
        "slide_id": slide.id,
        "doc_id": slide.doc_id,
        "page_number": slide.page_number,
        "filename": doc.original_filename if doc else "",
        "slide_type": slide.slide_type or "other",
        "exam_signal": bool(slide.exam_signal),
        "summary": slide.summary or "",
        "concepts": slide.concepts or "",
        "chapter": slide.chapter or "",
        "pyq_hit_count": slide.pyq_hit_count or 0,
        "importance_score": slide.importance_score or 0.0,
    }
    if include_raw:
        d["raw_text"] = (slide.raw_text or "")[:1500]
    return d


def _doc_for_slide(slide: Slide, session: Session) -> Document | None:
    return session.query(Document).filter(Document.id == slide.doc_id).first()


# ── Subject-filtered hybrid search ──────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _parse_chroma_id(cid: str) -> tuple[int, int]:
    """'doc3_page7' → (3, 7)"""
    parts = cid.replace("doc", "").replace("page", "").split("_")
    return int(parts[0]), int(parts[1])


def run_hybrid_search(
    query: str,
    subject: str,
    session: Session,
    embedder: Embedder,
    chroma: ChromaStore,
    top_k: int = SEARCH_TOP_K,
) -> list[dict]:
    """
    Subject-filtered hybrid search: dense (ChromaDB) + sparse (BM25) + RRF.

    Returns a list of enriched slide dicts sorted by descending RRF score.
    Non-substantive slides (heading-only, index pages) are filtered out.
    """
    fetch_n = top_k * 3  # over-fetch to compensate for filtering

    # ── Dense search (ChromaDB — subject-filtered via metadata) ──────
    query_vec = embedder.embed_query(query)
    try:
        dense_raw = chroma.query(
            query_embedding=query_vec,
            n_results=fetch_n,
            where={"subject": subject},
        )
    except Exception:
        # Fall back to unfiltered if subject metadata missing
        dense_raw = chroma.query(query_embedding=query_vec, n_results=fetch_n)

    dense_ranked: list[dict] = []
    if dense_raw and dense_raw.get("ids") and dense_raw["ids"][0]:
        for rank, (cid, meta) in enumerate(
            zip(dense_raw["ids"][0], dense_raw["metadatas"][0]), start=1,
        ):
            doc_id, page_num = _parse_chroma_id(cid)
            dense_ranked.append({
                "key": f"{doc_id}_{page_num}",
                "doc_id": doc_id,
                "page_number": page_num,
                "source_file": meta.get("source_file", ""),
                "rank": rank,
            })

    # ── Sparse search (subject-specific BM25 built inline) ──────────
    subject_slides = (
        session.query(Slide)
        .filter(Slide.subject == subject, Slide.is_embedded == True)
        .all()
    )

    corpus: list[list[str]] = []
    corpus_slides: list[Slide] = []
    for sl in subject_slides:
        tokens = _tokenize(
            f"{sl.summary or ''} {sl.concepts or ''} {sl.raw_text or ''}"
        )
        if tokens:
            corpus.append(tokens)
            corpus_slides.append(sl)

    sparse_ranked: list[dict] = []
    if corpus:
        bm25 = BM25Okapi(corpus)
        q_tokens = _tokenize(query)
        if q_tokens:
            scores = bm25.get_scores(q_tokens)
            scored = sorted(
                ((i, scores[i]) for i in range(len(scores)) if scores[i] > 0),
                key=lambda x: x[1],
                reverse=True,
            )
            for rank, (idx, _score) in enumerate(scored[:fetch_n], start=1):
                sl = corpus_slides[idx]
                sparse_ranked.append({
                    "key": f"{sl.doc_id}_{sl.page_number}",
                    "doc_id": sl.doc_id,
                    "page_number": sl.page_number,
                    "source_file": "",
                    "rank": rank,
                })

    # ── RRF fusion ───────────────────────────────────────────────────
    dense_map = {r["key"]: r["rank"] for r in dense_ranked}
    sparse_map = {r["key"]: r["rank"] for r in sparse_ranked}
    all_keys = set(dense_map) | set(sparse_map)

    fused: list[dict] = []
    for key in all_keys:
        score = 0.0
        d_rank = dense_map.get(key)
        s_rank = sparse_map.get(key)
        if d_rank is not None:
            score += 1.0 / (RRF_K + d_rank)
        if s_rank is not None:
            score += 1.0 / (RRF_K + s_rank)

        doc_id, page_num = (int(x) for x in key.split("_"))
        slide = (
            session.query(Slide)
            .filter(Slide.doc_id == doc_id, Slide.page_number == page_num)
            .first()
        )
        if not slide or not is_substantive(slide):
            continue

        doc = _doc_for_slide(slide, session)
        d = slide_to_dict(slide, doc)
        d["rrf_score"] = round(score, 6)
        d["dense_rank"] = d_rank
        d["sparse_rank"] = s_rank
        fused.append(d)

    fused.sort(key=lambda x: x["rrf_score"], reverse=True)
    return fused[:top_k]


# ── Filtered queries ─────────────────────────────────────────────────────

def search_by_type(
    subject: str, slide_type: str, session: Session, limit: int = 50,
) -> list[dict]:
    """Get slides of a specific type sorted by importance."""
    slides = (
        session.query(Slide)
        .filter(Slide.subject == subject, Slide.slide_type == slide_type)
        .order_by(desc(Slide.importance_score))
        .limit(limit)
        .all()
    )
    return [
        slide_to_dict(sl, _doc_for_slide(sl, session))
        for sl in slides if is_substantive(sl)
    ]


def search_by_concept(
    subject: str, keyword: str, session: Session, limit: int = 30,
) -> list[dict]:
    """Search slides whose concepts contain *keyword* (case-insensitive)."""
    pattern = f"%{keyword.lower()}%"
    slides = (
        session.query(Slide)
        .filter(Slide.subject == subject, func.lower(Slide.concepts).like(pattern))
        .order_by(desc(Slide.importance_score))
        .limit(limit)
        .all()
    )
    return [slide_to_dict(sl, _doc_for_slide(sl, session)) for sl in slides]


def get_slide_detail(slide_id: int, session: Session) -> dict | None:
    """Full slide details (un-trimmed raw_text)."""
    slide = session.query(Slide).filter(Slide.id == slide_id).first()
    if not slide:
        return None
    doc = _doc_for_slide(slide, session)
    d = slide_to_dict(slide, doc, include_raw=True)
    d["raw_text"] = slide.raw_text or ""  # full — override the trimmed version
    return d


# ── Chapter / document level ─────────────────────────────────────────────

def get_chapter_structure(subject: str, session: Session) -> list[dict]:
    """Return chapter info across all processed docs in a subject."""
    docs = (
        session.query(Document)
        .filter(Document.subject == subject, Document.status == "processed")
        .all()
    )
    chapters: list[dict] = []
    for doc in docs:
        if not doc.chapters_json:
            continue
        try:
            for ch in json.loads(doc.chapters_json):
                ch["filename"] = doc.filename
                ch["doc_id"] = doc.id
                chapters.append(ch)
        except (json.JSONDecodeError, TypeError):
            continue
    return chapters


def get_subject_overview(subject: str, session: Session) -> dict:
    """Comprehensive stats for a subject."""
    docs = session.query(Document).filter(Document.subject == subject).all()
    total_slides = (
        session.query(func.count(Slide.id)).filter(Slide.subject == subject).scalar()
    )
    embedded = (
        session.query(func.count(Slide.id))
        .filter(Slide.subject == subject, Slide.is_embedded == True)
        .scalar()
    )
    pyq_count = (
        session.query(func.count(PYQQuestion.id))
        .filter(PYQQuestion.subject == subject)
        .scalar()
    )
    avg_imp = (
        session.query(func.avg(Slide.importance_score))
        .filter(Slide.subject == subject, Slide.is_embedded == True)
        .scalar()
    ) or 0.0
    high_count = (
        session.query(func.count(Slide.id))
        .filter(Slide.subject == subject, Slide.importance_score >= HIGH_PRIORITY_THRESHOLD)
        .scalar()
    )
    return {
        "subject": subject,
        "documents": len(docs),
        "total_slides": total_slides,
        "embedded_slides": embedded,
        "pyq_questions": pyq_count,
        "avg_importance": round(avg_imp, 3),
        "high_priority_slides": high_count,
        "document_list": [
            {
                "id": d.id,
                "filename": d.filename,
                "core_topics": d.core_topics or "",
                "total_slides": d.total_slides or 0,
            }
            for d in docs
        ],
    }


# ── Priority tiers ──────────────────────────────────────────────────────

def get_priority_slides(subject: str, session: Session) -> dict:
    """
    Classify embedded slides into High / Medium / Low priority.

    Thresholds:
      High   >= 0.4
      Medium >= 0.15
      Low    <  0.15
    """
    slides = (
        session.query(Slide)
        .filter(Slide.subject == subject, Slide.is_embedded == True)
        .order_by(desc(Slide.importance_score))
        .all()
    )
    high, medium, low = [], [], []
    for sl in slides:
        if not is_substantive(sl):
            continue
        d = slide_to_dict(sl, _doc_for_slide(sl, session))
        if sl.importance_score >= HIGH_PRIORITY_THRESHOLD:
            high.append(d)
        elif sl.importance_score >= MEDIUM_PRIORITY_THRESHOLD:
            medium.append(d)
        else:
            low.append(d)
    return {"high": high, "medium": medium, "low": low}


# ── PYQ report ───────────────────────────────────────────────────────────

def get_pyq_report(subject: str, session: Session) -> dict:
    """PYQ questions → matched slides with similarity scores."""
    questions = (
        session.query(PYQQuestion).filter(PYQQuestion.subject == subject).all()
    )
    report: list[dict] = []
    for q in questions:
        matches = (
            session.query(PYQMatch, Slide)
            .join(Slide, PYQMatch.slide_id == Slide.id)
            .filter(PYQMatch.pyq_id == q.id)
            .order_by(desc(PYQMatch.similarity_score))
            .all()
        )
        matched_slides = []
        for m, sl in matches:
            doc = _doc_for_slide(sl, session)
            matched_slides.append({
                "slide_id": sl.id,
                "page_number": sl.page_number,
                "filename": doc.filename if doc else "",
                "summary": sl.summary or "",
                "chapter": sl.chapter or "",
                "concepts": sl.concepts or "",
                "similarity_score": round(m.similarity_score, 4),
            })
        report.append({
            "question_id": q.id,
            "question_text": q.question_text,
            "source_file": q.source_file or "",
            "matched_slides": matched_slides,
            "match_count": len(matched_slides),
        })
    return {
        "subject": subject,
        "total_questions": len(questions),
        "questions": report,
    }


# ── Weak spots ───────────────────────────────────────────────────────────

def get_weak_spots(subject: str, session: Session) -> list[dict]:
    """
    Chapters with high PYQ frequency but potentially sparse slide coverage.
    Useful for identifying topics to study harder.
    """
    questions = (
        session.query(PYQQuestion).filter(PYQQuestion.subject == subject).all()
    )

    chapter_pyq_hits: dict[str, int] = {}
    chapter_matched_ids: dict[str, set[int]] = {}

    for q in questions:
        matches = (
            session.query(PYQMatch, Slide)
            .join(Slide, PYQMatch.slide_id == Slide.id)
            .filter(PYQMatch.pyq_id == q.id)
            .all()
        )
        for _m, sl in matches:
            if sl is None:
                continue
            ch = sl.chapter or "Uncategorized"
            chapter_pyq_hits[ch] = chapter_pyq_hits.get(ch, 0) + 1
            chapter_matched_ids.setdefault(ch, set()).add(sl.id)

    # Total slides per chapter
    all_slides = session.query(Slide).filter(Slide.subject == subject).all()
    chapter_total: dict[str, int] = {}
    for sl in all_slides:
        ch = sl.chapter or "Uncategorized"
        chapter_total[ch] = chapter_total.get(ch, 0) + 1

    weak: list[dict] = []
    for ch, hits in sorted(chapter_pyq_hits.items(), key=lambda x: x[1], reverse=True):
        total = chapter_total.get(ch, 1)
        matched = len(chapter_matched_ids.get(ch, set()))
        weak.append({
            "chapter": ch,
            "pyq_hits": hits,
            "matched_slides": matched,
            "total_slides": total,
            "coverage_ratio": round(matched / total, 2) if total > 0 else 0,
            "priority": "high" if hits >= 3 else "medium" if hits >= 1 else "low",
        })
    return weak
