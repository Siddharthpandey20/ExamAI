"""
pipeline.py — Orchestrator for the PYQ ingestion and mapping pipeline.

Architecture: Three-phase parallel pipeline
─────────────────────────────────────────────
  Phase A — Text Extraction  (CPU/IO bound, parallel across files)
  Phase B — LLM Question Extraction  (GPU/API bound, parallel across files)
  Phase C — Hybrid Search + DB Write  (sequential per question, but
            files run concurrently via ThreadPool)

Multiple PYQ files are processed in parallel using ThreadPoolExecutor.
Phases A and B run concurrently across files. Phase C uses a threading
lock to serialize SQLite writes safely.

Duplicate prevention (two-layer):
  - Primary: SQLite `pyq_questions.source_file` (authoritative)
  - Secondary: JSON tracker file (fast pre-filter)

Flow per file:
  1. Parse PDF/PPTX → raw text                          (Phase A)
  2. Llama 3 → structured question list                  (Phase B)
  3. For each question: hybrid search → RRF              (Phase C)
  4. Record matches + increment hit counts in SQLite      (Phase C)
  5. Global importance recomputation (after all files)
"""

import os
import logging
import glob
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from indexing.database import get_db, init_db
from indexing.db_chroma import ChromaStore
from indexing.embedder import Embedder

from pyq.config import PYQ_UPLOAD_DIR, SUPPORTED_EXTENSIONS, MAX_WORKERS
from pyq.extractor import extract_questions
from pyq.bm25_search import BM25Index
from pyq.hybrid_search import hybrid_search
from pyq.mapper import (
    record_matches,
    recompute_importance_scores,
    is_pyq_already_ingested,
)
from pyq.tracker import is_processed, mark_processed
from pyq.ingestion_helper import extract_pyq_text

log = logging.getLogger(__name__)

# Lock for SQLite writes — SQLAlchemy sessions are not thread-safe
_db_write_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────
# Phase A — Text Extraction (IO-bound, parallelizable)
# ─────────────────────────────────────────────────────────────────────

def _extract_raw_text(filepath: str) -> str:
    """
    Run PYQ-specific ingestion (Stage 1: parse+render, Stage 2: OCR)
    and return concatenated text from native + OCR sources.
    """
    ext = os.path.splitext(filepath)[1].lower()
    fname = os.path.basename(filepath)

    if ext != ".pdf":
        log.warning(f"[Phase A] Only PDF supported for PYQ, got: {ext}")
        return ""

    log.info(f"[Phase A] Extracting text from PYQ: {fname}")
    pages = extract_pyq_text(filepath)

    all_text = []
    for page in pages:
        parts = []
        pnum = page.get("page_num", 0)

        native = page.get("native_text", "").strip()
        if native:
            parts.append(native)

        ocr = page.get("ocr_text", "").strip()
        if ocr:
            parts.append(ocr)

        if parts:
            all_text.append(f"--- Page {pnum} ---")
            all_text.extend(parts)

    combined = "\n\n".join(all_text)
    log.info(f"[Phase A] {fname}: {len(combined)} chars from {len(pages)} pages")
    return combined


# ─────────────────────────────────────────────────────────────────────
# Phase B — LLM Question Extraction (API-bound, parallelizable)
# ─────────────────────────────────────────────────────────────────────

def _extract_questions_from_text(raw_text: str, source_hint: str):
    """Send raw text to Llama 3 and get structured questions."""
    log.info(f"[Phase B] Extracting questions for: {source_hint}")
    return extract_questions(raw_text, source_hint=source_hint)


# ─────────────────────────────────────────────────────────────────────
# Phase C — Search + DB Write (DB writes serialized via lock)
# ─────────────────────────────────────────────────────────────────────

def _search_and_record(
    question_list,
    filename: str,
    embedder: Embedder,
    chroma: ChromaStore,
) -> int:
    """
    Run hybrid search for all questions and record matches in SQLite.
    DB writes are serialized via _db_write_lock.
    Returns total number of matches.
    """
    total_matches = 0

    with _db_write_lock:
        with get_db() as session:
            # Build BM25 index (reflects latest embedded slides)
            bm25_index = BM25Index(session)

            for q in question_list.questions:
                log.info(
                    f"[Phase C] {filename} Q{q.question_number}: "
                    f"{q.question_text[:60]}..."
                )

                matches = hybrid_search(
                    query=q.question_text,
                    session=session,
                    embedder=embedder,
                    chroma=chroma,
                    bm25_index=bm25_index,
                )

                record_matches(session, q, matches, source_file=filename)
                total_matches += len(matches)

                for m in matches:
                    log.info(
                        f"    → Slide {m.page_number} (doc={m.doc_id}) "
                        f"RRF={m.rrf_score:.4f} "
                        f"[D:{m.dense_rank or '-'} S:{m.sparse_rank or '-'}]"
                    )

    return total_matches


