"""
pipeline.py — Orchestrator for the indexing stage.

Flow per markdown file:
  1. MD5 hash the file → check SQLite cache
  2. If hash exists and all slides embedded → skip (cached)
  3. If new or changed:
       a. Parse enriched markdown → DocMeta + SlideMeta list
       b. Upsert document record in SQLite
       c. Upsert each slide record in SQLite
       d. Build embedding text per slide
       e. Batch-encode with sentence-transformers
       f. Upsert into ChromaDB with metadata
       g. Mark slides as embedded in SQLite
  4. Report stats

Both databases are stored in the ExamAI root directory.
"""

import os
import logging
import glob

from sqlalchemy.orm import Session

from indexing.config import KNOWLEDGE_DIR
from indexing.database import get_db, init_db
from indexing.db_sqlite import (
    md5_file,
    get_document_by_hash,
    insert_document,
    upsert_slide,
    mark_slides_embedded,
    get_unembedded_slides,
)
from indexing.db_chroma import ChromaStore
from indexing.md_reader import parse_structured_markdown
from indexing.embedder import Embedder, build_embed_text

log = logging.getLogger(__name__)


def _is_structured(filepath: str) -> bool:
    """Quick check: does the markdown contain a Document Overview block?"""
    with open(filepath, "r", encoding="utf-8") as f:
        head = f.read(2000)
    return "## Document Overview" in head


def _infer_subject_from_path(filepath: str) -> str:
    """
    Try to infer subject from the file path.
    e.g. 'data/ML/knowledge/file.md' → 'ML'
    Looks for the pattern data/{SUBJECT}/knowledge/...
    Returns uppercase subject name, or empty string if not inferrable.
    """
    import re
    norm = filepath.replace("\\", "/")
    m = re.search(r"data/([^/]+)/knowledge/", norm)
    if m:
        return m.group(1).upper()
    return ""


