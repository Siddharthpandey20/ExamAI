"""
mapper.py — PYQ-to-Slide mapper: records matches and updates scores in SQLite.

Dynamic scoring fields (pyq_hit_count, importance_score) live ONLY in SQLite.
ChromaDB stores only static slide metadata for vector search.

For each matched (question, slide) pair:
  1. Insert PYQQuestion record in SQLite
  2. Insert PYQMatch record (pyq_id ↔ slide_id, rrf_score)
  3. Increment Slide.pyq_hit_count
  4. Recompute Slide.importance_score
"""

import logging

from sqlalchemy.orm import Session

from indexing.models import Slide, PYQQuestion, PYQMatch
from pyq.config import WEIGHT_PYQ_FREQUENCY, WEIGHT_SLIDE_EMPHASIS, WEIGHT_CONCEPT_IMPORTANCE
from pyq.schemas import ExtractedQuestion, RRFResult

log = logging.getLogger(__name__)


def _compute_importance_score(slide: Slide, max_pyq_hits: int) -> float:
    """
    Compute importance score for a slide:

      importance = W_pyq * normalized_pyq_freq
                 + W_emphasis * slide_emphasis
                 + W_concept * concept_importance

    Where:
      - normalized_pyq_freq = pyq_hit_count / max_pyq_hits (across all slides)
      - slide_emphasis = 1.0 if exam_signal else 0.0
      - concept_importance = min(num_concepts / 5, 1.0)  (more concepts = more important)
    """
    if max_pyq_hits <= 0:
        pyq_norm = 0.0
    else:
        pyq_norm = slide.pyq_hit_count / max_pyq_hits

    emphasis = 1.0 if slide.exam_signal else 0.0

    num_concepts = len([c for c in (slide.concepts or "").split(",") if c.strip()])
    concept_norm = min(num_concepts / 5.0, 1.0)

    score = (
        WEIGHT_PYQ_FREQUENCY * pyq_norm
        + WEIGHT_SLIDE_EMPHASIS * emphasis
        + WEIGHT_CONCEPT_IMPORTANCE * concept_norm
    )
    return round(score, 4)


def record_matches(
    session: Session,
    question: ExtractedQuestion,
    matches: list[RRFResult],
    source_file: str,
    subject: str = "",
) -> PYQQuestion | None:
    """
    Record a single question and its matched slides in SQLite.

    Parameters
    ----------
    session : Session
        Active SQLAlchemy session.
    question : ExtractedQuestion
        The extracted exam question.
    matches : list[RRFResult]
        Filtered RRF results (top K above threshold).
    source_file : str
        Source PYQ filename for tracking.
    subject : str
        User-assigned subject name.

    Returns
    -------
    PYQQuestion or None
        The inserted question record, or None if no matches.
    """
    if not matches:
        log.info(f"  Q{question.question_number}: No matches — skipping DB insert")
        return None

    # Insert the question
    pyq_q = PYQQuestion(
        question_text=question.question_text,
        source_file=source_file,
        subject=subject,
    )
    session.add(pyq_q)
    session.flush()  # get pyq_q.id

    # Insert match records and increment hit counts
    for match in matches:
        # Insert PYQMatch
        pyq_match = PYQMatch(
            pyq_id=pyq_q.id,
            slide_id=match.slide_id,
            similarity_score=match.rrf_score,
        )
        session.add(pyq_match)

        # Increment slide hit count
        slide = session.query(Slide).filter(Slide.id == match.slide_id).first()
        if slide:
            slide.pyq_hit_count = (slide.pyq_hit_count or 0) + 1

    session.flush()

    log.info(
        f"  Q{question.question_number}: {len(matches)} matches recorded "
        f"(PYQ ID={pyq_q.id})"
    )
    return pyq_q


def recompute_importance_scores(session: Session) -> int:
    """
    Recompute pyq_hit_count AND importance_score for ALL embedded slides.

    pyq_hit_count is derived from the actual pyq_matches table (COUNT of
    matches per slide), making it the single source of truth.  This avoids
    drift caused by failed increments, blanket resets, or cross-subject
    remapping.

    Returns the number of slides updated.
    """
    from sqlalchemy import func

    all_slides = session.query(Slide).filter(Slide.is_embedded == True).all()

    if not all_slides:
        return 0

    # Derive hit counts from the matches table (source of truth)
    hit_counts = dict(
        session.query(PYQMatch.slide_id, func.count(PYQMatch.pyq_id))
        .group_by(PYQMatch.slide_id)
        .all()
    )

    # Apply derived counts to slides
    for slide in all_slides:
        slide.pyq_hit_count = hit_counts.get(slide.id, 0)

    # Find max for normalization (after updating counts)
    max_hits = max((s.pyq_hit_count or 0) for s in all_slides)

    updated = 0
    for slide in all_slides:
        new_score = _compute_importance_score(slide, max_hits)
        if slide.importance_score != new_score:
            slide.importance_score = new_score
            updated += 1

    session.flush()
    log.info(f"[Mapper] Recomputed importance scores: {updated}/{len(all_slides)} slides updated")
    return updated


def is_pyq_already_ingested(session: Session, source_file: str) -> bool:
    """
    Check if a PYQ source file already has questions in SQLite.

    This is the authoritative duplicate check — the JSON tracker is a
    convenience cache, but SQLite is the source of truth.
    """
    count = (
        session.query(PYQQuestion)
        .filter(PYQQuestion.source_file == source_file)
        .count()
    )
    return count > 0
