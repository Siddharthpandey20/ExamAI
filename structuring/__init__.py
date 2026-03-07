"""
Structuring Module — ExamPrep AI

Anchor file that orchestrates the two-agent pipeline:
  Agent 1 (Ollama/Llama3)  → File-level: document overview + map-reduce summaries
  Agent 2 (Gemini Flash)   → Slide-level: per-slide classification and metadata

Scans knowledge/ for unprocessed markdown files, runs both agents,
and saves structured JSON output to structured_output/.

Usage:
    # From central system:
    from structuring import run_structuring
    results = run_structuring()

    # Process a specific file:
    from structuring import run_structuring
    results = run_structuring("knowledge/3.md")

    # Standalone:
    python -m structuring
    python -m structuring knowledge/3.md
"""

import os
import json
import glob
import logging

from structuring.config import KNOWLEDGE_DIR, STRUCTURED_DIR
from structuring.tracker import is_structured, mark_structured
from structuring.md_parser import parse_markdown
from structuring.file_agent import step1_document_overview, step2_map_reduce
from structuring.slide_agent import classify_all_slides
from structuring.schemas import FileStructuredOutput

log = logging.getLogger(__name__)


def _find_pending_files() -> list[str]:
    """Return markdown files in knowledge/ that haven't been structured yet."""
    pattern = os.path.join(KNOWLEDGE_DIR, "*.md")
    all_md = sorted(glob.glob(pattern))
    return [f for f in all_md if not is_structured(os.path.basename(f))]


def _save_output(output: FileStructuredOutput, source_name: str) -> str:
    """Save the structured output as JSON. Returns the output path."""
    os.makedirs(STRUCTURED_DIR, exist_ok=True)
    out_name = os.path.splitext(source_name)[0] + ".json"
    out_path = os.path.join(STRUCTURED_DIR, out_name)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output.model_dump(), f, indent=2, ensure_ascii=False)

    return out_path


def process_file(filepath: str) -> str | None:
    """
    Run the full two-agent pipeline on a single knowledge markdown file.

    Returns the path to the structured JSON output, or None on failure.
    """
    fname = os.path.basename(filepath)
    log.info(f"{'='*60}")
    log.info(f"[START] Structuring: {fname}")
    log.info(f"{'='*60}")

    # ── Parse the markdown ───────────────────────────────────────────
    log.info("[Parse] Extracting slides from markdown...")
    doc_title, slides = parse_markdown(filepath)

    if not slides:
        log.warning(f"[Skip] No slides found in {fname}")
        return None

    log.info(f"[Parse] Found {len(slides)} slides in '{doc_title}'")

    # ── Agent 1: File-Level (Ollama) ─────────────────────────────────
    log.info("[Agent 1] File-level analysis with Ollama...")

    # Step 1: Document Overview
    log.info("[Agent 1 / Step 1] Generating document overview...")
    overview = step1_document_overview(doc_title, slides)
    log.info(f"[Agent 1 / Step 1] Done — {len(overview.chapters)} chapters detected")

    # Step 2: Map-Reduce Summaries
    log.info("[Agent 1 / Step 2] Map-Reduce chapter summaries...")
    global_summary = step2_map_reduce(overview, slides)
    log.info(f"[Agent 1 / Step 2] Done — global summary ready")

    # ── Handoff: Agent 1 → Agent 2 ──────────────────────────────────
    log.info("[Handoff] Passing document context to Gemini slide agent...")

    # ── Agent 2: Slide-Level (Gemini) ────────────────────────────────
    log.info("[Agent 2] Slide-level classification with Gemini...")
    slide_metadata = classify_all_slides(overview, slides)
    log.info(f"[Agent 2] Done — {len(slide_metadata)} slides classified")

    # ── Assemble final output ────────────────────────────────────────
    output = FileStructuredOutput(
        source_file=fname,
        document_overview=overview,
        global_summary=global_summary,
        slides=slide_metadata,
    )

    out_path = _save_output(output, fname)
    log.info(f"[DONE] Output saved to {out_path}")
    return out_path


def run_structuring(source: str | None = None) -> list[str]:
    """
    Main entry point for the structuring module.

    Parameters
    ----------
    source : str or None
        - Path to a single .md file  → structure just that file
        - None                       → structure all pending files in knowledge/

    Returns
    -------
    list[str]
        Paths to generated structured JSON files.
    """
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    os.makedirs(STRUCTURED_DIR, exist_ok=True)

    # Determine files to process
    if source and os.path.isfile(source):
        files = [os.path.abspath(source)]
    else:
        files = _find_pending_files()

    if not files:
        log.info("[INFO] No unprocessed knowledge files found.")
        print("[INFO] No unprocessed knowledge files found.")
        return []

    print(f"[INFO] {len(files)} file(s) pending structuring.\n")
    results: list[str] = []

    for filepath in files:
        fname = os.path.basename(filepath)
        try:
            out_path = process_file(filepath)
            if out_path:
                mark_structured(fname, out_path)
                results.append(out_path)
                print(f"[OK] {fname} → {out_path}")
            else:
                print(f"[SKIP] {fname} — no slides found")
        except Exception as e:
            log.error(f"[FAIL] {fname}: {e}", exc_info=True)
            print(f"[FAIL] {fname} — {e}")

    print(f"\n[DONE] {len(results)}/{len(files)} files structured successfully.")
    return results
