"""
file_agent.py — File-Level Agent (Ollama/Llama3) using OpenAI Agents SDK.

Uses `output_type` on the Agent so the SDK handles structured parsing
automatically — prompts focus on WHAT to do, not output format.

Four-step flow:
  Step 1a: Chunk overview — split slides into chunks, run local overview per chunk (parallel)
  Step 1b: Merge overview — combine chunk overviews into final DocumentOverview
  Step 2:  Map  — summarize each chapter with overarching context (parallel, semaphore-limited)
  Step 3:  Reduce — combine chapter summaries into global summary
"""

import asyncio
import logging
import math
import re

from openai import AsyncOpenAI
from agents import Agent, Runner, ModelSettings, RunConfig
from agents.models.openai_provider import OpenAIProvider
from agents import custom_span
from dotenv import load_dotenv

from structuring.config import (
    OLLAMA_BASE_URL, OLLAMA_MODEL,
    OVERVIEW_CHUNK_SIZE, OLLAMA_MAX_CONCURRENCY,
)
from structuring.schemas import (
    ParsedSlide,
    ChapterInfo,
    ChunkOverview,
    DocumentOverview,
    ChapterSummary,
    GlobalDocumentSummary,
)
from structuring.md_parser import build_preview_document, get_chapter_slides, clean_for_llm

load_dotenv()
log = logging.getLogger(__name__)

# ── Ollama provider (OpenAI-compatible) ──────────────────────────────────

_ollama_client = AsyncOpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
_ollama_provider = OpenAIProvider(openai_client=_ollama_client, use_responses=False)
_run_config = RunConfig(model_provider=_ollama_provider)

# Semaphore to limit concurrent Ollama calls (avoid overloading local GPU)
_ollama_sem = asyncio.Semaphore(OLLAMA_MAX_CONCURRENCY)


# ── Stage 1a: Chunk Overview Agent ───────────────────────────────────────

chunk_overview_agent = Agent(
    name="ChunkOverviewAgent",
    instructions=(
        "You are an academic document analyzer. "
        "You receive a CHUNK of slide previews from a larger lecture document. "
        "Analyze ONLY these slides and produce:\n"
        "- local_topics: the main topics found in this chunk\n"
        "- local_chapters: group the slides in this chunk into chapters. "
        "Each chapter has a name, slide_range, and key_topics.\n"
        "- topic_keywords: important keywords from this chunk\n"
        "- chunk_summary: a 2-3 sentence summary of this chunk\n\n"
        "CRITICAL RULES:\n"
        "- slide_range must be ONLY numbers and dashes, e.g. '27-35'. "
        "Do NOT include the word 'Page'.\n"
        "- Your chapters MUST cover ALL slides in this chunk with NO GAPS. "
        "The chunk slide range is given — every slide in that range must belong to a chapter.\n"
        "- Only use information present in the slides. Do not hallucinate."
    ),
    model=OLLAMA_MODEL,
    model_settings=ModelSettings(temperature=0.3),
    output_type=ChunkOverview,
)

# ── Stage 1b: Merge Overview Agent ───────────────────────────────────────

