"""
schemas.py — Pydantic models for all structured data in the structuring pipeline.

Two levels of output:
  1. File-Level  (Ollama/Llama3)  → DocumentOverview, ChapterSummary, GlobalSummary
  2. Slide-Level (Gemini Flash)   → SlideMetadata per slide
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────

class SlideType(str, Enum):
    DEFINITION = "definition"
    SYNTAX_CODE = "syntax/code"
    COMPARISON = "comparison"
    NUMERICAL_EXAMPLE = "numerical_example"
    DIAGRAM_EXPLANATION = "diagram_explanation"
    SUMMARY = "summary"
    CONCEPT = "concept"
    EXAMPLE = "example"
    TABLE = "table"
    OTHER = "other"


# ── Markdown Parser Output ───────────────────────────────────────────────

class ParsedSlide(BaseModel):
    """Raw slide extracted from a knowledge markdown file."""
    slide_number: int = Field(description="Page/slide number from the markdown")
    header: str = Field(description="The ## heading text of the slide")
    content: str = Field(description="Full text content of the slide")
    preview: str = Field(description="Header + first 2-3 sentences (for context-limited calls)")
    has_table: bool = Field(default=False, description="Whether the slide contains a table")
    has_ocr: bool = Field(default=False, description="Whether the slide has OCR-extracted text")
    char_count: int = Field(default=0, description="Total character count of slide content")


# ── File-Level Agent (Ollama) — Step 1 ───────────────────────────────────

class ChapterInfo(BaseModel):
    """A detected chapter/topic grouping from the document."""
    chapter_name: str = Field(description="Name of the chapter or topic")
    slide_range: str = Field(description="Slide range, e.g. '1-5' or '6-12'")
    key_topics: list[str] = Field(description="Main topics covered in this chapter")


class DocumentOverview(BaseModel):
    """Step 1 output: high-level document structure from Ollama."""
    document_title: str = Field(description="Title of the document")
    subject: str = Field(description="Academic subject this belongs to")
    overarching_summary: str = Field(description="2-3 sentence summary of the entire document")
    chapters: list[ChapterInfo] = Field(description="Detected chapter groupings")
    total_slides: int = Field(description="Total number of slides in the document")


# ── File-Level Agent (Ollama) — Step 2 (Map-Reduce) ──────────────────────

class ChapterSummary(BaseModel):
    """Map step output: summary of a single chapter."""
    chapter_name: str = Field(description="Name of the chapter")
    summary: str = Field(description="3-5 sentence summary of the chapter content")
    key_concepts: list[str] = Field(description="Important concepts in this chapter")
    has_numerical_examples: bool = Field(default=False, description="Whether chapter has numerical problems")


class GlobalDocumentSummary(BaseModel):
    """Reduce step output: final document-level summary combining all chapters."""
    document_title: str = Field(description="Title of the document")
    subject: str = Field(description="Academic subject")
    global_summary: str = Field(description="Comprehensive summary of the entire document")
    chapter_summaries: list[ChapterSummary] = Field(description="Summary per chapter")
    core_topics: list[str] = Field(description="Top-level topics across the whole document")
    total_chapters: int = Field(description="Number of chapters detected")


# ── Slide-Level Agent (Gemini) ───────────────────────────────────────────

class SlideMetadata(BaseModel):
    """Structured metadata for a single slide, extracted by Gemini."""
    slide_number: int = Field(description="Page/slide number")
    parent_topic: str = Field(description="The chapter or parent topic this slide belongs to")
    slide_type: SlideType = Field(description="Classification of the slide content")
    core_concepts: list[str] = Field(description="Key concepts present on this slide")
    exam_signals: bool = Field(
        default=False,
        description="True if slide has exam-importance hints (Summary, Comparison, Note, Important, etc.)"
    )
    slide_summary: str = Field(description="1-2 sentence clean summary of the slide")


class SlideBatchResponse(BaseModel):
    """Response from Gemini for a batch of 10-15 slides."""
    slides: list[SlideMetadata] = Field(description="Structured metadata for each slide in the batch")


# ── Final Combined Output ────────────────────────────────────────────────

class FileStructuredOutput(BaseModel):
    """Complete structured output for one knowledge markdown file."""
    source_file: str = Field(description="Name of the source markdown file")
    document_overview: DocumentOverview = Field(description="Step 1: high-level structure")
    global_summary: GlobalDocumentSummary = Field(description="Step 2: map-reduce summary")
    slides: list[SlideMetadata] = Field(description="Per-slide structured metadata")
