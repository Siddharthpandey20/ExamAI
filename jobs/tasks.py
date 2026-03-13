"""
tasks.py — Celery task definitions for the ExamAI pipeline.

Study Material chain (3 tasks, Celery chain):
    ingest_task  →  structure_task  →  index_task
    Each task returns md_path, which flows into the next via Celery chaining.

PYQ pipeline (1 task, internally phased):
    process_pyq_task  (ingest_pyq → extract → map)
    Single task because PYQ phases are tightly coupled.

Design:
  - Each task updates job/phase status in SQLite before and after execution.
  - Already-processed files are detected and phases marked "skipped".
  - Heavy resources (Embedder, ChromaStore) are cached per worker process.
  - Errors are recorded in SQLite, then re-raised to stop the chain.
  - All DB writes use _safe_db_op() with retry to handle transient SQLite locks.
"""

import os
import logging
import asyncio
import threading
import time
from datetime import datetime, timezone

from jobs.celery_app import app
from jobs.models import (
    Job, JobPhase,
    JobStatus, PhaseStatus,
)
from indexing.database import get_db, init_db

log = logging.getLogger(__name__)

# Max retries and delay for transient SQLite lock errors
_DB_RETRY_ATTEMPTS = 8
_DB_RETRY_DELAY = 0.25  # seconds, doubles each retry (max ~32s total)


# ═════════════════════════════════════════════════════════════════════════
# Shared resource cache (per worker process)
# ═════════════════════════════════════════════════════════════════════════

_resource_lock = threading.Lock()
_embedder = None
_chroma = None
_db_initialized = False


def _ensure_db():
    """Register job models with SQLAlchemy Base and create tables."""
    global _db_initialized
    if not _db_initialized:
        import jobs.models  # noqa: F401 — registers models with Base
        init_db()
        _db_initialized = True


def _get_embedder():
    """Lazy singleton: load the 1.3 GB sentence-transformer once per worker."""
    global _embedder
    if _embedder is None:
        with _resource_lock:
            if _embedder is None:
                from indexing.embedder import Embedder
                _embedder = Embedder()
    return _embedder


def _get_chroma():
    """Lazy singleton: open ChromaDB persistent client once per worker."""
    global _chroma
    if _chroma is None:
        with _resource_lock:
            if _chroma is None:
                from indexing.db_chroma import ChromaStore
                _chroma = ChromaStore()
    return _chroma


# ═════════════════════════════════════════════════════════════════════════
# Safe DB write with retry (handles transient SQLite locks)
# ═════════════════════════════════════════════════════════════════════════

def _safe_db_op(fn):
    """
    Execute a callable that uses get_db() with retry on OperationalError.
    Returns whatever *fn* returns so callers can retrieve results.
    Prevents "database is locked" crashes when study_material and PYQ
    chains run concurrently.
    """
    delay = _DB_RETRY_DELAY
    for attempt in range(1, _DB_RETRY_ATTEMPTS + 1):
        try:
            return fn()
        except Exception as exc:
            if "database is locked" in str(exc) and attempt < _DB_RETRY_ATTEMPTS:
                log.warning(f"[db] Locked (attempt {attempt}/{_DB_RETRY_ATTEMPTS}), retrying in {delay:.1f}s")
                time.sleep(delay)
                delay *= 2
            else:
                raise


# ═════════════════════════════════════════════════════════════════════════
# Phase / Job status helpers
# ═════════════════════════════════════════════════════════════════════════

def _update_phase(job_id, phase, status, task_id=None, error=None, progress_pct=None, progress_detail=None):
    """Update a single phase's status and sync the parent job's tracking fields."""
    def _op():
        with get_db() as session:
            jp = (
                session.query(JobPhase)
                .filter(JobPhase.job_id == job_id, JobPhase.phase == phase)
                .first()
            )
            if not jp:
                return

            jp.status = status
            if task_id:
                jp.celery_task_id = task_id
            if status == PhaseStatus.RUNNING.value:
                jp.started_at = datetime.now(timezone.utc)
                if progress_pct is None:
                    jp.progress_pct = 0
            if status in (PhaseStatus.COMPLETED.value, PhaseStatus.SKIPPED.value,
                           PhaseStatus.FAILED.value):
                jp.completed_at = datetime.now(timezone.utc)
                jp.progress_pct = 100
                jp.progress_detail = None
            if error:
                jp.error_message = error
            if progress_pct is not None:
                jp.progress_pct = progress_pct
            if progress_detail is not None:
                jp.progress_detail = progress_detail

            # Sync parent job
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                job.current_phase = phase
                job.updated_at = datetime.now(timezone.utc)
                if status == PhaseStatus.RUNNING.value and job.status == JobStatus.PENDING.value:
                    job.status = JobStatus.PROCESSING.value
    _safe_db_op(_op)


