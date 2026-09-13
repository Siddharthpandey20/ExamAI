"""
recovery.py — detect jobs that stopped making progress.

A worker that is killed mid-task leaves its job row in `processing` forever:
nothing ever transitions it, so the API keeps reporting it as running and
jobs/status.py keeps computing its duration against `now()`, producing a
figure that grows without bound. The live database currently holds one such
row, idle for months.

Detection needs no schema change. Job.updated_at is already written on every
phase transition and every progress tick, so "no update for a long time"
is a sufficient and cheap signal.

This module only *reports*. It deliberately does not mark stale jobs failed
or re-enqueue them: both rewrite historical rows, which is a decision for the
operator rather than something a status query should do as a side effect.
"""

import os
from datetime import datetime, timedelta, timezone

from jobs.models import Job, JobStatus

# Generous by design. A single phase can legitimately run for many minutes —
# Ollama on CPU takes ~10 minutes for a document-level pass, and structuring
# reports progress only once before Agent 1 starts. This threshold is meant
# to catch abandonment, not slowness.
STALE_AFTER_SECONDS = int(os.environ.get("EXAMAI_JOB_STALE_SECONDS", str(60 * 60)))

_NON_TERMINAL = (JobStatus.PENDING.value, JobStatus.PROCESSING.value)


def _as_utc(dt: datetime | None) -> datetime | None:
    """SQLite stores these naive; treat a naive value as UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def job_idle_seconds(job: Job, now: datetime | None = None) -> float | None:
    """Seconds since this job last changed, or None if it never started."""
    stamp = _as_utc(job.updated_at) or _as_utc(job.created_at)
    if stamp is None:
        return None
    now = now or datetime.now(timezone.utc)
    return max((now - stamp).total_seconds(), 0.0)


def is_job_stale(job: Job, now: datetime | None = None,
                 threshold_seconds: int | None = None) -> bool:
    """True when a non-terminal job has made no progress for too long.

    Completed and failed jobs are never stale — they are finished.
    """
    if job.status not in _NON_TERMINAL:
        return False
    idle = job_idle_seconds(job, now)
    if idle is None:
        return False
    limit = STALE_AFTER_SECONDS if threshold_seconds is None else threshold_seconds
    return idle > limit


def find_stale_jobs(session, now: datetime | None = None,
                    threshold_seconds: int | None = None) -> list[Job]:
    """Every non-terminal job that has stopped progressing. Read-only."""
    limit = STALE_AFTER_SECONDS if threshold_seconds is None else threshold_seconds
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=limit)

    candidates = (
        session.query(Job)
        .filter(Job.status.in_(_NON_TERMINAL))
        .order_by(Job.id)
        .all()
    )
    # Filtered in Python rather than SQL: updated_at is stored naive, so a
    # SQL comparison against an aware cutoff is not portable.
    return [j for j in candidates
            if is_job_stale(j, now=now, threshold_seconds=limit)]
