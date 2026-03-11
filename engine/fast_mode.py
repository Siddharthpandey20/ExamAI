"""
engine/fast_mode.py — Fast mode: hybrid search → context build → LLM → response.

Uses engine.llm.ModelPool for multi-model round-robin with fallback.
Uses engine.cache.smart_cache_check for two-level caching (exact + fuzzy).
Large contexts are chunked and distributed across models in parallel.
"""

import logging

from agents import  custom_span
from engine import get_embedder, get_chroma
from engine.config import CONTEXT_MAX_SLIDES, MAX_CONTEXT_CHARS
from engine.llm import pool, chunk_text
from engine.cache import smart_cache_check, store_cache
from engine.tools import (
    run_hybrid_search,
    get_priority_slides,
    get_subject_overview,
    get_chapter_structure,
)
from indexing.database import SessionFactory

log = logging.getLogger(__name__)


# ── LLM helper ──────────────────────────────────────────────────────────

async def _call_llm(system: str, user: str) -> tuple[str, str]:
    """
    Smart LLM call: if user context is large → chunk + parallel across models.
    Returns (response_text, model_used).
    """
    chunks = chunk_text(user, max_chars=MAX_CONTEXT_CHARS)
    if len(chunks) <= 1:
        return await pool.complete(system, user)
    return await pool.complete_chunked(system, chunks, merge_system=system)


# ── Slide context builder ───────────────────────────────────────────────

def _build_context(slides: list[dict]) -> str:
    """Format slide dicts into readable context for the LLM.

    Uses the AI-processed metadata (summary, concepts, type) from the
    structuring phase instead of raw OCR text — more concise and higher quality.
    """
    parts: list[str] = []
    for i, s in enumerate(slides, 1):
        tier = (
            "HIGH" if s["importance_score"] >= 0.4
            else "MEDIUM" if s["importance_score"] >= 0.15
            else "LOW"
        )
        parts.append(
            f"[Slide {i}] Page {s['page_number']} of {s['filename']}\n"
            f"  Chapter: {s['chapter']} | Type: {s['slide_type']} | "
            f"Priority: {tier} | PYQ Hits: {s['pyq_hit_count']} | "
            f"Exam Signal: {'Yes' if s['exam_signal'] else 'No'}\n"
            f"  Concepts: {s['concepts']}\n"
            f"  Summary: {s['summary']}\n"
        )
    return "\n".join(parts)


# ═════════════════════════════════════════════════════════════════════════
#  SEARCH
# ═════════════════════════════════════════════════════════════════════════

_SEARCH_SYSTEM = """\
You are an exam study assistant for a university student. You have access to \
their specific lecture slides, indexed by importance and exam relevance.

RULES:
- Always reference specific slides: "Page X of filename"
- Never say "Based on the data provided" or "According to the slides shared"
- Speak with authority as if you studied the material yourself
- If a concept spans multiple slides, mention all of them
- Highlight exam-relevant details (PYQ hits, exam signals)
- If slides contain numerical examples, point them out
- Be concise but thorough
"""


async def fast_search(query: str, subject: str, force: bool = False) -> dict:
    """Hybrid search → LLM-formatted answer + slide references."""
    with custom_span("fast_search"):
        # ── Two-level cache (exact → fuzzy) ──────────────────────────
        cached, query = await smart_cache_check(subject, "search", query, force)
        if cached:
            return cached

        embedder = get_embedder()
        chroma = get_chroma()

        session = SessionFactory()
        try:
            slides = run_hybrid_search(
                query, subject, session, embedder, chroma,
                top_k=CONTEXT_MAX_SLIDES,
            )

            if not slides:
                return {
                    "answer": (
                        f"No relevant slides found for '{query}' in {subject}. "
                        "Make sure the material has been uploaded and fully processed."
                    ),
                    "slides": [],
                    "mode": "fast",
                }

            context = _build_context(slides)
            user_msg = (
                f"Subject: {subject}\nStudent's question: {query}\n\n"
                f"Relevant slides:\n{context}"
            )
            answer, model_used = await _call_llm(_SEARCH_SYSTEM, user_msg)

            result = {
                "answer": answer,
                "slides": [
                    {
                        "slide_id": s["slide_id"],
                        "page_number": s["page_number"],
                        "filename": s["filename"],
                        "chapter": s["chapter"],
                        "slide_type": s["slide_type"],
                        "importance_score": s["importance_score"],
                        "pyq_hit_count": s["pyq_hit_count"],
                        "rrf_score": s.get("rrf_score", 0),
                    }
                    for s in slides
                ],
                "mode": "fast",
                "model_used": model_used,
            }
            store_cache(subject, "search", query, result, model_used)
            return result
        finally:
            session.close()