merge_overview_agent = Agent(
    name="MergeOverviewAgent",
    instructions=(
        "You are an academic document analyzer performing a MERGE step. "
        "You receive chunk summaries from different parts of a lecture document. "
        "Each chunk has local chapters and topics. Your job is to produce the FINAL "
        "document overview by merging these chunks into a coherent chapter structure.\n\n"
        "You MUST:\n"
        "- Combine or rename chapters that clearly cover the same topic across chunks.\n"
        "- Produce a single list of chapters that covers ALL slides from 1 to total_slides.\n"
        "- Write a 2-3 sentence overarching summary of the entire document.\n"
        "- Identify the document subject and title.\n\n"
        "CRITICAL RULES:\n"
        "- slide_range must be ONLY numbers and dashes, e.g. '1-12' or '13-26'. "
        "Do NOT include the word 'Page'.\n"
        "- Chapters MUST cover ALL slides from 1 to total_slides with NO GAPS and NO OVERLAPS.\n"
        "- Only use information present in the chunk summaries. Do not hallucinate."
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


# ── Helpers ──────────────────────────────────────────────────────────────

def _parse_slide_range(range_str: str) -> set[int]:
    """Parse a slide_range string like '1-5, 8-12' into a set of ints."""
    nums = set()
    cleaned = re.sub(r"(?i)^page\s+", "", range_str.strip())
    for part in cleaned.split(","):
        part = part.strip()
        part = re.sub(r"(?i)^page\s+", "", part)
        if not part:
            continue
        try:
            if "-" in part:
                lo, hi = part.split("-", 1)
                nums.update(range(int(lo.strip()), int(hi.strip()) + 1))
            elif part.isdigit():
                nums.add(int(part))
        except ValueError:
            continue
    return nums


def _build_gap_chapters(missing: set[int]) -> list[ChapterInfo]:
    """Build 'Additional Topics' chapters for uncovered slides."""
    if not missing:
        return []
    missing_sorted = sorted(missing)
    range_parts = []
    start = missing_sorted[0]
    end = start
    for n in missing_sorted[1:]:
        if n == end + 1:
            end = n
        else:
            range_parts.append(f"{start}-{end}" if start != end else str(start))
            start = n
            end = n
    range_parts.append(f"{start}-{end}" if start != end else str(start))
    return [ChapterInfo(
        chapter_name="Additional Topics",
        slide_range=", ".join(range_parts),
        key_topics=["continuation", "additional material"],
    )]


def _normalize_chapters(chapters: list[ChapterInfo]) -> list[ChapterInfo]:
    """Strip 'Page ' prefixes from all chapter slide_range values."""
    for ch in chapters:
        ch.slide_range = re.sub(r"(?i)^page\s+", "", ch.slide_range).strip()
    return chapters


# ── Public API ───────────────────────────────────────────────────────────

async def run_file_agent(
    document_title: str, slides: list[ParsedSlide]
) -> tuple[DocumentOverview, GlobalDocumentSummary]:
    total_slides = len(slides)
    with custom_span("file_agent"):
        # ════════════════════════════════════════════════════════════════
        # Step 1: Two-stage overview
        # ════════════════════════════════════════════════════════════════

        with custom_span("overview_phase"):
            overview = await _two_stage_overview(document_title, slides, total_slides)

        # ════════════════════════════════════════════════════════════════
        # Step 2: Map — parallel chapter summaries (semaphore-limited)
        # ════════════════════════════════════════════════════════════════

        with custom_span("chapter_map_phase"):
            chapter_summaries = await _parallel_chapter_map(overview, slides)

        # ════════════════════════════════════════════════════════════════
        # Step 3: Reduce — combine into global summary
        # ════════════════════════════════════════════════════════════════

        with custom_span("reduce_phase"):
            global_summary = await _reduce_summaries(overview, chapter_summaries)

    global_summary.chapter_summaries = chapter_summaries
    global_summary.total_chapters = len(chapter_summaries)
    return overview, global_summary


# ── Step 1: Two-stage overview ───────────────────────────────────────────

async def _two_stage_overview(
    document_title: str,
    slides: list[ParsedSlide],
    total_slides: int,
) -> DocumentOverview:
    """
    Stage 1a: Split into chunks, run local overviews in parallel.
    Stage 1b: Merge chunk results into final DocumentOverview.
    """
    chunk_size = OVERVIEW_CHUNK_SIZE
    num_chunks = math.ceil(total_slides / chunk_size)

    # Small documents (≤ 1 chunk) — skip chunking, run single overview
    if num_chunks <= 1:
        return await _single_overview(document_title, slides, total_slides)

    log.info(
        f"[Agent 1] Two-stage overview: {total_slides} slides → "
        f"{num_chunks} chunks of ~{chunk_size}"
    )

    # ── Stage 1a: Parallel chunk overviews ────────────────────────
    chunk_overviews: list[ChunkOverview] = []

    async def _run_chunk(chunk_id: int, chunk_slides: list[ParsedSlide], first: int, last: int):
        async with _ollama_sem:
            with custom_span(f"chunk_{chunk_id}"):
                preview = build_preview_document(chunk_slides)
                chunk_input = (
                    f"Document: {document_title}\n"
                    f"This is chunk {chunk_id} of {num_chunks} from a {total_slides}-slide document.\n"
                    f"Chunk slide range: {first}-{last}\n\n"
                    f"--- Slide Previews ---\n{preview}"
                )
                result = await Runner.run(
                    chunk_overview_agent,
                    input=chunk_input,
                    run_config=_run_config,
                )
                co: ChunkOverview = result.final_output
                co.chunk_id = chunk_id
                co.slide_range_local = f"{first}-{last}"
                _normalize_chapters(co.local_chapters)
                log.info(
                    f"[Agent 1] Chunk {chunk_id}/{num_chunks} done: "
                    f"slides {first}-{last}, {len(co.local_chapters)} chapters"
                )
                return co

    tasks = []
    for i in range(num_chunks):
        start_idx = i * chunk_size
        end_idx = min(start_idx + chunk_size, total_slides)
        chunk_slides = slides[start_idx:end_idx]
        first_page = chunk_slides[0].slide_number
        last_page = chunk_slides[-1].slide_number
        tasks.append(_run_chunk(i + 1, chunk_slides, first_page, last_page))

    with custom_span("chunk_overviews"):
        chunk_overviews = await asyncio.gather(*tasks)

    # ── Stage 1b: Merge ──────────────────────────────────────────
    with custom_span("merge_overview"):
        merge_lines = []
        for co in chunk_overviews:
            chapters_text = "\n".join(
                f"    - {ch.chapter_name} (slides {ch.slide_range}): {', '.join(ch.key_topics)}"
                for ch in co.local_chapters
            )
            merge_lines.append(
                f"Chunk {co.chunk_id} (slides {co.slide_range_local}):\n"
                f"  Summary: {co.chunk_summary}\n"
                f"  Topics: {', '.join(co.local_topics)}\n"
                f"  Keywords: {', '.join(co.topic_keywords)}\n"
                f"  Chapters:\n{chapters_text}"
            )

        merge_input = (
            f"Document: {document_title}\n"
            f"Total slides: {total_slides}\n\n"
            f"--- Chunk Overviews ---\n\n" + "\n\n".join(merge_lines)
        )

        result = await Runner.run(
            merge_overview_agent,
            input=merge_input,
            run_config=_run_config,
        )
        overview: DocumentOverview = result.final_output

    # ── Post-process: normalize, fix total_slides, fill gaps ─────
    overview.total_slides = total_slides
    _normalize_chapters(overview.chapters)

    covered = set()
    for ch in overview.chapters:
        covered |= _parse_slide_range(ch.slide_range)

    missing = set(range(1, total_slides + 1)) - covered
    if missing:
        log.warning(
            f"[Agent 1] Merge chapters cover {len(covered)}/{total_slides} slides. "
            f"Missing: {sorted(missing)[:20]}{'...' if len(missing) > 20 else ''}"
        )
        overview.chapters.extend(_build_gap_chapters(missing))
        log.info(f"[Agent 1] Auto-filled gap chapter for {len(missing)} uncovered slides")

    log.info(
        f"[Agent 1] Final overview: {len(overview.chapters)} chapters, "
        f"{total_slides} slides"
    )
    return overview


async def _single_overview(
    document_title: str,
    slides: list[ParsedSlide],
    total_slides: int,
) -> DocumentOverview:
    """Fallback for small documents that don't need chunking."""
    with custom_span("single_overview"):
        preview = build_preview_document(slides)
        step1_input = (
            f"Document: {document_title}\n"
            f"Total slides: {total_slides}\n\n"
            f"--- Slide Previews ---\n{preview}"
        )
        result = await Runner.run(
            merge_overview_agent,
            input=step1_input,
            run_config=_run_config,
        )
        overview: DocumentOverview = result.final_output

    overview.total_slides = total_slides
    _normalize_chapters(overview.chapters)

    covered = set()
    for ch in overview.chapters:
        covered |= _parse_slide_range(ch.slide_range)

    missing = set(range(1, total_slides + 1)) - covered
    if missing:
        log.warning(
            f"[Agent 1] Single overview covers {len(covered)}/{total_slides}. "
            f"Missing: {sorted(missing)[:20]}"
        )
        overview.chapters.extend(_build_gap_chapters(missing))

    return overview


# ── Step 2: Parallel chapter map ─────────────────────────────────────────

async def _parallel_chapter_map(
    overview: DocumentOverview,
    slides: list[ParsedSlide],
) -> list[ChapterSummary]:
    """Run chapter summarization in parallel, limited by semaphore."""

    async def _summarize_chapter(chapter: ChapterInfo) -> ChapterSummary | None:
        async with _ollama_sem:
            with custom_span(f"chapter_{chapter.chapter_name}"):
                chapter_slides = get_chapter_slides(slides, chapter.slide_range)
                if not chapter_slides:
                    log.warning(f"[Agent 1] No slides found for chapter '{chapter.chapter_name}' range={chapter.slide_range}")
                    return None
                chapter_text = "\n\n".join(
                    f"{s.header}\n{clean_for_llm(s.content)}" for s in chapter_slides
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
                return result.final_output

    tasks = [_summarize_chapter(ch) for ch in overview.chapters]
    results = await asyncio.gather(*tasks)

    # Filter out None results (chapters with no slides)
    return [r for r in results if r is not None]


# ── Step 3: Reduce ───────────────────────────────────────────────────────

async def _reduce_summaries(
    overview: DocumentOverview,
    chapter_summaries: list[ChapterSummary],
) -> GlobalDocumentSummary:
    """Combine chapter summaries into a single global summary."""
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
    return result.final_output