# ─────────────────────────────────────────────────────────────────────
# Per-file pipeline (runs all 3 phases for one file)
# ─────────────────────────────────────────────────────────────────────

def _process_single_file(
    filepath: str,
    embedder: Embedder,
    chroma: ChromaStore,
    force: bool = False,
) -> dict:
    """
    Process one PYQ file through phases A → B → C.
    Thread-safe: DB writes are serialized via _db_write_lock.
    """
    filename = os.path.basename(filepath)
    result = {"filename": filename, "status": "ok", "questions": 0, "matches": 0}

    # ── Duplicate check 1: JSON tracker (fast pre-filter) ────────────
    if not force and is_processed(filepath):
        log.info(f"[Pipeline] SKIP '{filename}' — already in tracker")
        result["status"] = "skipped"
        return result

    # ── Duplicate check 2: SQLite (authoritative) ────────────────────
    if not force:
        with get_db() as session:
            if is_pyq_already_ingested(session, filename):
                log.info(f"[Pipeline] SKIP '{filename}' — already in SQLite")
                mark_processed(filepath, 0, 0)  # sync tracker to match DB
                result["status"] = "skipped"
                return result

    # ── Phase A: Extract raw text ────────────────────────────────────
    raw_text = _extract_raw_text(filepath)
    if not raw_text.strip():
        log.warning(f"[Pipeline] No text extracted from {filename}")
        result["status"] = "no_text"
        return result

    # ── Phase B: LLM question extraction ─────────────────────────────
    source_hint = os.path.splitext(filename)[0]
    question_list = _extract_questions_from_text(raw_text, source_hint)

    if not question_list.questions:
        log.warning(f"[Pipeline] No questions extracted from {filename}")
        result["status"] = "no_questions"
        return result

    result["questions"] = len(question_list.questions)
    log.info(f"[Pipeline] {filename}: {len(question_list.questions)} questions extracted")

    # ── Phase C: Search + DB write ───────────────────────────────────
    total_matches = _search_and_record(question_list, filename, embedder, chroma)
    result["matches"] = total_matches

    # ── Mark in tracker ──────────────────────────────────────────────
    mark_processed(filepath, result["questions"], total_matches)

    log.info(
        f"[DONE] {filename}: {result['questions']} questions, "
        f"{total_matches} matches"
    )
    return result


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

def run_pyq_pipeline(filepath: str | None = None, force: bool = False) -> list[dict]:
    """
    Run the PYQ pipeline on one or many files.

    Multiple files are processed in parallel:
      - Phase A (text extraction) and Phase B (LLM) overlap across files
      - Phase C (DB writes) is serialized via a threading lock

    Parameters
    ----------
    filepath : str or None
        Single file path, or None to scan pyq_uploads/.
    force : bool
        Re-process even if tracked / already in DB.

    Returns
    -------
    list[dict] — one result per file: {filename, status, questions, matches}
    """
    os.makedirs(PYQ_UPLOAD_DIR, exist_ok=True)

    # ── Collect files ────────────────────────────────────────────────
    if filepath:
        files = [os.path.abspath(filepath)]
    else:
        files = []
        for ext in SUPPORTED_EXTENSIONS:
            pattern = os.path.join(PYQ_UPLOAD_DIR, f"*{ext}")
            files.extend(glob.glob(pattern))
        files.sort()

    if not files:
        log.info("[Pipeline] No PYQ files to process.")
        return []

    log.info(f"[Pipeline] {len(files)} PYQ file(s) found")

    # ── Init shared resources (created once, shared across threads) ──
    init_db()
    chroma = ChromaStore()
    embedder = Embedder()

    # ── Parallel file processing ─────────────────────────────────────
    results: list[dict] = []

    if len(files) == 1:
        # Single file — no thread overhead
        results.append(
            _process_single_file(files[0], embedder, chroma, force)
        )
    else:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            future_map = {
                pool.submit(
                    _process_single_file, fpath, embedder, chroma, force
                ): fpath
                for fpath in files
            }

            for future in as_completed(future_map):
                fpath = future_map[future]
                fname = os.path.basename(fpath)
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    log.error(f"[Pipeline] FAILED '{fname}': {e}", exc_info=True)
                    results.append({
                        "filename": fname,
                        "status": "error",
                        "questions": 0,
                        "matches": 0,
                    })

    # ── Global importance recomputation (after ALL files done) ───────
    with get_db() as session:
        recompute_importance_scores(session)

    # ── Summary ──────────────────────────────────────────────────────
    total_q = sum(r["questions"] for r in results)
    total_m = sum(r["matches"] for r in results)
    skipped = sum(1 for r in results if r["status"] == "skipped")
    log.info(
        f"\n[Pipeline] PYQ Complete — "
        f"{len(results)} files ({skipped} skipped), "
        f"{total_q} questions, {total_m} matches"
    )

    return results
