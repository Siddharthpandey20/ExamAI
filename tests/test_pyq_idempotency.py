"""
Regression tests for PYQ idempotency.

Two distinct duplication paths are covered:

  1. record_matches() inserted a new PYQQuestion on every call, so the
     re-map path — which re-scores questions that are ALREADY stored —
     duplicated a subject's entire question set each time it ran, and
     orphaned the previous generation by deleting its matches.

  2. process_pyq_task had no duplicate guard, so a re-upload or an
     acks_late retry re-inserted the whole paper.

Duplicated questions inflate pyq_hit_count, which feeds importance_score
and therefore the priority tiers, study plans and revision schedules.

Runs against a throwaway SQLite file. No Celery, no Redis, no network.
"""


import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from indexing.models import Base, Document, Slide, PYQQuestion, PYQMatch
from pyq.mapper import (
    record_matches,
    recompute_importance_scores,
    is_pyq_already_ingested,
)
from pyq.schemas import ExtractedQuestion, RRFResult

SOURCE = "CN.pdf"
SUBJECT = "CN"


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()

    doc = Document(filename="cn.md", file_hash="h1", status="processed", subject=SUBJECT)
    s.add(doc)
    s.flush()
    for page in range(1, 6):
        s.add(Slide(doc_id=doc.id, page_number=page, subject=SUBJECT,
                    summary=f"slide {page}", concepts="tcp, udp",
                    is_embedded=True, exam_signal=(page == 1)))
    s.commit()
    yield s
    s.close()


def _q(n):
    return ExtractedQuestion(question_number=n, question_text=f"Explain concept {n}", marks=5)


def _matches(session, n=3):
    ids = [r[0] for r in session.query(Slide.id).order_by(Slide.id).limit(n)]
    return [RRFResult(slide_id=i, doc_id=1, page_number=i, source_file="cn.md",
                      rrf_score=0.03, dense_rank=1, sparse_rank=1) for i in ids]


def _ingest_paper(session, n_questions=3):
    """Simulate the first ingestion of a paper."""
    for i in range(1, n_questions + 1):
        record_matches(session, _q(i), _matches(session),
                       source_file=SOURCE, subject=SUBJECT)
    recompute_importance_scores(session)
    session.commit()


def _counts(session):
    return (
        session.query(func.count(PYQQuestion.id)).scalar(),
        session.query(func.count()).select_from(PYQMatch).scalar(),
        session.query(func.coalesce(func.sum(Slide.pyq_hit_count), 0)).scalar(),
        round(session.query(func.coalesce(func.sum(Slide.importance_score), 0)).scalar(), 6),
    )


# ── The re-map path must not duplicate questions ─────────────────────────

def _simulate_remap(session):
    """Mirror remap_pyq_task: load questions, clear matches, re-attach."""
    rows = session.query(PYQQuestion).filter(PYQQuestion.subject == SUBJECT).all()
    q_data = [{"id": r.id, "text": r.question_text, "source": r.source_file or ""} for r in rows]
    ids = [d["id"] for d in q_data]

    session.query(PYQMatch).filter(PYQMatch.pyq_id.in_(ids)).delete(synchronize_session="fetch")
    for d in q_data:
        record_matches(
            session,
            ExtractedQuestion(question_number=0, question_text=d["text"], marks=None),
            _matches(session),
            source_file=d["source"],
            subject=SUBJECT,
            existing_pyq_id=d["id"],          # the fix
        )
    recompute_importance_scores(session)
    session.commit()


def test_remap_does_not_duplicate_questions(session):
    _ingest_paper(session)
    before = _counts(session)

    _simulate_remap(session)
    assert _counts(session) == before, "one re-map changed the data"

    for _ in range(4):
        _simulate_remap(session)
    assert _counts(session) == before, "repeated re-maps drifted"


def test_remap_leaves_no_orphaned_questions(session):
    _ingest_paper(session)
    _simulate_remap(session)
    _simulate_remap(session)

    orphans = (
        session.query(func.count(PYQQuestion.id))
        .filter(~session.query(PYQMatch)
                .filter(PYQMatch.pyq_id == PYQQuestion.id).exists())
        .scalar()
    )
    assert orphans == 0


def test_remap_preserves_question_identity(session):
    _ingest_paper(session)
    before = {(r.id, r.question_text, r.source_file, r.subject)
              for r in session.query(PYQQuestion).all()}
    _simulate_remap(session)
    after = {(r.id, r.question_text, r.source_file, r.subject)
             for r in session.query(PYQQuestion).all()}
    assert before == after, "re-map must reuse the stored rows, ids included"


def test_remap_without_existing_id_still_inserts(session):
    """Default behaviour is unchanged for the first-ingestion caller."""
    _ingest_paper(session, n_questions=1)
    n_before = session.query(func.count(PYQQuestion.id)).scalar()
    record_matches(session, _q(99), _matches(session),
                   source_file=SOURCE, subject=SUBJECT)
    session.commit()
    assert session.query(func.count(PYQQuestion.id)).scalar() == n_before + 1


def test_remap_tolerates_a_deleted_question(session):
    _ingest_paper(session)
    result = record_matches(session, _q(1), _matches(session),
                            source_file=SOURCE, subject=SUBJECT,
                            existing_pyq_id=999999)
    assert result is None


def test_hit_counts_stay_consistent_with_matches_table(session):
    _ingest_paper(session)
    for _ in range(3):
        _simulate_remap(session)

    derived = dict(session.query(PYQMatch.slide_id, func.count(PYQMatch.pyq_id))
                   .group_by(PYQMatch.slide_id).all())
    for slide in session.query(Slide).all():
        assert (slide.pyq_hit_count or 0) == derived.get(slide.id, 0)


# ── The upload guard must block re-ingestion ─────────────────────────────

def test_guard_detects_already_ingested_paper(session):
    assert is_pyq_already_ingested(session, SOURCE, subject=SUBJECT) is False
    _ingest_paper(session)
    assert is_pyq_already_ingested(session, SOURCE, subject=SUBJECT) is True


def test_guard_is_scoped_by_subject(session):
    """The same filename under a different subject is NOT a duplicate."""
    _ingest_paper(session)
    assert is_pyq_already_ingested(session, SOURCE, subject="ML") is False
    assert is_pyq_already_ingested(session, SOURCE, subject=SUBJECT) is True


def test_guard_without_subject_keeps_filename_only_behaviour(session):
    """pyq/pipeline.py calls this with no subject and must be unaffected."""
    _ingest_paper(session)
    assert is_pyq_already_ingested(session, SOURCE) is True
    assert is_pyq_already_ingested(session, "other.pdf") is False


def test_reingesting_a_guarded_paper_would_duplicate(session):
    """Documents WHY the guard exists: without it, a re-run doubles the paper."""
    _ingest_paper(session)
    q_before, m_before, _, _ = _counts(session)

    _ingest_paper(session)  # no guard in this helper - simulates the old path
    q_after, m_after, _, _ = _counts(session)

    assert q_after == q_before * 2
    assert m_after == m_before * 2
    # ...which is exactly what is_pyq_already_ingested now prevents upstream.
    assert is_pyq_already_ingested(session, SOURCE, subject=SUBJECT) is True
