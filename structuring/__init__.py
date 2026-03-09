"""
Structuring Module — ExamPrep AI

Async agentic orchestrator with true Agent 1 → Agent 2 handoff:

  Agent 1 (Ollama/Llama3):
    Step 1: Document overview (chapters, summary)
    Step 2: Map-Reduce chapter summaries
    → Produces: DocumentOverview + GlobalDocumentSummary

  HANDOFF: Agent 1 output is programmatically injected into Agent 2's
           system prompt as context.

  Agent 2 (Groq):
    Slide-level classification in sliding-window batches (12 slides/call)
    Rate-limited to 20 calls/min
    → Produces: SlideMetadata per slide

  Writer:
    Enriches the original knowledge markdown with metadata per slide.
    Output stays as markdown — no JSON files.

Usage:
    from structuring import run_structuring
    import asyncio
    results = asyncio.run(run_structuring())
    results = asyncio.run(run_structuring("knowledge/3.md"))

CLI:
    python -m structuring
    python -m structuring knowledge/3.md
"""

import os
import glob
import logging

from structuring.config import KNOWLEDGE_DIR
from structuring.tracker import is_structured, mark_structured
from structuring.md_parser import parse_markdown
from structuring.file_agent import run_file_agent
from structuring.slide_agent import run_slide_agent
from structuring.md_writer import write_structured_markdown

from agents import trace, custom_span

log = logging.getLogger(__name__)


def _find_pending_files() -> list[str]:
    """Return knowledge markdown files that haven't been structured yet."""
    pattern = os.path.join(KNOWLEDGE_DIR, "*.md")
    all_md = sorted(glob.glob(pattern))
    return [f for f in all_md if not is_structured(os.path.basename(f))]


async def process_file(filepath: str) -> str | None:
    """
    Run the full two-agent pipeline on a single knowledge markdown file.

    Flow:
      1. Parse markdown into slides
      2. Agent 1 (Ollama): document overview + map-reduce summaries
      3. Agent 2 (Groq): slide-level classification (with Agent 1 context)
      4. Writer: enrich the markdown with metadata per slide

    Returns the path to the structured markdown, or None on failure.
    """
    fname = os.path.basename(filepath)
    log.info(f"{'='*60}")
    log.info(f"[START] Structuring: {fname}")
    log.info(f"{'='*60}")

    with trace("structuring_pipeline"):
        # ── Parse ────────────────────────────────────────────────────────
        with custom_span("parse"):
            doc_title, slides = parse_markdown(filepath)
            if not slides:
                log.warning(f"[Skip] No slides in {fname}")
                return None
            log.info(f"[Parse] {len(slides)} slides in '{doc_title}'")

        # ── Agent 1: File-Level (Ollama) ─────────────────────────────────
        log.info("[Agent 1] Starting file-level analysis (Ollama)...")
        overview, global_summary = await run_file_agent(doc_title, slides)

        # ── HANDOFF: Agent 1 → Agent 2 ──────────────────────────────────
        log.info("[Handoff] Injecting file context into slide agent...")

        # ── Agent 2: Slide-Level (Groq) ─────────────────────────────────
        log.info("[Agent 2] Starting slide classification (Groq)...")
        slide_metadata = await run_slide_agent(overview, slides)
        log.info(f"[Agent 2] {len(slide_metadata)} slides classified")

        # ── Write structured markdown ────────────────────────────────────
        with custom_span("write_output"):
            log.info("[Writer] Writing enriched markdown...")
            out_path = write_structured_markdown(
                filepath, overview, global_summary, slides, slide_metadata
            )

    log.info(f"[DONE] {fname} structured → {out_path}")
    return out_path


async def run_structuring(source: str | None = None) -> list[str]:
    """
    Main entry point. Async.

    Parameters
    ----------
    source : str or None
        Path to a single .md file, or None to process all pending files.

    Returns
    -------
    list[str]
        Paths to structured markdown files.
    """
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

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
            out_path = await process_file(filepath)
            if out_path:
                mark_structured(fname, out_path)
                results.append(out_path)
                print(f"[OK] {fname} → structured markdown updated")
            else:
                print(f"[SKIP] {fname} — no slides found")
        except Exception as e:
            log.error(f"[FAIL] {fname}: {e}", exc_info=True)
            print(f"[FAIL] {fname} — {e}")

    print(f"\n[DONE] {len(results)}/{len(files)} files structured.")
    return results
