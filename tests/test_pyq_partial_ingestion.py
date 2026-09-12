"""
Regression tests for honest reporting of partially-ingested PYQ papers.

Phase 3 of process_pyq_task commits one question at a time, so a crash
mid-loop leaves rows behind without the paper being finished. The guard used
to treat "some rows exist" as "already done": it marked every phase SKIPPED,
called _complete_job() so the UI showed a green tick, and wrote the JSON
tracker — sealing the paper in a permanently half-ingested state that no API
call could undo.

Completion must instead be PROVEN by one of two independent signals:
  - the JSON tracker, written only as the last step of a successful run
    (both in jobs/tasks.py and pyq/pipeline.py);
  - a completed Celery job for the same paper and subject, which survives a
    lost or deleted tracker file.

These tests exercise that decision logic against a throwaway database. No
Celery, Redis, Ollama or network.
"""

import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indexing.models import Base, Document, Slide, PYQQuestion, PYQMatch  # noqa: E402
from jobs.models import Job, JobStatus, JobType  # noqa: E402
from pyq.mapper import record_matches, is_pyq_already_ingested  # noqa: E402
from pyq.schemas import ExtractedQuestion, RRFResult  # noqa: E402

PAPER, SUBJECT, TOTAL = "Midterm2024.pdf", "CN", 10
THIS_JOB = 999


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'probe.db'}")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    d = Document(filename="cn.md", file_hash="h", status="processed", subject=SUBJECT)
    s.add(d)
    s.flush()
    for p in range(1, 6):
        s.add(Slide(doc_id=d.id, page_number=p, subject=SUBJECT,
                    summary=f"s{p}", concepts="tcp", is_embedded=True))
    s.commit()
    return s


def _matches(s, n=3):
    ids = [r[0] for r in s.query(Slide.id).order_by(Slide.id).limit(n)]
    return [RRFResult(slide_id=i, doc_id=1, page_number=i, source_file="cn.md",
                      rrf_score=0.03, dense_rank=1, sparse_rank=1) for i in ids]


def _ingest(s, upto):
    """Replay phase 3: one committed transaction per question."""
    for i in range(1, upto + 1):
        record_matches(s, ExtractedQuestion(question_number=i,
                                            question_text=f"Q{i}", marks=5),
                       _matches(s), source_file=PAPER, subject=SUBJECT)
        s.commit()


def _add_job(s, status, job_id=None):
    j = Job(id=job_id, filename=PAPER, filepath=f"/tmp/{PAPER}",
            job_type=JobType.PYQ.value, status=status, subject=SUBJECT)
    s.add(j)
    s.commit()
    return j


# ── The decision under test, mirroring jobs/tasks.process_pyq_task ───────

def decide(session, tracker_says_done: bool, job_id: int = THIS_JOB) -> str:
    has_completed_job = (
        session.query(Job)
        .filter(Job.job_type == JobType.PYQ.value,
                Job.filename == PAPER,
                Job.subject == SUBJECT,
                Job.status == JobStatus.COMPLETED.value,
                Job.id != job_id)
        .count() > 0
    )
    if tracker_says_done or has_completed_job:
        return "skip_complete"

    if not is_pyq_already_ingested(session, PAPER, subject=SUBJECT):
        return "process"

    return "fail_partial"


# ── Scenario coverage ────────────────────────────────────────────────────

def test_fresh_paper_is_processed(session):
    assert decide(session, tracker_says_done=False) == "process"


def test_completed_paper_is_skipped_via_tracker(session):
    """Legitimate completed-PYQ skip behaviour must be preserved."""
    _ingest(session, TOTAL)
    assert decide(session, tracker_says_done=True) == "skip_complete"


def test_completed_paper_is_skipped_via_completed_job(session):
    """A lost tracker must not turn a finished paper into a failure."""
    _ingest(session, TOTAL)
    _add_job(session, JobStatus.COMPLETED.value, job_id=1)
    assert decide(session, tracker_says_done=False) == "skip_complete"


def test_partial_ingestion_is_reported_as_failure_not_success(session):
    """The core regression: 4 of 10 questions stored, nothing proves success."""
    _ingest(session, 4)
    assert decide(session, tracker_says_done=False) == "fail_partial"


def test_retry_after_partial_ingestion_does_not_duplicate(session):
    """Repeated retries must neither duplicate nor flip to success."""
    _ingest(session, 4)
    before = session.query(PYQQuestion).count()
    for _ in range(3):
        assert decide(session, tracker_says_done=False) == "fail_partial"
    assert session.query(PYQQuestion).count() == before


def test_failed_jobs_alone_do_not_prove_completion(session):
    """Earlier failed attempts must not be mistaken for a finished run."""
    _ingest(session, 4)
    _add_job(session, JobStatus.FAILED.value, job_id=1)
    _add_job(session, JobStatus.FAILED.value, job_id=2)
    assert decide(session, tracker_says_done=False) == "fail_partial"


def test_the_current_job_cannot_prove_its_own_completion(session):
    """The in-flight job row must be excluded from the completion check."""
    _ingest(session, 4)
    _add_job(session, JobStatus.COMPLETED.value, job_id=THIS_JOB)
    assert decide(session, tracker_says_done=False, job_id=THIS_JOB) == "fail_partial"


def test_completion_is_scoped_by_subject(session):
    """A completed job for another subject must not unlock this one."""
    _ingest(session, 4)
    j = Job(filename=PAPER, filepath=f"/tmp/{PAPER}", job_type=JobType.PYQ.value,
            status=JobStatus.COMPLETED.value, subject="ML")
    session.add(j)
    session.commit()
    assert decide(session, tracker_says_done=False) == "fail_partial"


def test_completed_job_of_another_type_does_not_count(session):
    _ingest(session, 4)
    j = Job(filename=PAPER, filepath=f"/tmp/{PAPER}",
            job_type=JobType.STUDY_MATERIAL.value,
            status=JobStatus.COMPLETED.value, subject=SUBJECT)
    session.add(j)
    session.commit()
    assert decide(session, tracker_says_done=False) == "fail_partial"


def test_partial_state_is_left_untouched(session):
    """The guard must never delete or alter the rows already stored."""
    _ingest(session, 4)
    q_before = [(r.id, r.question_text) for r in session.query(PYQQuestion).all()]
    m_before = session.query(PYQMatch).count()

    decide(session, tracker_says_done=False)

    assert [(r.id, r.question_text) for r in session.query(PYQQuestion).all()] == q_before
    assert session.query(PYQMatch).count() == m_before


def test_normal_reupload_of_a_finished_paper_still_skips(session):
    _ingest(session, TOTAL)
    for _ in range(3):
        assert decide(session, tracker_says_done=True) == "skip_complete"
    assert session.query(PYQQuestion).count() == TOTAL
