"""
routes/uploads.py — File upload + file-serving endpoints.

POST /api/upload/study-material   — upload study material (PDF/PPTX)
POST /api/upload/pyq              — upload past year question paper
GET  /api/upload/file/{subject}/{folder}/{filename} — serve an uploaded file
"""

import os
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Path as FastPath
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from indexing.database import get_db_dep
from indexing.models import Subject, Document, PYQQuestion
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


def safe_upload_path(target_dir: str, raw_filename: str) -> tuple[str, str]:
    """Resolve *raw_filename* to a path guaranteed to sit inside *target_dir*.

    The multipart filename is attacker-controlled and Starlette does not
    sanitise it, so joining it directly would let '../..' escape the subject
    directory.  For an ordinary filename this is an identity transform — the
    stored name must keep matching the markdown stem that indexing uses to
    find the original upload.

    Returns (safe_filename, absolute_save_path).
    """
    # Strip any directory component using both separators, so behaviour is
    # identical whether the server runs on Windows or POSIX.
    name = (raw_filename or "").replace("\\", "/").split("/")[-1]
    # Drop control characters, then leading dots/spaces so '..' and friends
    # cannot survive as a name of their own.
    name = "".join(ch for ch in name if ch.isprintable()).lstrip(". ").strip()
    if not name:
        name = "upload"

    save_path = os.path.join(target_dir, name)

    # Defence in depth: never trust the string, check the resolved path.
    resolved = os.path.realpath(save_path)
    resolved_dir = os.path.realpath(target_dir)
    try:
        inside = os.path.commonpath([resolved, resolved_dir]) == resolved_dir
    except ValueError:
        # Different drives on Windows — definitively outside.
        inside = False
    if not inside or os.path.dirname(resolved) != resolved_dir:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    return name, resolved


def _resolve_subject(subject: str, db: Session) -> str:
    """
    Resolve subject name: must already exist in DB.
    Normalizes to UPPERCASE before lookup.
    Returns the canonical subject name.
    """
    name = subject.strip().upper()
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

    dirs = get_subject_dirs(subject_name)
    filename, save_path = safe_upload_path(dirs["uploads"], file.filename)

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

    # Guard: PYQ uploads require at least one indexed study material document
    doc_count = (
        db.query(Document)
        .filter(Document.subject == subject_name, Document.status == "processed")
        .count()
    )
    if doc_count == 0:
        raise HTTPException(
            status_code=409,
            detail=f"Subject '{subject_name}' has no indexed study material yet. "
                   "Upload and process study material before uploading PYQ papers.",
        )

    dirs = get_subject_dirs(subject_name)
    filename, save_path = safe_upload_path(dirs["pyq_uploads"], file.filename)

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


# ── File serving ─────────────────────────────────────────────────────────

@router.get("/file/{subject}/{folder}/{filename}")
async def serve_uploaded_file(
    subject: str = FastPath(..., description="Subject name"),
    folder: str = FastPath(..., pattern="^(uploads|pyq_uploads)$", description="uploads or pyq_uploads"),
    filename: str = FastPath(..., description="Filename to serve"),
    db: Session = Depends(get_db_dep),
):
    """
    Serve an uploaded file (study material or PYQ) for in-app viewing.

    Only serves files from data/{subject}/uploads/ or data/{subject}/pyq_uploads/.
    """
    subject_name = subject.strip().upper()
    existing = db.query(Subject).filter(Subject.name == subject_name).first()
    if not existing:
        raise HTTPException(404, f"Subject '{subject_name}' not found.")

    dirs = get_subject_dirs(subject_name)
    target_dir = dirs.get(folder)
    if not target_dir:
        raise HTTPException(400, f"Invalid folder '{folder}'.")

    # Prevent path traversal
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(target_dir, safe_filename)
    resolved = os.path.realpath(file_path)

    if not resolved.startswith(os.path.realpath(target_dir)):
        raise HTTPException(403, "Access denied.")

    if not os.path.isfile(resolved):
        raise HTTPException(404, f"File '{safe_filename}' not found.")

    # Determine correct MIME type for in-browser viewing
    ext = os.path.splitext(safe_filename)[1].lower()
    mime_types = {
        ".pdf": "application/pdf",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".ppt": "application/vnd.ms-powerpoint",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    media_type = mime_types.get(ext, "application/octet-stream")

    return FileResponse(
        resolved,
        filename=safe_filename,
        media_type=media_type,
        content_disposition_type="inline",
    )


@router.get("/pyq-files/{subject}")
async def list_pyq_files(
    subject: str,
    db: Session = Depends(get_db_dep),
):
    """
    List all PYQ files for a subject — both from disk (pyq_uploads/) and
    unique source_file entries from the pyq_questions table.
    """
    subject_name = subject.strip().upper()
    existing = db.query(Subject).filter(Subject.name == subject_name).first()
    if not existing:
        raise HTTPException(404, f"Subject '{subject_name}' not found.")

    dirs = get_subject_dirs(subject_name)
    pyq_dir = dirs["pyq_uploads"]

    files = []
    if os.path.isdir(pyq_dir):
        for f in sorted(os.listdir(pyq_dir)):
            fpath = os.path.join(pyq_dir, f)
            if os.path.isfile(fpath):
                files.append({
                    "filename": f,
                    "size_bytes": os.path.getsize(fpath),
                    "url": f"/api/upload/file/{subject_name}/pyq_uploads/{f}",
                })

    # Count questions per source file
    question_counts: dict[str, int] = {}
    questions = (
        db.query(PYQQuestion.source_file)
        .filter(PYQQuestion.subject == subject_name)
        .all()
    )
    for (src,) in questions:
        if src:
            base = os.path.basename(src)
            question_counts[base] = question_counts.get(base, 0) + 1

    for f in files:
        f["question_count"] = question_counts.get(f["filename"], 0)

    return {
        "subject": subject_name,
        "total": len(files),
        "files": files,
    }

