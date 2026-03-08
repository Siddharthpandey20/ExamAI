"""
status.py — Job status query functions.

All functions return plain dicts/lists — ready for FastAPI JSON responses.
No Celery dependency; reads only from SQLite.
"""

import logging

from jobs.models import Job, JobPhase, JobStatus, PhaseStatus
from indexing.database import get_db, init_db

log = logging.getLogger(__name__)

_db_ready = False


def _ensure_db():
    global _db_ready
    if not _db_ready:
        import jobs.models  # noqa: F401
        init_db()
        _db_ready = True


# ── Serializers ──────────────────────────────────────────────────────────

def _serialize_phase(phase: JobPhase) -> dict:
    duration = None
    if phase.started_at and phase.completed_at:
        duration = round((phase.completed_at - phase.started_at).total_seconds(), 1)

    return {
        "phase": phase.phase,
        "status": phase.status,
        "celery_task_id": phase.celery_task_id,
        "started_at": phase.started_at.isoformat() if phase.started_at else None,
        "completed_at": phase.completed_at.isoformat() if phase.completed_at else None,
        "duration_sec": duration,
        "error": phase.error_message,
    }


def _serialize_job(job: Job) -> dict:
    return {
        "id": job.id,
        "filename": job.filename,
        "filepath": job.filepath,
        "job_type": job.job_type,
        "status": job.status,
        "subject": job.subject,
        "current_phase": job.current_phase,
        "celery_chain_id": job.celery_chain_id,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "error": job.error_message,
        "phases": [_serialize_phase(p) for p in job.phases],
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
    """
    Flat dashboard view: one row per file with current phase and progress.

    Returns:
        [{"id": 1, "filename": "3.pdf", "status": "processing",
          "current_phase": "structure", "progress": "1/3"}, ...]
    """
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

            # Determine the currently active phase
            current = next(
                (p.phase for p in phases if p.status == PhaseStatus.RUNNING.value),
                job.current_phase,
            )

            overview.append({
                "id": job.id,
                "filename": job.filename,
                "job_type": job.job_type,
                "status": job.status,
                "current_phase": current,
                "progress": f"{done}/{total}",
                "error": job.error_message,
            })

        return overview
