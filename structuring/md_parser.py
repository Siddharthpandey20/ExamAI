"""
md_parser.py — Parse knowledge markdown files into structured slide objects.

The knowledge/ markdown files follow a consistent format:
  # Document Title
  _Source: filename.pdf_
  ---
  ## Page N
  <content>
  ### Extracted from Image (OCR)
  <ocr content>
  ### Table N
  <table content>

This module extracts each slide as a ParsedSlide with header, full content,
a short preview (for Ollama context), and flags for tables/OCR.
"""

import re

from structuring.schemas import ParsedSlide
from structuring.config import PREVIEW_CHAR_LIMIT


def _extract_preview(header: str, content: str, max_sentences: int = 3) -> str:
    """
    Build a short preview: header + first N sentences of the content.
    Used to keep Ollama Step-1 calls within context limits.
    """
    # Split into sentences (rough heuristic: period/question/exclamation + space)
    sentences = re.split(r'(?<=[.!?])\s+', content.strip())
    preview_body = " ".join(sentences[:max_sentences])
    return f"{header}\n{preview_body}".strip()


def parse_markdown(filepath: str) -> tuple[str, list[ParsedSlide]]:
    """
    Parse a knowledge markdown file into a document title and list of slides.

    Returns
    -------
    (document_title, slides)
        document_title : str — the # heading of the file
        slides         : list[ParsedSlide]
    """
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    # Extract document title (first # heading)
    title_match = re.match(r"^#\s+(.+)", text, re.MULTILINE)
    document_title = title_match.group(1).strip() if title_match else "Untitled"

    # Split into slide sections on "## Page N" boundaries
    # Each split gives us the content between two ## Page headers
    slide_pattern = re.compile(r"^##\s+Page\s+(\d+)\s*$", re.MULTILINE)
    matches = list(slide_pattern.finditer(text))

    if not matches:
        return document_title, []

    slides: list[ParsedSlide] = []

    for i, match in enumerate(matches):
        slide_number = int(match.group(1))

        # Content runs from end of this header to start of next header (or EOF)
        content_start = match.end()
        content_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        raw_content = text[content_start:content_end].strip()

        # Clean up leading/trailing --- separators
        raw_content = re.sub(r"^---\s*", "", raw_content)
        raw_content = re.sub(r"\s*---\s*$", "", raw_content)

        # Detect sub-section flags
        has_table = bool(re.search(r"^###\s+Table\s+\d+", raw_content, re.MULTILINE))
        has_ocr = bool(re.search(r"^###\s+Extracted from Image", raw_content, re.MULTILINE))

        header = f"## Page {slide_number}"

        # Build the preview for Ollama (header + first few sentences)
        # Strip markdown table syntax and OCR blocks for cleaner preview
        preview_content = re.sub(r"\|.*\|", "", raw_content)  # remove table rows
        preview_content = re.sub(r"###\s+Extracted from Image.*", "", preview_content, flags=re.DOTALL)
        preview_content = re.sub(r"###\s+Table\s+\d+", "[Table present]", preview_content)
        preview_content = preview_content.strip()

        preview = _extract_preview(header, preview_content)

        slides.append(ParsedSlide(
            slide_number=slide_number,
            header=header,
            content=raw_content,
            preview=preview,
            has_table=has_table,
            has_ocr=has_ocr,
            char_count=len(raw_content),
        ))

    return document_title, slides


def build_preview_document(slides: list[ParsedSlide]) -> str:
    """
    Build a condensed preview of the entire document for Ollama Step 1.

    If total content is under PREVIEW_CHAR_LIMIT, returns all slide content.
    Otherwise, returns only headers + first few sentences per slide.
    """
    total_chars = sum(s.char_count for s in slides)

    if total_chars <= PREVIEW_CHAR_LIMIT:
        # Small document — send everything
        parts = [f"{s.header}\n{s.content}" for s in slides]
    else:
        # Large document — send only previews
        parts = [s.preview for s in slides]

    return "\n\n".join(parts)


def get_chapter_slides(
    slides: list[ParsedSlide], slide_range: str
) -> list[ParsedSlide]:
    """
    Given a slide range string like '1-5' or '3-8', return the matching slides.
    Handles single numbers ('5') and ranges ('5-10').
    """
    parts = slide_range.strip().split("-")
    try:
        start = int(parts[0].strip())
        end = int(parts[-1].strip())
    except (ValueError, IndexError):
        return []

    return [s for s in slides if start <= s.slide_number <= end]
