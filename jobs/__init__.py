"""
Jobs Module — ExamPrep AI

Async job infrastructure for background pipeline processing.
Uses Celery + Redis for task queuing and SQLite for job tracking.

User submits files → Celery chains fire → Each file flows through
ingest → structure → index automatically in the background.
Multiple files process in parallel via the worker thread pool.

Public API (FastAPI-ready):
    submit_study_materials(filepaths) → list[int]   # returns job IDs
    submit_pyq_files(filepaths)      → list[int]   # returns job IDs
    get_job_status(job_id)           → dict | None
    get_all_jobs()                   → list[dict]
    get_active_jobs()                → list[dict]
    get_pipeline_overview()          → list[dict]

Usage:
    from jobs import submit_study_materials, get_job_status

    job_ids = submit_study_materials(["uploads/ch1.pdf", "uploads/ch2.pdf"])
    for jid in job_ids:
        print(get_job_status(jid))

CLI:
    python -m jobs worker                              # start Celery worker
    python -m jobs submit uploads/file.pdf             # submit study material
    python -m jobs submit --pyq pyq_uploads/paper.pdf  # submit PYQ
    python -m jobs status                              # show all jobs
    python -m jobs status 5                            # show job #5 detail
    python -m jobs overview                            # pipeline dashboard
"""

import os
import logging

from celery import chain as celery_chain

from jobs.models import (
    Job, JobPhase,
    JobType, JobStatus, PhaseStatus,
    STUDY_PHASES, PYQ_PHASES,
)
from jobs.status import get_job_status, get_all_jobs, get_active_jobs, get_pipeline_overview
from indexing.database import get_db, init_db

log = logging.getLogger(__name__)

# Re-export status functions for convenience
__all__ = [
    "submit_study_materials",
    "submit_pyq_files",
    "get_job_status",
    "get_all_jobs",
    "get_active_jobs",
    "get_pipeline_overview",
]


def _ensure_db():
    import jobs.models  # noqa: F401
    init_db()


def _create_job(filepath: str, job_type: str, subject: str = "") -> int:
    """Create a Job record with its phase records in SQLite. Returns job ID."""
    _ensure_db()
    filename = os.path.basename(filepath)
    phases = STUDY_PHASES if job_type == JobType.STUDY_MATERIAL.value else PYQ_PHASES

    with get_db() as session:
        job = Job(
            filename=filename,
            filepath=os.path.abspath(filepath),
            job_type=job_type,
            status=JobStatus.PENDING.value,
            subject=subject,
        )
        session.add(job)
        session.flush()

        for phase_name in phases:
            phase = JobPhase(
                job_id=job.id,
                phase=phase_name,
                status=PhaseStatus.PENDING.value,
            )
            session.add(phase)

        session.flush()
        job_id = job.id

    return job_id


def _store_chain_id(job_id: int, chain_id: str):
    """Store the Celery AsyncResult ID on the job for external tracking."""
    with get_db() as session:
        job = session.query(Job).filter(Job.id == job_id).first()
        if job:
            job.celery_chain_id = chain_id


def submit_study_materials(filepaths: list[str], subject: str = "") -> list[int]:
    """
    Submit study material files for background processing.

    Each file gets its own Celery chain: ingest → structure → index.
    All chains run in parallel through the worker thread pool.

    Parameters
    ----------
    filepaths : list[str]
        Paths to raw upload files (PDF, PPTX).
    subject : str
        User-assigned subject name (will be uppercased).

    Returns
    -------
    list[int]
        Job IDs for tracking progress via get_job_status().
    """
    from jobs.tasks import ingest_task, structure_task, index_task

    subject = subject.strip().upper() if subject else ""

    job_ids = []
    for filepath in filepaths:
        filepath = os.path.abspath(filepath)
        if not os.path.isfile(filepath):
            log.warning(f"[submit] File not found: {filepath}")
            continue

        job_id = _create_job(filepath, JobType.STUDY_MATERIAL.value, subject=subject)

        pipeline = celery_chain(
            ingest_task.s(filepath, job_id, subject),
            structure_task.s(job_id),
            index_task.s(job_id, subject),
        )
        result = pipeline.apply_async()
        _store_chain_id(job_id, result.id)

        log.info(f"[submit] Job {job_id}: {os.path.basename(filepath)} -> chain {result.id}")
        job_ids.append(job_id)

    return job_ids


def submit_pyq_files(filepaths: list[str], subject: str = "") -> list[int]:
    """
    Submit PYQ files for background processing.

    Each file gets a single Celery task with internal phase tracking
    (ingest_pyq → extract → map).

    Parameters
    ----------
    filepaths : list[str]
        Paths to PYQ PDFs.
    subject : str
        User-assigned subject name.

    Returns
    -------
    list[int]
        Job IDs for tracking progress via get_job_status().
    """
    from jobs.tasks import process_pyq_task

    job_ids = []
    for filepath in filepaths:
        filepath = os.path.abspath(filepath)
        if not os.path.isfile(filepath):
            log.warning(f"[submit] File not found: {filepath}")
            continue

        job_id = _create_job(filepath, JobType.PYQ.value, subject=subject)

        result = process_pyq_task.apply_async(args=[filepath, job_id, subject])
        _store_chain_id(job_id, result.id)

        log.info(f"[submit] PYQ Job {job_id}: {os.path.basename(filepath)} -> task {result.id}")
        job_ids.append(job_id)

    return job_ids