def _update_progress(job_id, phase, pct, detail=None):
    """Lightweight mid-task progress update (no status change)."""
    def _op():
        with get_db() as session:
            jp = (
                session.query(JobPhase)
                .filter(JobPhase.job_id == job_id, JobPhase.phase == phase)
                .first()
            )
            if jp:
                jp.progress_pct = pct
                if detail is not None:
                    jp.progress_detail = detail
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                job.updated_at = datetime.now(timezone.utc)
    _safe_db_op(_op)


def _fail_job(job_id, phase, error):
    """Mark a job and its current phase as failed."""
    def _op():
        with get_db() as session:
            jp = (
                session.query(JobPhase)
                .filter(JobPhase.job_id == job_id, JobPhase.phase == phase)
                .first()
            )
            if jp:
                jp.status = PhaseStatus.FAILED.value
                jp.completed_at = datetime.now(timezone.utc)
                jp.error_message = error

            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.current_phase = phase
                job.updated_at = datetime.now(timezone.utc)
                job.error_message = error
    _safe_db_op(_op)


def _complete_job(job_id):
    """Mark a job as successfully completed."""
    def _op():
        with get_db() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.COMPLETED.value
                job.updated_at = datetime.now(timezone.utc)
    _safe_db_op(_op)


# ═════════════════════════════════════════════════════════════════════════
# Study Material Tasks — chained: ingest → structure → index
# ═════════════════════════════════════════════════════════════════════════

@app.task(bind=True, name="jobs.ingest")
def ingest_task(self, filepath, job_id, subject=""):
    """
    Phase 1: Parse a raw upload (PDF/PPTX) into knowledge markdown.

    Skips if the file was already ingested (tracker check).
    Returns md_path for the next task in the Celery chain.
    """
    _ensure_db()

    from ingestion.pipeline import run_pipeline
    from ingestion.tracker import is_processed, mark_processed
    from indexing.config import get_subject_dirs

    filename = os.path.basename(filepath)
    knowledge_dir = get_subject_dirs(subject)["knowledge"] if subject else None

    # ── Skip if already ingested ─────────────────────────────────────
    if is_processed(filepath):
        stem = os.path.splitext(filename)[0]
        if knowledge_dir:
            md_path = os.path.join(knowledge_dir, f"{stem}.md")
        else:
            from ingestion.config import KNOWLEDGE_DIR
            md_path = os.path.join(KNOWLEDGE_DIR, f"{stem}.md")
        if os.path.exists(md_path):
            log.info(f"[ingest] '{filename}' already ingested -> skipped")
            _update_phase(job_id, "ingest", PhaseStatus.SKIPPED.value)
            return md_path

    # ── Run ingestion ────────────────────────────────────────────────
    _update_phase(job_id, "ingest", PhaseStatus.RUNNING.value, task_id=self.request.id,
                  progress_detail="Starting ingestion")

    def _ingest_progress(pct, detail):
        _update_progress(job_id, "ingest", pct, detail)

    try:
        md_path = run_pipeline(filepath, knowledge_dir=knowledge_dir, progress_cb=_ingest_progress)
        if not md_path:
            raise RuntimeError(f"Ingestion produced no output for '{filename}'")

        mark_processed(filepath)
        _update_phase(job_id, "ingest", PhaseStatus.COMPLETED.value)
        log.info(f"[ingest] Done: {filename} -> {md_path}")
        return md_path

    except Exception as e:
        log.error(f"[ingest] Failed: {filename} — {e}", exc_info=True)
        _fail_job(job_id, "ingest", str(e))
        raise


