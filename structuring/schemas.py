"""
schemas.py — Pydantic models for the structuring pipeline.

Used as `output_type` by the OpenAI Agents SDK so the LLM auto-parses
into these models — no bloated JSON-instruction prompts needed.

Two agent levels:
  1. File-Level  (Ollama)  → DocumentOverview, ChapterSummary, GlobalSummary
  2. Slide-Level (Gemini)    → SlideMetadata per slide
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


# ── Markdown Parser (internal only) ──────────────────────────────────────

class ParsedSlide(BaseModel):
    """Raw slide extracted from a knowledge markdown file."""
    slide_number: int
    header: str
    content: str
    preview: str
    has_table: bool = False
    has_ocr: bool = False
    char_count: int = 0


# ── File-Level Agent outputs ─────────────────────────────────────────────

class ChapterInfo(BaseModel):
    chapter_name: str = Field(description="Name of the chapter or topic")
    slide_range: str = Field(description="e.g. '1-5' or '6-12'")
    key_topics: list[str] = Field(description="Main topics in this chapter")


class ChunkOverview(BaseModel):
    """Stage 1 output: local overview for a chunk of 30-40 slides."""
    chunk_id: int = Field(description="Sequential chunk number starting from 1")
    local_topics: list[str] = Field(description="Main topics found in this chunk")
    local_chapters: list[ChapterInfo] = Field(description="Chapters found in this chunk")
    topic_keywords: list[str] = Field(description="Important keywords from this chunk")
    slide_range_local: str = Field(description="e.g. '1-35' — the slide range this chunk covers")
    chunk_summary: str = Field(description="2-3 sentence summary of this chunk")


class DocumentOverview(BaseModel):
    """Agent 1 Step 1: high-level document structure."""
    document_title: str
    subject: str
    overarching_summary: str = Field(description="2-3 sentence summary of the entire document")
    chapters: list[ChapterInfo]
    total_slides: int
    ai_subject: str = Field(description="AI-extracted subject, may differ from filename or user input")


class ChapterSummary(BaseModel):
    """Agent 1 Map step: summary of a single chapter."""
    chapter_name: str
    summary: str = Field(description="3-5 sentence summary")
    key_concepts: list[str]
    has_numerical_examples: bool = False


class GlobalDocumentSummary(BaseModel):
    """Agent 1 Reduce step: final combined summary."""
    document_title: str
    subject: str
    global_summary: str
    chapter_summaries: list[ChapterSummary]
    core_topics: list[str]
    total_chapters: int


# ── Slide-Level Agent outputs ────────────────────────────────────────────

class SlideMetadata(BaseModel):
    """Per-slide classification from Agent 2."""
    slide_number: int
    parent_topic: str
    slide_type: SlideType
    core_concepts: list[str]
    exam_signals: bool = Field(
        default=False,
        description="True if slide has exam hints: Summary, Comparison, Note, Important, Remember"
    )
    slide_summary: str = Field(description="1-2 sentence clean summary")
    chapter: str = Field(description="Chapter name as per the content and similar to DocumentOverview")


class SlideBatchResponse(BaseModel):
    """Batch response for the sliding-window pattern."""
    slides: list[SlideMetadata]
