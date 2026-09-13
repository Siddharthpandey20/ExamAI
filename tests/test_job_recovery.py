"""
Tests for stale-job detection.

A worker killed mid-task leaves its job row non-terminal forever. Nothing
transitions it, so the API keeps reporting it as running and computes its
duration against now(), producing a figure that grows without bound.

Detection needs no schema change: Job.updated_at is already written on every
phase transition and progress tick.

Detection is read-only by design. Marking stale jobs failed or re-enqueuing
them rewrites historical rows, which is an operator decision, not something a
status query should do as a side effect — so no such function exists here.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from indexing.models import Base
from jobs.models import Job, JobStatus, JobType
from jobs.recovery import (
    STALE_AFTER_SECONDS, find_stale_jobs, is_job_stale, job_idle_seconds,
)

NOW = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'jobs.db'}")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _job(session, status, idle_minutes, job_type=JobType.PYQ.value):
    """A job whose last update was *idle_minutes* ago. Stored naive, as SQLite does."""
    stamp = (NOW - timedelta(minutes=idle_minutes)).replace(tzinfo=None)
    j = Job(filename="paper.pdf", filepath="/tmp/paper.pdf", job_type=job_type,
            status=status, subject="CN", created_at=stamp, updated_at=stamp)
    session.add(j)
    session.commit()
    return j


# ── Terminal jobs are never stale ────────────────────────────────────────

@pytest.mark.parametrize("status", [JobStatus.COMPLETED.value, JobStatus.FAILED.value])
def test_terminal_jobs_are_never_stale(session, status):
    j = _job(session, status, idle_minutes=100_000)
    assert is_job_stale(j, now=NOW) is False


# ── Non-terminal jobs ────────────────────────────────────────────────────

@pytest.mark.parametrize("status", [JobStatus.PENDING.value, JobStatus.PROCESSING.value])
def test_recent_non_terminal_job_is_not_stale(session, status):
    j = _job(session, status, idle_minutes=5)
    assert is_job_stale(j, now=NOW) is False


@pytest.mark.parametrize("status", [JobStatus.PENDING.value, JobStatus.PROCESSING.value])
def test_abandoned_non_terminal_job_is_stale(session, status):
    j = _job(session, status, idle_minutes=60 * 24 * 30)   # a month
    assert is_job_stale(j, now=NOW) is True


def test_a_long_but_live_phase_is_not_stale(session):
    """Structuring reports progress once and can then run for many minutes;
    the threshold must not mistake slowness for abandonment."""
    j = _job(session, JobStatus.PROCESSING.value, idle_minutes=20)
    assert is_job_stale(j, now=NOW) is False


def test_threshold_boundary(session):
    limit_min = STALE_AFTER_SECONDS / 60
    just_under = _job(session, JobStatus.PROCESSING.value, idle_minutes=limit_min - 1)
    assert is_job_stale(just_under, now=NOW) is False
    just_over = _job(session, JobStatus.PROCESSING.value, idle_minutes=limit_min + 1)
    assert is_job_stale(just_over, now=NOW) is True


def test_threshold_is_overridable(session):
    j = _job(session, JobStatus.PROCESSING.value, idle_minutes=10)
    assert is_job_stale(j, now=NOW, threshold_seconds=60 * 60) is False
    assert is_job_stale(j, now=NOW, threshold_seconds=60) is True


# ── Timestamp handling ───────────────────────────────────────────────────

def test_naive_timestamps_are_treated_as_utc(session):
    """SQLite strips tzinfo; a naive value must not be read as local time."""
    j = _job(session, JobStatus.PROCESSING.value, idle_minutes=30)
    assert j.updated_at.tzinfo is None
    idle = job_idle_seconds(j, now=NOW)
    assert 29 * 60 < idle < 31 * 60


def test_idle_never_goes_negative(session):
    """A clock skew that puts updated_at in the future must not underflow."""
    future = (NOW + timedelta(hours=1)).replace(tzinfo=None)
    j = Job(filename="f.pdf", filepath="/tmp/f.pdf", job_type=JobType.PYQ.value,
            status=JobStatus.PROCESSING.value, subject="CN",
            created_at=future, updated_at=future)
    session.add(j)
    session.commit()
    assert job_idle_seconds(j, now=NOW) == 0.0
    assert is_job_stale(j, now=NOW) is False


def test_missing_timestamps_are_not_stale():
    """A row written by raw SQL can carry NULL timestamps.

    The ORM cannot produce this — the columns declare defaults that SQLAlchemy
    applies at flush — so the guard is exercised on an unpersisted instance.
    """
    j = Job(filename="f.pdf", filepath="/tmp/f.pdf", job_type=JobType.PYQ.value,
            status=JobStatus.PROCESSING.value, subject="CN")
    j.created_at = None
    j.updated_at = None
    assert job_idle_seconds(j, now=NOW) is None
    assert is_job_stale(j, now=NOW) is False


def test_created_at_is_used_when_never_updated():
    """Falls back to created_at when a job was queued but never picked up."""
    j = Job(filename="f.pdf", filepath="/tmp/f.pdf", job_type=JobType.PYQ.value,
            status=JobStatus.PENDING.value, subject="CN")
    j.created_at = (NOW - timedelta(days=5)).replace(tzinfo=None)
    j.updated_at = None
    assert is_job_stale(j, now=NOW) is True


# ── find_stale_jobs ──────────────────────────────────────────────────────

def test_find_stale_jobs_selects_only_the_abandoned(session):
    _job(session, JobStatus.COMPLETED.value, 100_000)
    _job(session, JobStatus.FAILED.value, 100_000)
    _job(session, JobStatus.PROCESSING.value, 5)
    old1 = _job(session, JobStatus.PROCESSING.value, 60 * 24 * 10)
    old2 = _job(session, JobStatus.PENDING.value, 60 * 24 * 10)

    found = find_stale_jobs(session, now=NOW)
    assert {j.id for j in found} == {old1.id, old2.id}


def test_find_stale_jobs_is_read_only(session):
    """Detection must not rewrite historical rows."""
    j = _job(session, JobStatus.PROCESSING.value, 60 * 24 * 10)
    before = (j.status, j.updated_at, j.error_message, j.current_phase)

    find_stale_jobs(session, now=NOW)
    session.expire_all()

    after = session.query(Job).filter(Job.id == j.id).first()
    assert (after.status, after.updated_at, after.error_message, after.current_phase) == before


def test_no_reaper_is_exposed():
    """Marking jobs failed rewrites user data and must stay an explicit
    operator action, not a side effect of a status query."""
    import jobs.recovery as rec
    exported = {n for n in dir(rec) if not n.startswith("_")}
    for forbidden in ("reap_stale_jobs", "fail_stale_jobs", "requeue_stale_jobs"):
        assert forbidden not in exported


def test_empty_database_is_handled(session):
    assert find_stale_jobs(session, now=NOW) == []
