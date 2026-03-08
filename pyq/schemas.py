"""
schemas.py — Pydantic models for the PYQ pipeline.

Used as `output_type` by the OpenAI Agents SDK so Llama 3 auto-parses
extracted questions into structured objects.
"""

from pydantic import BaseModel, Field


class ExtractedQuestion(BaseModel):
    """A single clean exam question extracted by the LLM."""
    question_number: int = Field(description="Sequential question number")
    question_text: str = Field(description="The full, clean question text")
    marks: int | None = Field(default=None, description="Marks if mentioned, else null")
    subtopic_hint: str = Field(default="", description="Topic hint if obvious from question context")


class ExtractedQuestionList(BaseModel):
    """Batch response: all questions extracted from a document or page range."""
    source_info: str = Field(default="", description="Brief source identifier, e.g. 'Midterm 2024'")
    questions: list[ExtractedQuestion]


class RRFResult(BaseModel):
    """A single slide result after RRF fusion."""
    slide_id: int
    doc_id: int
    page_number: int
    source_file: str
    rrf_score: float
    dense_rank: int | None = None
    sparse_rank: int | None = None