@app.task(bind=True, name="jobs.structure")
def structure_task(self, md_path, job_id):
    """
    Phase 2: Run agentic structuring (LLM classification) on the markdown.

    Receives md_path from ingest_task via Celery chain result passing.
    Returns md_path for the index task.
    """
    _ensure_db()

    from structuring import process_file
    from structuring.tracker import is_structured, mark_structured

    filename = os.path.basename(md_path)

    # ── Skip if already structured ───────────────────────────────────
    if is_structured(filename):
        log.info(f"[structure] '{filename}' already structured -> skipped")
        _update_phase(job_id, "structure", PhaseStatus.SKIPPED.value)
        return md_path

    # ── Run structuring (async → sync bridge) ────────────────────────
    _update_phase(job_id, "structure", PhaseStatus.RUNNING.value, task_id=self.request.id,
                  progress_detail="Running LLM classification")

    try:
        _update_progress(job_id, "structure", 10, "Agent 1: Document overview (Ollama)")
        result = asyncio.run(process_file(md_path))
        if not result:
            raise RuntimeError(f"Structuring produced no output for '{filename}'")

        mark_structured(filename, result)
        _update_phase(job_id, "structure", PhaseStatus.COMPLETED.value)
        log.info(f"[structure] Done: {filename}")
        return md_path

    except Exception as e:
        log.error(f"[structure] Failed: {filename} — {e}", exc_info=True)
        _fail_job(job_id, "structure", str(e))
        raise


@app.task(bind=True, name="jobs.index")
def index_task(self, md_path, job_id, subject=""):
    """
    Phase 3: Embed structured knowledge into ChromaDB + SQLite.

    Receives md_path from structure_task via Celery chain result passing.
    Uses shared Embedder and ChromaStore singletons for efficiency.
    """
    _ensure_db()

    from indexing.pipeline import index_file
    from indexing.db_sqlite import md5_file, get_document_by_hash, get_unembedded_slides

    filename = os.path.basename(md_path)
    embedder = _get_embedder()
    chroma = _get_chroma()

    # ── Skip if already fully indexed ────────────────────────────────
    file_hash = md5_file(md_path)
    with get_db() as session:
        existing = get_document_by_hash(session, file_hash)
        if existing and not get_unembedded_slides(session, existing.id):
            log.info(f"[index] '{filename}' already indexed -> skipped")
            _update_phase(job_id, "index", PhaseStatus.SKIPPED.value)
            _complete_job(job_id)
            return {"md_path": md_path, "status": "skipped", "slides": 0}

    # ── Run indexing ─────────────────────────────────────────────────
    _update_phase(job_id, "index", PhaseStatus.RUNNING.value, task_id=self.request.id,
                  progress_detail="Loading embedder")

    try:
        _update_progress(job_id, "index", 20, "Parsing structured markdown")
        with get_db() as session:
            result = index_file(md_path, session, chroma, embedder, subject=subject)

        _update_phase(job_id, "index", PhaseStatus.COMPLETED.value)
        _complete_job(job_id)
        log.info(f"[index] Done: {filename} — {result['slides_indexed']} slides")

        # ── Auto re-map: if PYQ questions exist for this subject,
        #    re-run mapping so the new slides get scored too ──────────
        if subject:
            _trigger_pyq_remap(subject)

        return {
            "md_path": md_path,
            "status": result["status"],
            "slides": result["slides_indexed"],
        }

    except Exception as e:
        log.error(f"[index] Failed: {filename} — {e}", exc_info=True)
        _fail_job(job_id, "index", str(e))
        raise


# ═════════════════════════════════════════════════════════════════════════
# PYQ Task — single task with internal phase tracking
# ═════════════════════════════════════════════════════════════════════════

