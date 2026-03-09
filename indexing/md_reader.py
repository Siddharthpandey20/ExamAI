"""
md_reader.py — Parse enriched (structured) markdown into slide dicts.

The enriched markdown format produced by the structuring pipeline:

  # Document Title
  ---
  ## Document Overview
  **Subject:** ...
  **Summary:** ...
  **Core Topics:** ...
  **Chapters:**
    - **ChapterName** (slides X-Y): topics
  ---
  ## Page N
  > **Title:** parent_topic | **Type:** slide_type | **Concepts:** c1, c2 | **Exam Signal:** Yes/No
  > **Summary:** summary text
  <original content>

This module extracts:
  - document-level metadata (subject, summary, chapters)
  - per-slide metadata (type, concepts, exam_signal, summary, raw content)
"""

import re
import logging

log = logging.getLogger(__name__)


# ── Data containers ──────────────────────────────────────────────────────

class DocMeta:
    """Document-level metadata extracted from the overview block."""
    def __init__(self):
        self.title: str = ""
        self.subject: str = ""
        self.summary: str = ""
        self.core_topics: list[str] = []
        self.chapters: list[dict] = []       # [{name, slide_range, topics}]


class SlideMeta:
    """Per-slide metadata + content extracted from the enriched markdown."""
    def __init__(self):
        self.page_number: int = 0
        self.parent_topic: str = ""
        self.slide_type: str = "other"
        self.concepts: list[str] = []
        self.exam_signal: bool = False
        self.summary: str = ""
        self.raw_text: str = ""
        self.chapter: str = ""              


# ── Parser ───────────────────────────────────────────────────────────────

def _parse_overview(text: str) -> DocMeta:
    """Extract the Document Overview block."""
    meta = DocMeta()

    # Title — first # heading
    m = re.match(r"^#\s+(.+)", text, re.MULTILINE)
    if m:
        meta.title = m.group(1).strip()

    # Subject
    m = re.search(r"\*\*Subject:\*\*\s*(.+)", text)
    if m:
        meta.subject = m.group(1).strip()

    # Summary (document-level)
    m = re.search(r"\*\*Summary:\*\*\s*(.+?)(?=\n\n|\n\*\*)", text, re.DOTALL)
    if m:
        meta.summary = m.group(1).strip()

    # Core Topics
    m = re.search(r"\*\*Core Topics:\*\*\s*(.+)", text)
    if m:
        meta.core_topics = [t.strip() for t in m.group(1).split(",") if t.strip()]

    # Chapters — handle both "(slides 1-5)" and "(slides Page 1-5)" formats
    for cm in re.finditer(
        r"-\s+\*\*(.+?)\*\*\s+\(slides\s+(.+?)\):\s*(.+)",
        text,
    ):
        raw_range = cm.group(2).strip()
        # Normalize: strip "Page " prefix if present
        raw_range = re.sub(r"(?i)^page\s+", "", raw_range)
        meta.chapters.append({
            "name": cm.group(1).strip(),
            "slide_range": raw_range,
            "topics": cm.group(3).strip(),
        })

    return meta


def _resolve_chapter(page_number: int, chapters: list[dict]) -> str:
    """Find which chapter a slide belongs to based on slide ranges."""
    for ch in chapters:
        # Parse ranges like "1-5" or "1-6" or "7, 12, 16, 19, 28" or "Page 1-5"
        range_str = ch["slide_range"]
        # Strip "Page " prefix if present
        range_str = re.sub(r"(?i)^page\s+", "", range_str)
        for part in range_str.split(","):
            part = part.strip()
            # Strip any remaining "Page " in individual parts
            part = re.sub(r"(?i)^page\s+", "", part)
            if not part:
                continue
            try:
                if "-" in part:
                    lo, hi = part.split("-", 1)
                    if int(lo.strip()) <= page_number <= int(hi.strip()):
                        return ch["name"]
                else:
                    if page_number == int(part):
                        return ch["name"]
            except ValueError:
                continue
    return ""


def _parse_slide_metadata_line(line: str) -> dict:
    """
    Parse the blockquote metadata line:
      > **Title:** ... | **Type:** ... | **Concepts:** ... | **Exam Signal:** Yes/No
    """
    result = {}

    m = re.search(r"\*\*Title:\*\*\s*(.+?)\s*\|", line)
    if m:
        result["parent_topic"] = m.group(1).strip()

    m = re.search(r"\*\*Type:\*\*\s*(.+?)\s*\|", line)
    if m:
        result["slide_type"] = m.group(1).strip()

    m = re.search(r"\*\*Concepts:\*\*\s*(.+?)\s*\|", line)
    if m:
        raw = m.group(1).strip()
        result["concepts"] = [c.strip() for c in raw.split(",") if c.strip() and c.strip() != "—"]

    m = re.search(r"\*\*Chapter:\*\*\s*(.+?)\s*\|", line)
    if m:
        result["chapter"] = m.group(1).strip()

    m = re.search(r"\*\*Exam Signal:\*\*\s*(\w+)", line)
    if m:
        result["exam_signal"] = m.group(1).strip().lower() == "yes"

    return result


def _parse_slide_summary_line(line: str) -> str:
    """Extract the summary from: > **Summary:** ..."""
    m = re.search(r"\*\*Summary:\*\*\s*(.+)", line)
    return m.group(1).strip() if m else ""


def parse_structured_markdown(filepath: str) -> tuple[DocMeta, list[SlideMeta]]:
    """
    Parse a fully enriched knowledge markdown file.

    Returns
    -------
    (doc_meta, slides)
        doc_meta : DocMeta   — document-level metadata
        slides   : list[SlideMeta] — per-slide data ready for indexing
    """
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    doc_meta = _parse_overview(text)

    # Split into slide blocks on "## Page N"
    slide_pattern = re.compile(r"^##\s+Page\s+(\d+)\s*$", re.MULTILINE)
    matches = list(slide_pattern.finditer(text))

    slides: list[SlideMeta] = []

    for i, match in enumerate(matches):
        page_num = int(match.group(1))
        content_start = match.end()
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[content_start:content_end].strip()

        # Remove trailing --- separator
        block = re.sub(r"\s*---\s*$", "", block)

        slide = SlideMeta()
        slide.page_number = page_num

        # Parse metadata blockquote lines (lines starting with >)
        lines = block.split("\n")
        content_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(">") and "**Title:**" in stripped:
                meta = _parse_slide_metadata_line(stripped)
                slide.parent_topic = meta.get("parent_topic", "")
                slide.slide_type = meta.get("slide_type", "other")
                slide.concepts = meta.get("concepts", [])
                slide.exam_signal = meta.get("exam_signal", False)
                slide.chapter = meta.get("chapter", "")
            elif stripped.startswith(">") and "**Summary:**" in stripped:
                slide.summary = _parse_slide_summary_line(stripped)
            else:
                content_lines.append(line)

        # Fallback: resolve chapter from document-level chapter ranges
        # if the per-slide metadata didn't provide one
        if not slide.chapter:
            slide.chapter = _resolve_chapter(page_num, doc_meta.chapters)

        slide.raw_text = "\n".join(content_lines).strip()
        slides.append(slide)

    log.info(f"[Reader] Parsed {filepath}: {len(slides)} slides, {len(doc_meta.chapters)} chapters")
    return doc_meta, slides