# ═════════════════════════════════════════════════════════════════════════
#  TOPIC COVERAGE
# ═════════════════════════════════════════════════════════════════════════

_COVERAGE_SYSTEM = """\
You are a study material coverage analyser. A student wants to know whether a \
topic is covered in their slides.

RULES:
- Give a clear YES / NO / PARTIALLY verdict first
- List exact slide locations: "Page X of filename"
- If partially covered, say what IS covered and what is missing
- If not covered, suggest the closest related topic from the slides
- Never say "based on the data" — speak directly
"""


async def fast_coverage(topic: str, subject: str, force: bool = False) -> dict:
    """Check whether *topic* is covered in the student's slides."""
    with custom_span("fast_coverage"):
        cached, topic = await smart_cache_check(subject, "coverage", topic, force)
        if cached:
            return cached

        embedder = get_embedder()
        chroma = get_chroma()

        session = SessionFactory()
        try:
            slides = run_hybrid_search(
                topic, subject, session, embedder, chroma, top_k=8,
            )

            if not slides:
                return {
                    "covered": False,
                    "confidence": "none",
                    "answer": (
                        f"'{topic}' does not appear to be covered in your "
                        f"{subject} material. No matching slides found."
                    ),
                    "slides": [],
                }

            top_score = slides[0].get("rrf_score", 0)
            if top_score > 0.025:
                confidence = "high"
            elif top_score > 0.015:
                confidence = "medium"
            else:
                confidence = "low"

            context = _build_context(slides[:6])
            user_msg = (
                f"Subject: {subject}\n"
                f"Topic to check: {topic}\n"
                f"Match confidence: {confidence} (top RRF score {top_score:.4f})\n\n"
                f"Closest matching slides:\n{context}"
            )
            answer, model_used = await _call_llm(_COVERAGE_SYSTEM, user_msg)

            result = {
                "covered": confidence in ("high", "medium"),
                "confidence": confidence,
                "answer": answer,
                "slides": [
                    {
                        "slide_id": s["slide_id"],
                        "page_number": s["page_number"],
                        "filename": s["filename"],
                        "chapter": s["chapter"],
                        "rrf_score": s.get("rrf_score", 0),
                    }
                    for s in slides[:6]
                ],
                "model_used": model_used,
            }
            store_cache(subject, "coverage", topic, result, model_used)
            return result
        finally:
            session.close()


# ═════════════════════════════════════════════════════════════════════════
#  STUDY PLAN
# ═════════════════════════════════════════════════════════════════════════

_STUDY_PLAN_SYSTEM = """\
You are an exam study planner. Generate a structured study plan for a student \
based on their slide priorities and PYQ data.

RULES:
- Organise by priority tiers: HIGH → MEDIUM → LOW
- For each topic / chapter list:
  • Specific slides (Page X of filename)
  • Why it is important (PYQ frequency, exam signals)
  • Key concepts to focus on
- Put numerical problems in a separate "Practice Problems" section
- Be specific — no vague advice
- Start with the most exam-critical topics
"""