@app.task(bind=True, name="jobs.process_pyq")
def process_pyq_task(self, filepath, job_id, subject=""):
    """
    Process a PYQ file through all three phases sequentially:

      Phase 1 (ingest_pyq): OCR text extraction from scanned paper
      Phase 2 (extract):    LLM-based question extraction via Llama 3
      Phase 3 (map):        Hybrid search + slide mapping + importance scoring

    Phase status is updated at each transition for real-time progress visibility.
    """
    _ensure_db()

    from pyq.ingestion_helper import extract_pyq_text
    from pyq.extractor import extract_questions
    from pyq.hybrid_search import hybrid_search
    from pyq.mapper import record_matches, recompute_importance_scores
    from pyq.tracker import is_processed, mark_processed
    from pyq.bm25_search import BM25Index

    filename = os.path.basename(filepath)
    embedder = _get_embedder()
    chroma = _get_chroma()

    # ── Phase 1: Text extraction (OCR) ───────────────────────────────
    _update_phase(job_id, "ingest_pyq", PhaseStatus.RUNNING.value, task_id=self.request.id,
                  progress_detail="Extracting text via OCR")

    try:
        pages = extract_pyq_text(filepath)

        all_text = []
        for page in pages:
            parts = []
            if page.get("native_text", "").strip():
                parts.append(page["native_text"])
            if page.get("ocr_text", "").strip():
                parts.append(page["ocr_text"])
            if parts:
                all_text.append(f"--- Page {page.get('page_num', 0)} ---")
                all_text.extend(parts)
        raw_text = "\n\n".join(all_text)

        if not raw_text.strip():
            _fail_job(job_id, "ingest_pyq", "No text could be extracted from PDF")
            return {"filename": filename, "status": "no_text", "questions": 0, "matches": 0}

        _update_phase(job_id, "ingest_pyq", PhaseStatus.COMPLETED.value)

    except Exception as e:
        log.error(f"[pyq] Phase 1 failed: {filename} — {e}", exc_info=True)
        _fail_job(job_id, "ingest_pyq", str(e))
        raise

    # ── Phase 2: Question extraction (LLM) ───────────────────────────
    _update_phase(job_id, "extract", PhaseStatus.RUNNING.value,
                  progress_detail="Sending to Llama3 for question extraction")

    try:
        source_hint = os.path.splitext(filename)[0]
        question_list = extract_questions(raw_text, source_hint=source_hint)

        if not question_list.questions:
            _update_phase(job_id, "extract", PhaseStatus.COMPLETED.value)
            _update_phase(job_id, "map", PhaseStatus.SKIPPED.value)
            _complete_job(job_id)
            mark_processed(filepath, 0, 0)
            return {"filename": filename, "status": "no_questions", "questions": 0, "matches": 0}

        _update_phase(job_id, "extract", PhaseStatus.COMPLETED.value)

    except Exception as e:
        log.error(f"[pyq] Phase 2 failed: {filename} — {e}", exc_info=True)
        _fail_job(job_id, "extract", str(e))
        raise

    # ── Phase 3: Hybrid search + slide mapping ───────────────────────
    #
    # CRITICAL: Each question is processed in its own short DB session
    # (micro-transaction) so the SQLite write lock is held for only
    # milliseconds at a time.  The previous design opened ONE session
    # for the entire loop; record_matches' flush() acquired the write
    # lock early and held it until the loop finished — blocking every
    # other DB writer (including the progress-update calls) for minutes.
    #
    _update_phase(job_id, "map", PhaseStatus.RUNNING.value,
                  progress_detail="Building BM25 index")

    try:
        # Build BM25 index in a short read-only session (closes immediately)
        with get_db() as session:
            bm25_index = BM25Index(session)

        total_matches = 0
        n_questions = len(question_list.questions)

        for i, q in enumerate(question_list.questions, 1):
            _update_progress(job_id, "map",
                             int(i / n_questions * 90),
                             f"Mapping question {i}/{n_questions}")

            # One short transaction per question: search → record → commit
            def _map_one(question=q):
                with get_db() as sess:
                    matches = hybrid_search(
                        query=question.question_text,
                        session=sess,
                        embedder=embedder,
                        chroma=chroma,
                        bm25_index=bm25_index,
                        subject=subject,
                    )
                    record_matches(sess, question, matches,
                                   source_file=filename, subject=subject)
                    return len(matches)

            n = _safe_db_op(_map_one)
            total_matches += n

        # Final short transaction: recompute importance scores
        def _recompute():
            with get_db() as sess:
                recompute_importance_scores(sess)
        _safe_db_op(_recompute)

        _update_phase(job_id, "map", PhaseStatus.COMPLETED.value)
        _complete_job(job_id)
        mark_processed(filepath, len(question_list.questions), total_matches)

        log.info(
            f"[pyq] Done: {filename} — "
            f"{len(question_list.questions)} questions, {total_matches} matches"
        )
        return {
            "filename": filename,
            "status": "ok",
            "questions": len(question_list.questions),
            "matches": total_matches,
        }

    except Exception as e:
        log.error(f"[pyq] Phase 3 failed: {filename} — {e}", exc_info=True)
        _fail_job(job_id, "map", str(e))
        raise