def index_file(
    filepath: str,
    session: Session,
    chroma: ChromaStore,
    embedder: Embedder,
    force: bool = False,
    subject: str = "",
) -> dict:
    """
    Index a single enriched markdown file.

    Parameters
    ----------
    filepath : str           — path to knowledge/*.md
    session  : Session       — SQLAlchemy session (managed by caller)
    chroma   : ChromaStore   — ChromaDB instance
    embedder : Embedder      — sentence-transformer encoder
    force    : bool          — if True, re-index even if hash matches
    subject  : str           — user-assigned subject name

    Returns
    -------
    dict with keys: filename, status, slides_indexed, cached
    """
    filename = os.path.basename(filepath)
    file_hash = md5_file(filepath)

    result = {"filename": filename, "status": "ok", "slides_indexed": 0, "cached": False}

    # ── Step 1: Cache check ──────────────────────────────────────────
    if not force:
        existing = get_document_by_hash(session, file_hash)
        if existing:
            unembedded = get_unembedded_slides(session, existing.id)
            if not unembedded:
                log.info(f"[Pipeline] SKIP '{filename}' — hash match, all slides embedded")
                result["status"] = "skipped"
                result["cached"] = True
                return result
            else:
                log.info(
                    f"[Pipeline] '{filename}' — hash match but {len(unembedded)} "
                    f"slides not embedded, re-embedding"
                )

    # ── Step 2: Verify it's a structured file ────────────────────────
    if not _is_structured(filepath):
        log.warning(f"[Pipeline] SKIP '{filename}' — no Document Overview found (not structured)")
        result["status"] = "not_structured"
        return result

    # ── Step 3: Parse enriched markdown ──────────────────────────────
    doc_meta, slides = parse_structured_markdown(filepath)
    if not slides:
        log.warning(f"[Pipeline] SKIP '{filename}' — no slides found")
        result["status"] = "no_slides"
        return result

    log.info(f"[Pipeline] Parsed '{filename}': {len(slides)} slides")

    # ── Step 4: Upsert document in SQLite ────────────────────────────
    import json
    from indexing.models import Subject
    chapters_json = json.dumps(doc_meta.chapters, ensure_ascii=False)
    core_topics_str = ", ".join(doc_meta.core_topics)

    # Resolve subject: prefer user-given subject, then infer from path, never use AI subject
    resolved_subject_id = None
    subject_name = subject.upper() if subject else _infer_subject_from_path(filepath)
    if subject_name:
        subject_row = session.query(Subject).filter(Subject.name == subject_name).first()
        if subject_row:
            resolved_subject_id = subject_row.id
        else:
            log.warning(f"[Pipeline] Subject '{subject_name}' not found in subjects table")

    existing = get_document_by_hash(session, file_hash)
    if existing:
        doc_id = existing.id
        # Update metadata in case structuring was re-run
        existing.subject = subject_name
        existing.ai_subject = doc_meta.subject
        existing.subject_id = resolved_subject_id
        existing.summary = doc_meta.summary
        existing.core_topics = core_topics_str
        existing.chapters_json = chapters_json
        existing.total_slides = len(slides)
    else:
        chroma.delete_by_source(filename)
        doc = insert_document(
            session, filename, file_hash,
            subject=subject_name,
            ai_subject=doc_meta.subject,
            subject_id=resolved_subject_id,
            summary=doc_meta.summary,
            core_topics=core_topics_str,
            chapters_json=chapters_json,
            total_slides=len(slides),
        )
        doc_id = doc.id

    # ── Step 5: Upsert slides in SQLite ──────────────────────────────
    slide_ids: list[int] = []
    for s in slides:
        concepts_str = ", ".join(s.concepts)
        slide_obj = upsert_slide(
            session,
            doc_id=doc_id,
            page_number=s.page_number,
            slide_type=s.slide_type,
            exam_signal=s.exam_signal,
            raw_text=s.raw_text,
            summary=s.summary,
            concepts=concepts_str,
            chapter=s.chapter,
            subject=subject_name,
        )
        slide_ids.append(slide_obj.id)

    # ── Step 6: Build embedding texts ────────────────────────────────
    embed_texts: list[str] = []
    for s in slides:
        concepts_str = ", ".join(s.concepts)
        embed_texts.append(build_embed_text(s.summary, concepts_str, s.raw_text))

    # ── Step 7: Generate embeddings ──────────────────────────────────
    log.info(f"[Pipeline] Embedding {len(embed_texts)} slides ...")
    embeddings = embedder.embed_passages(embed_texts)

    # ── Step 8: Upsert into ChromaDB ─────────────────────────────────
    chroma_ids: list[str] = []
    chroma_docs: list[str] = []
    chroma_metas: list[dict] = []

    for s, embed_text in zip(slides, embed_texts):
        chroma_id = f"doc{doc_id}_page{s.page_number}"
        chroma_ids.append(chroma_id)
        chroma_docs.append(embed_text)
        chroma_metas.append({
            "source_file": filename,
            "page_number": s.page_number,
            "slide_type": s.slide_type,
            "concepts": ", ".join(s.concepts),
            "chapter": s.chapter,
            "subject": subject_name,
        })

    chroma.upsert_slides(
        ids=chroma_ids,
        embeddings=embeddings,
        documents=chroma_docs,
        metadatas=chroma_metas,
    )

    # ── Step 9: Mark slides as embedded in SQLite ────────────────────
    mark_slides_embedded(session, slide_ids)

    result["slides_indexed"] = len(slides)
    log.info(f"[Pipeline] DONE '{filename}': {len(slides)} slides indexed")
    return result


def run_indexing(filepath: str | None = None, force: bool = False, subject: str = "") -> list[dict]:
    """
    Run the indexing pipeline.

    Parameters
    ----------
    filepath : str or None
        If given, index only that file.
        If None, index all .md files in KNOWLEDGE_DIR.
    force : bool
        Re-index even if the file hash already exists in SQLite.
    subject : str
        User-assigned subject name (will be uppercased).
        If empty, inferred from file path.

    Returns
    -------
    list[dict] — one result dict per file processed.
    """
    # ── Init shared resources ────────────────────────────────────────
    init_db()
    chroma = ChromaStore()
    embedder = Embedder()

    if filepath:
        files = [filepath]
    else:
        files = sorted(glob.glob(os.path.join(KNOWLEDGE_DIR, "*.md")))

    if not files:
        log.warning("[Pipeline] No markdown files found in knowledge/")
        return []

    log.info(f"[Pipeline] Processing {len(files)} file(s) ...")

    results = []
    for fpath in files:
        # Each file gets its own session → commit/rollback per file
        with get_db() as session:
            result = index_file(fpath, session, chroma, embedder, force=force, subject=subject)
            results.append(result)

    # ── Summary ──────────────────────────────────────────────────
    indexed = sum(r["slides_indexed"] for r in results)
    skipped = sum(1 for r in results if r["cached"])
    log.info(
        f"[Pipeline] Complete — "
        f"{len(results)} files, {indexed} slides indexed, {skipped} cached/skipped"
    )
    log.info(f"[Pipeline] ChromaDB total: {chroma.count()} records")

    return results