async def fast_study_plan(subject: str, force: bool = False) -> dict:
    """Priority-ranked study plan built from DB data."""
    with custom_span("fast_study_plan"):
        cache_q = f"study-plan:{subject}"
        cached, _ = await smart_cache_check(subject, "study-plan", cache_q, force)
        
        if cached:
            return cached

        session = SessionFactory()
        try:
            tiers = get_priority_slides(subject, session)
            overview = get_subject_overview(subject, session)
            chapters = get_chapter_structure(subject, session)

            # Assemble a compact context string
            lines: list[str] = [
                f"Subject: {subject}",
                f"Total slides: {overview['total_slides']}",
                f"PYQ questions mapped: {overview['pyq_questions']}",
            ]
            if chapters:
                lines.append("\nChapter structure:")
                for ch in chapters:
                    lines.append(f"  - {ch.get('name', '?')} ({ch.get('filename', '')})")

            for tier_name, slides in [
                ("HIGH PRIORITY", tiers["high"]),
                ("MEDIUM PRIORITY", tiers["medium"]),
                ("LOW PRIORITY", tiers["low"]),
            ]:
                lines.append(f"\n=== {tier_name} ({len(slides)} slides) ===")
                for s in slides[:15]:
                    lines.append(
                        f"Page {s['page_number']} of {s['filename']} | "
                        f"{s['chapter']} | Type: {s['slide_type']} | "
                        f"PYQ Hits: {s['pyq_hit_count']} | "
                        f"Score: {s['importance_score']:.2f}\n"
                        f"  Concepts: {s['concepts']}\n"
                        f"  Summary: {s['summary'][:200]}"
                    )

            answer, model_used = await _call_llm(
                _STUDY_PLAN_SYSTEM, "\n".join(lines),
            )

            result = {
                "plan": answer,
                "stats": {
                    "high_priority": len(tiers["high"]),
                    "medium_priority": len(tiers["medium"]),
                    "low_priority": len(tiers["low"]),
                    "total_slides": overview["total_slides"],
                    "pyq_questions": overview["pyq_questions"],
                },
                "mode": "fast",
                "model_used": model_used,
            }
            store_cache(subject, "study-plan", cache_q, result, model_used)
            return result
        finally:
            session.close()


# ═════════════════════════════════════════════════════════════════════════
#  LAST-DAY REVISION
# ═════════════════════════════════════════════════════════════════════════

_REVISION_SYSTEM = """\
You are an exam revision optimiser. A student has limited time before their \
exam. Create a concrete, time-boxed study schedule.

RULES:
- Allocate time proportional to topic importance
- HIGH priority topics get the most time
- Include specific slide references (Page X of filename)
- Add a "Quick Formulas / Definitions Review" block (5-10 min)
- Add a "Practice Problems" block if numerical slides exist
- Leave a 10 % buffer for ad-hoc review
- Format as a numbered timeline with minute allocations
- Be realistic — don't try to cover everything if time is short
"""


async def fast_revision(subject: str, hours: float, force: bool = False) -> dict:
    """Time-constrained revision schedule."""
    with custom_span("fast_revision"):
        cache_q = f"revision:{subject}:{hours}"
        cached, _ = await smart_cache_check(subject, "revision", cache_q, force)
        if cached:
            return cached

        total_min = int(hours * 60)

        session = SessionFactory()
        try:
            tiers = get_priority_slides(subject, session)
            overview = get_subject_overview(subject, session)

            numericals = [
                s for tier in tiers.values() for s in tier
                if s["slide_type"] == "numerical_example"
            ]

            lines: list[str] = [
                f"Subject: {subject}",
                f"Time available: {hours} hours ({total_min} minutes)",
                f"Total slides: {overview['total_slides']}",
                f"PYQ questions mapped: {overview['pyq_questions']}",
            ]

            lines.append(f"\n=== HIGH PRIORITY ({len(tiers['high'])} slides) ===")
            for s in tiers["high"][:15]:
                lines.append(
                    f"Page {s['page_number']} of {s['filename']} | {s['chapter']} | "
                    f"Type: {s['slide_type']} | PYQ: {s['pyq_hit_count']} | "
                    f"Score: {s['importance_score']:.2f}\n"
                    f"  Concepts: {s['concepts']} | Summary: {s['summary'][:150]}"
                )

            lines.append(f"\n=== MEDIUM PRIORITY ({len(tiers['medium'])} slides) ===")
            for s in tiers["medium"][:10]:
                lines.append(
                    f"Page {s['page_number']} of {s['filename']} | {s['chapter']} | "
                    f"Concepts: {s['concepts']}"
                )

            if numericals:
                lines.append(
                    f"\n=== NUMERICAL PROBLEMS ({len(numericals)} slides) ==="
                )
                for s in numericals[:8]:
                    lines.append(
                        f"Page {s['page_number']} of {s['filename']} | "
                        f"{s['chapter']} | {s['concepts']}"
                    )
            answer, model_used = await _call_llm(
                _REVISION_SYSTEM, "\n".join(lines),
            )

            result = {
                "plan": answer,
                "time_hours": hours,
                "time_minutes": total_min,
                "stats": {
                    "high_priority": len(tiers["high"]),
                    "medium_priority": len(tiers["medium"]),
                    "low_priority": len(tiers["low"]),
                    "numerical_problems": len(numericals),
                },
                "mode": "fast",
                "model_used": model_used,
            }
            store_cache(subject, "revision", cache_q, result, model_used)
            return result
        finally:
            session.close()
