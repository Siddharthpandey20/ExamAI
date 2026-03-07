"""
file_agent.py — File-Level Agent (Ollama/Llama3) using OpenAI Agents SDK.

Uses `output_type` on the Agent so the SDK handles structured parsing
automatically — prompts focus on WHAT to do, not output format.

Three-step flow:
  Step 1: Document overview (chapters + overarching summary)
  Step 2: Map — summarize each chapter with overarching context
  Step 3: Reduce — combine chapter summaries into global summary
"""

import logging

from openai import AsyncOpenAI
from agents import Agent, Runner, ModelSettings, RunConfig
from agents.models.openai_provider import OpenAIProvider
from agents.tracing import trace
from dotenv import load_dotenv

from structuring.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from structuring.schemas import (
    ParsedSlide,
    DocumentOverview,
    ChapterSummary,
    GlobalDocumentSummary,
)
from structuring.md_parser import build_preview_document, get_chapter_slides

load_dotenv()
log = logging.getLogger(__name__)

# ── Ollama provider (OpenAI-compatible) ──────────────────────────────────

_ollama_client = AsyncOpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
_ollama_provider = OpenAIProvider(openai_client=_ollama_client, use_responses=False)
_run_config = RunConfig(model_provider=_ollama_provider)

# ── Step 1: Overview Agent ───────────────────────────────────────────────

overview_agent = Agent(
    name="DocumentOverviewAgent",
    instructions=(
        "You are an academic document analyzer. "
        "Given slide previews from a lecture document, identify the document title, "
        "academic subject, write a 2-3 sentence overarching summary, and group "
        "consecutive slides into chapters. Each chapter should have a name, "
        "slide range (e.g. '1-5'), and key topics. "
        "Only use information present in the slides. Do not hallucinate."
    ),
    model=OLLAMA_MODEL,
    model_settings=ModelSettings(temperature=0.3),
    output_type=DocumentOverview,
)

# ── Step 2: Chapter Summary Agent ────────────────────────────────────────

chapter_agent = Agent(
    name="ChapterSummaryAgent",
    instructions=(
        "You are an academic content summarizer. "
        "You receive an overarching document summary for context, "
        "and the full text of one chapter. "
        "Summarize the chapter in 3-5 sentences, list key concepts, "
        "and flag if it contains numerical examples. "
        "Only summarize what is in the chapter text. Do not hallucinate."
    ),
    model=OLLAMA_MODEL,
    model_settings=ModelSettings(temperature=0.3),
    output_type=ChapterSummary,
)

# ── Step 3: Global Summary Agent ─────────────────────────────────────────

global_summary_agent = Agent(
    name="GlobalSummaryAgent",
    instructions=(
        "You are an academic document summarizer. "
        "Given the document title, subject, and all chapter summaries, "
        "produce a comprehensive global summary that synthesizes everything. "
        "List the core topics across the whole document. "
        "Do not invent content not present in the chapter summaries."
    ),
    model=OLLAMA_MODEL,
    model_settings=ModelSettings(temperature=0.3),
    output_type=GlobalDocumentSummary,
)


# ── Public API ───────────────────────────────────────────────────────────

async def run_file_agent(
    document_title: str, slides: list[ParsedSlide]
) -> tuple[DocumentOverview, GlobalDocumentSummary]:
    # ── Step 1: Document Overview ─────────────────────────────
    with trace("document_overview_step"):
        preview = build_preview_document(slides)
        step1_input = (
            f"Document: {document_title}\n"
            f"Total slides: {len(slides)}\n\n"
            f"--- Slide Previews ---\n{preview}"
        )
        result = await Runner.run(
            overview_agent,
            input=step1_input,
            run_config=_run_config,
        )
        overview: DocumentOverview = result.final_output
    # ── Step 2: Map ───────────────────────────────────────────
    chapter_summaries: list[ChapterSummary] = []
    with trace("chapter_map_phase"):
        for chapter in overview.chapters:
            with trace(f"chapter_{chapter.chapter_name}"):
                chapter_slides = get_chapter_slides(slides, chapter.slide_range)
                if not chapter_slides:
                    continue
                chapter_text = "\n\n".join(
                    f"{s.header}\n{s.content}" for s in chapter_slides
                )
                map_input = (
                    f"Overarching Summary:\n{overview.overarching_summary}\n\n"
                    f"--- Chapter: {chapter.chapter_name} ---\n{chapter_text}"
                )
                result = await Runner.run(
                    chapter_agent,
                    input=map_input,
                    run_config=_run_config,
                )
                chapter_summaries.append(result.final_output)
    # ── Step 3: Reduce ────────────────────────────────────────
    with trace("global_reduce_phase"):
        summaries_text = "\n\n".join(
            f"Chapter: {cs.chapter_name}\nSummary: {cs.summary}\n"
            f"Key Concepts: {', '.join(cs.key_concepts)}"
            for cs in chapter_summaries
        )
        reduce_input = (
            f"Document: {overview.document_title}\n"
            f"Subject: {overview.subject}\n\n"
            f"--- Chapter Summaries ---\n{summaries_text}"
        )
        result = await Runner.run(
            global_summary_agent,
            input=reduce_input,
            run_config=_run_config,
        )
        global_summary: GlobalDocumentSummary = result.final_output
    global_summary.chapter_summaries = chapter_summaries
    global_summary.total_chapters = len(chapter_summaries)
    return overview, global_summary
