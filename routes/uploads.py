"""
routes/uploads.py — File upload endpoints.

POST /api/upload/study-material   — upload study material (PDF/PPTX)
POST /api/upload/pyq              — upload past year question paper
"""

import os
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from indexing.database import get_db_dep
from indexing.models import Subject
from indexing.config import ensure_subject_dirs, get_subject_dirs

router = APIRouter()
log = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".ppt"}


def _validate_file(file: UploadFile):
    """Check that the uploaded file has a supported extension."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )


def _resolve_subject(subject: str, db: Session) -> str:
    """
    Resolve subject name: must already exist in DB.
    Returns the canonical subject name.
    """
    name = subject.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Subject name is required.")

    existing = db.query(Subject).filter(Subject.name == name).first()
    if not existing:
        raise HTTPException(
            status_code=404,
            detail=f"Subject '{name}' not found. Create it first via POST /api/subjects.",
        )
    return existing.name


@router.post("/study-material")
async def upload_study_material(
    file: UploadFile = File(...),
    subject: str = Form(...),
    db: Session = Depends(get_db_dep),
):
    """
    Upload a study material file (PDF/PPTX) for processing.

    The file is saved to data/{subject}/uploads/ and a background
    Celery chain is fired: ingest → structure → index.

    Returns the job ID for status tracking.
    """
    _validate_file(file)
    subject_name = _resolve_subject(subject, db)
    ensure_subject_dirs(subject_name)

    filename = file.filename or "upload"
    dirs = get_subject_dirs(subject_name)
    save_path = os.path.join(dirs["uploads"], filename)

    # Save uploaded file to disk
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    log.info(f"[upload] Saved study material: {save_path}")

    # Submit to Celery pipeline
    from jobs import submit_study_materials
    job_ids = submit_study_materials([save_path], subject=subject_name)

    if not job_ids:
        raise HTTPException(status_code=500, detail="Failed to create processing job.")

    return {
        "message": f"File '{filename}' uploaded and queued for processing.",
        "job_id": job_ids[0],
        "subject": subject_name,
        "filepath": save_path,
    }


@router.post("/pyq")
async def upload_pyq(
    file: UploadFile = File(...),
    subject: str = Form(...),
    db: Session = Depends(get_db_dep),
):
    """
    Upload a past year question paper (PDF) for processing.

    The file is saved to data/{subject}/pyq_uploads/ and a background
    Celery task is fired: ingest_pyq → extract → map.

    Returns the job ID for status tracking.
    """
    _validate_file(file)
    subject_name = _resolve_subject(subject, db)
    ensure_subject_dirs(subject_name)

    filename = file.filename or "upload"
    dirs = get_subject_dirs(subject_name)
    save_path = os.path.join(dirs["pyq_uploads"], filename)

    # Save uploaded file to disk
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    log.info(f"[upload] Saved PYQ: {save_path}")

    # Submit to Celery pipeline
    from jobs import submit_pyq_files
    job_ids = submit_pyq_files([save_path], subject=subject_name)

    if not job_ids:
        raise HTTPException(status_code=500, detail="Failed to create processing job.")

    return {
        "message": f"PYQ '{filename}' uploaded and queued for processing.",
        "job_id": job_ids[0],
        "subject": subject_name,
        "filepath": save_path,
    }