# ═════════════════════════════════════════════════════════════════════════
# Auto PYQ Re-map — triggered when new study material is indexed
# ═════════════════════════════════════════════════════════════════════════

def _trigger_pyq_remap(subject: str):
    """
    Check if PYQ questions exist for *subject*; if so, fire remap_pyq_task
    so the newly indexed slides get matched against existing questions.
    """
    from indexing.models import PYQQuestion
    with get_db() as session:
        q_count = (
            session.query(PYQQuestion)
            .filter(PYQQuestion.subject == subject)
            .count()
        )
    if q_count > 0:
        log.info(f"[auto-remap] {q_count} PYQ questions exist for {subject} — scheduling re-map")
        remap_pyq_task.apply_async(args=[subject])


@app.task(bind=True, name="jobs.remap_pyq")
def remap_pyq_task(self, subject):
    """
    Re-run hybrid search for ALL existing PYQ questions against the
    current slide index for *subject*.  Updates similarity matches and
    recomputes importance scores.

    This fires automatically after new study material is indexed, so
    PYQ scores stay up-to-date without user intervention.
    """
    _ensure_db()

    from pyq.hybrid_search import hybrid_search
    from pyq.mapper import record_matches, recompute_importance_scores
    from pyq.bm25_search import BM25Index
    from indexing.models import PYQQuestion, PYQMatch

    embedder = _get_embedder()
    chroma = _get_chroma()

    log.info(f"[remap] Starting PYQ re-map for subject={subject}")

    from pyq.schemas import ExtractedQuestion
    from indexing.models import Slide

    try:
        # ── Step 1: Load questions (short read session) ──────────────
        with get_db() as session:
            questions = (
                session.query(PYQQuestion)
                .filter(PYQQuestion.subject == subject)
                .all()
            )
            if not questions:
                log.info(f"[remap] No PYQ questions for {subject} — nothing to do")
                return {"subject": subject, "status": "no_questions"}

            # Detach data we need so we can close the session
            q_data = [
                {"id": q.id, "text": q.question_text, "source": q.source_file or ""}
                for q in questions
            ]
            q_ids = [d["id"] for d in q_data]

        # ── Step 2: Clear old matches (short write session) ──────────
        def _clear_old():
            with get_db() as session:
                session.query(PYQMatch).filter(PYQMatch.pyq_id.in_(q_ids)).delete(synchronize_session="fetch")
                # pyq_hit_count and importance_score are recomputed from
                # pyq_matches at the end (step 5), so no need to zero them
                # here.  Zeroing was incorrect because cross-subject matches
                # on these slides would be lost.
        _safe_db_op(_clear_old)

        # ── Step 3: Build BM25 index (short read session) ────────────
        with get_db() as session:
            bm25_index = BM25Index(session)

        # ── Step 4: Map each question (micro-transaction per Q) ──────
        total_matches = 0
        for qd in q_data:
            def _map_one(data=qd):
                with get_db() as session:
                    matches = hybrid_search(
                        query=data["text"],
                        session=session,
                        embedder=embedder,
                        chroma=chroma,
                        bm25_index=bm25_index,
                        subject=subject,
                    )
                    eq = ExtractedQuestion(
                        question_number=0,
                        question_text=data["text"],
                        marks=None,
                    )
                    record_matches(session, eq, matches,
                                   source_file=data["source"], subject=subject)
                    return len(matches)

            n = _safe_db_op(_map_one)
            total_matches += n

        # ── Step 5: Recompute scores (short write session) ───────────
        def _recompute():
            with get_db() as session:
                recompute_importance_scores(session)
        _safe_db_op(_recompute)

        log.info(f"[remap] Done: {subject} — {len(q_data)} questions, {total_matches} matches")
        return {
            "subject": subject,
            "status": "ok",
            "questions": len(q_data),
            "matches": total_matches,
        }

    except Exception as e:
        log.error(f"[remap] Failed for {subject}: {e}", exc_info=True)
        raise
