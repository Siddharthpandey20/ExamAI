"""
md_writer.py — Assemble cleaned page content into a single Markdown file.

Takes the structured output from the pipeline and writes one .md file
per source document into the knowledge/ directory.

Handles:
  - AI-cleaned native text
  - OCR text (kept separate, not duplicated)
  - Tables (as markdown tables)
  - Diagram pages (flagged with note)
"""

import os
import re

from ingestion.config import KNOWLEDGE_DIR

# Patterns for garbage tokens to strip (line-level)
_GARBAGE_LINE_PATTERNS = [
    re.compile(r"^[0-9 ]+$"),          # lines with only digits and spaces
    re.compile(r"^[A-F0-9]{6,}$"),     # hex strings like EFFFFFFE
    re.compile(r"^\*+$"),              # lines of only asterisks
]


def _clean_garbage_lines(text: str) -> str:
    """Remove lines that match known OCR garbage patterns."""
    cleaned = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and any(p.match(stripped) for p in _GARBAGE_LINE_PATTERNS):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _clean_cell(val: str) -> str:
    """Clean a single table cell value."""
    stripped = val.strip()
    if any(p.match(stripped) for p in _GARBAGE_LINE_PATTERNS):
        return ""
    return stripped


def _format_table_md(table: list[list[str]]) -> str:
    """Convert a table (list of rows) into a Markdown table string."""
    if not table:
        return ""

    # Normalize column count to max row width
    max_cols = max(len(row) for row in table) if table else 0
    if max_cols == 0:
        return ""

    lines = []
    # Header row
    header = table[0]
    header = header + [""] * (max_cols - len(header))
    lines.append("| " + " | ".join(_clean_cell(str(c)) for c in header) + " |")
    lines.append("| " + " | ".join("---" for _ in range(max_cols)) + " |")
    # Data rows
    for row in table[1:]:
        padded = row + [""] * (max_cols - len(row))
        lines.append("| " + " | ".join(_clean_cell(str(c)) for c in padded[:max_cols]) + " |")

    return "\n".join(lines)


def build_markdown(filename: str, pages: list[dict]) -> str:
    """
    Build a complete Markdown document from processed page data.

    Each page dict has:
        - page_num: int
        - cleaned_text: str    (AI-cleaned native text)
        - ocr_text: str        (OCR results — kept separate)
        - tables: list         (list of table data — already structured)
        - is_diagram: bool     (True if page is diagram-only)
    """
    lines = []
    stem = os.path.splitext(filename)[0]
    lines.append(f"# {stem}\n")
    lines.append(f"_Source: {filename}_\n")

    for page in pages:
        pnum = page["page_num"]
        lines.append(f"\n---\n\n## Page {pnum}\n")

        # Diagram-only page
        if page.get("is_diagram", False):
            lines.append("> **[Diagram/Figure]** This page contains a visual diagram "
                         "or figure without extractable text.\n")
            continue

        # AI-cleaned native text
        text = _clean_garbage_lines(page.get("cleaned_text", "")).strip()
        if text:
            lines.append(text)
            lines.append("")

        # Tables (from Camelot, PPTX parser, or OCR reconstruction)
        tables = page.get("tables", [])
        for i, table in enumerate(tables, start=1):
            lines.append(f"### Table {i}\n")
            lines.append(_format_table_md(table))
            lines.append("")

        # OCR text — only if there's actual content AND no tables already cover it
        ocr = _clean_garbage_lines(page.get("ocr_text", "")).strip()
        if ocr and not tables:
            lines.append("### Extracted from Image (OCR)\n")
            lines.append(ocr)
            lines.append("")

    return "\n".join(lines)


def write_markdown(filename: str, pages: list[dict]) -> str:
    """
    Build markdown and write it to knowledge/<stem>.md.
    Returns the output file path.
    """
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

    md_content = build_markdown(filename, pages)
    stem = os.path.splitext(filename)[0]
    out_path = os.path.join(KNOWLEDGE_DIR, f"{stem}.md")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    return out_path
