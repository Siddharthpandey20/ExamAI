"""
status.py — Job status query functions.

All functions return plain dicts/lists — ready for FastAPI JSON responses.
No Celery dependency; reads only from SQLite.

All timestamps are converted to IST (UTC+5:30) in the output.
Phase durations and total job duration are computed automatically.
"""

import logging
from datetime import datetime, timezone, timedelta

from jobs.models import Job, JobPhase, JobStatus, PhaseStatus
from indexing.database import get_db, init_db

log = logging.getLogger(__name__)

_db_ready = False

# IST = UTC + 5:30
_IST = timezone(timedelta(hours=5, minutes=30))


def _ensure_db():
    global _db_ready
    if not _db_ready:
        import jobs.models  # noqa: F401
        init_db()
        _db_ready = True


def _to_ist(dt: datetime | None) -> str | None:
    """Convert a UTC datetime to IST string. Returns None if input is None."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_IST).strftime("%Y-%m-%d %H:%M:%S IST")


def _duration_str(seconds: float | None) -> str | None:
    """Human-readable duration string from seconds."""
    if seconds is None:
        return None
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs:.0f}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m {secs:.0f}s"

def _ensure_ist(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_IST)


# ── Serializers ──────────────────────────────────────────────────────────

def _serialize_phase(phase: JobPhase) -> dict:
    duration_sec = None
    if phase.started_at and phase.completed_at:
        # duration_sec = round((phase.completed_at - phase.started_at).total_seconds(), 1)
        start = _ensure_ist(phase.started_at)
        end = _ensure_ist(phase.completed_at)
        duration_sec = round((end - start).total_seconds(), 1)

    return {
        "phase": phase.phase,
        "status": phase.status,
        "celery_task_id": phase.celery_task_id,
        "started_at": _to_ist(phase.started_at),
        "completed_at": _to_ist(phase.completed_at),
        "duration_sec": duration_sec,
        "duration": _duration_str(duration_sec),
        "error": phase.error_message,
        "progress_pct": phase.progress_pct or 0,
        "progress_detail": phase.progress_detail,
    }


def _serialize_job(job: Job) -> dict:
    phases_data = [_serialize_phase(p) for p in job.phases]
    total_phases = len(phases_data)

    # Compute overall progress: average of all phase percentages
    if total_phases:
        overall_pct = sum(p["progress_pct"] for p in phases_data) // total_phases
    else:
        overall_pct = 0

    # Total job duration: from first phase start to last phase end (or now)
    started_times = [p.started_at for p in job.phases if p.started_at]
    ended_times = [p.completed_at for p in job.phases if p.completed_at]
    total_duration_sec = None
    if started_times:
        first_start = _ensure_ist(min(started_times))

        if job.status in (JobStatus.COMPLETED.value, JobStatus.FAILED.value) and ended_times:
            last_end = _ensure_ist(max(ended_times))
        else:
            last_end = datetime.now(_IST)

        total_duration_sec = round((last_end - first_start).total_seconds(), 1)
    return {
        "id": job.id,
        "filename": job.filename,
        "filepath": job.filepath,
        "job_type": job.job_type,
        "status": job.status,
        "subject": job.subject,
        "current_phase": job.current_phase,
        "celery_chain_id": job.celery_chain_id,
        "created_at": _to_ist(job.created_at),
        "updated_at": _to_ist(job.updated_at),
        "error": job.error_message,
        "overall_progress_pct": overall_pct,
        "total_duration_sec": total_duration_sec,
        "total_duration": _duration_str(total_duration_sec),
        "phases": phases_data,
    }


# ── Public query API ─────────────────────────────────────────────────────

def get_job_status(job_id: int) -> dict | None:
    """Get detailed status of a single job including all phase details."""
    _ensure_db()
    with get_db() as session:
        job = session.query(Job).filter(Job.id == job_id).first()
        if not job:
            return None
        return _serialize_job(job)


def get_all_jobs() -> list[dict]:
    """Get status of all jobs, newest first."""
    _ensure_db()
    with get_db() as session:
        jobs = session.query(Job).order_by(Job.created_at.desc()).all()
        return [_serialize_job(j) for j in jobs]


def get_active_jobs() -> list[dict]:
    """Get only jobs that are pending or currently processing."""
    _ensure_db()
    with get_db() as session:
        jobs = (
            session.query(Job)
            .filter(Job.status.in_([JobStatus.PENDING.value, JobStatus.PROCESSING.value]))
            .order_by(Job.created_at.desc())
            .all()
        )
        return [_serialize_job(j) for j in jobs]


def get_pipeline_overview() -> list[dict]:
    _ensure_db()
    with get_db() as session:
        jobs = session.query(Job).order_by(Job.created_at.desc()).all()

        overview = []
        for job in jobs:
            phases = job.phases

            done = sum(
                1 for p in phases
                if p.status in (PhaseStatus.COMPLETED.value, PhaseStatus.SKIPPED.value)
            )
            total = len(phases)

            current = next(
                (p.phase for p in phases if p.status == PhaseStatus.RUNNING.value),
                job.current_phase,
            )

            # Total job duration
            started_times = [p.started_at for p in phases if p.started_at]
            ended_times = [p.completed_at for p in phases if p.completed_at]
            total_duration_sec = None

            if started_times:
                first_start = _ensure_ist(min(started_times))

                if job.status in (JobStatus.COMPLETED.value, JobStatus.FAILED.value) and ended_times:
                    last_end = _ensure_ist(max(ended_times))
                else:
                    last_end = datetime.now(_IST)

                total_duration_sec = round((last_end - first_start).total_seconds(), 1)

            overview.append({
                "id": job.id,
                "filename": job.filename,
                "job_type": job.job_type,
                "status": job.status,
                "subject": job.subject,
                "current_phase": current,
                "progress": f"{done}/{total}",
                "overall_progress_pct": sum(
                    (p.progress_pct if p.progress_pct is not None else 0) for p in phases
                ) // total if total else 0,
                "progress_detail": next(
                    (p.progress_detail for p in phases if p.status == PhaseStatus.RUNNING.value),
                    None,
                ),
                "total_duration_sec": total_duration_sec,
                "total_duration": _duration_str(total_duration_sec),
                "created_at": _to_ist(job.created_at),
                "error": job.error_message,
            })

        return overview