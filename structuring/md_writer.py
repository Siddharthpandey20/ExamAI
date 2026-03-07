"""
md_writer.py — Write enriched structured markdown back into the knowledge file.

Takes the original parsed slides + slide metadata from Agent 2 and
rewrites the markdown with metadata headers injected into each slide:

  ## Page N
  > **Title:** parent_topic | **Type:** slide_type | **Concepts:** c1, c2 | **Exam Signal:** Yes/No
  > **Summary:** 1-2 sentence clean summary

  <original slide content>

This keeps everything in markdown — no JSON output files.
"""

import os
import re
import logging

from structuring.schemas import ParsedSlide, SlideMetadata, DocumentOverview, GlobalDocumentSummary

log = logging.getLogger(__name__)


def _build_metadata_block(meta: SlideMetadata) -> str:
    """Build the metadata blockquote for one slide."""
    concepts = ", ".join(meta.core_concepts) if meta.core_concepts else "—"
    exam = "Yes" if meta.exam_signals else "No"

    return (
        f"> **Title:** {meta.parent_topic} | "
        f"**Type:** {meta.slide_type.value} | "
        f"**Concepts:** {concepts} | "
        f"**Exam Signal:** {exam}\n"
        f"> **Summary:** {meta.slide_summary}"
    )


def _build_document_header(
    overview: DocumentOverview,
    global_summary: GlobalDocumentSummary,
) -> str:
    """Build the document-level summary block at the top of the file."""
    chapters_list = "\n".join(
        f"  - **{ch.chapter_name}** (slides {ch.slide_range}): {', '.join(ch.key_topics)}"
        for ch in overview.chapters
    )

    return (
        f"## Document Overview\n\n"
        f"**Subject:** {overview.subject}\n\n"
        f"**Summary:** {global_summary.global_summary}\n\n"
        f"**Core Topics:** {', '.join(global_summary.core_topics)}\n\n"
        f"**Chapters:**\n{chapters_list}\n"
    )


def write_structured_markdown(
    filepath: str,
    overview: DocumentOverview,
    global_summary: GlobalDocumentSummary,
    slides: list[ParsedSlide],
    slide_metadata: list[SlideMetadata],
) -> str:
    """
    Rewrite the knowledge markdown file with metadata injected per slide.

    The original file is overwritten with:
      1. Document title + source line (preserved)
      2. Document Overview block (new)
      3. Each slide with metadata blockquote + original content

    Returns the path to the written file.
    """
    # Build metadata lookup: slide_number → SlideMetadata
    meta_map: dict[int, SlideMetadata] = {m.slide_number: m for m in slide_metadata}

    # Read original to preserve the title and source line
    with open(filepath, "r", encoding="utf-8") as f:
        original = f.read()

    # Extract the title block (everything before first ## Page)
    title_match = re.search(r"^(#\s+.+\n(?:_Source:.+_\n)?)", original, re.MULTILINE)
    title_block = title_match.group(1).strip() if title_match else f"# {overview.document_title}"

    # ── Build output ─────────────────────────────────────────────────
    parts: list[str] = []

    # Title
    parts.append(title_block)
    parts.append("")

    # Document overview
    parts.append("---")
    parts.append("")
    parts.append(_build_document_header(overview, global_summary))
    parts.append("")

    # Each slide
    for slide in slides:
        parts.append("---")
        parts.append("")
        parts.append(slide.header)
        parts.append("")

        # Inject metadata if available
        meta = meta_map.get(slide.slide_number)
        if meta:
            parts.append(_build_metadata_block(meta))
            parts.append("")

        # Original content
        parts.append(slide.content)
        parts.append("")

    output_text = "\n".join(parts)

    # Write back to the same file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(output_text)

    log.info(f"[Writer] Structured markdown written to {filepath}")
    return filepath
