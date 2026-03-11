"""
slide_agent.py — Slide-Level Agent (GEMINI) using OpenAI Agents SDK.

Uses `output_type=SlideBatchResponse` so the SDK auto-parses the structured
output — the prompt focuses purely on classification logic.

Sliding Window pattern: 25 slides per API call (dynamic merge for small remainders).
Rate limiter: max 20 calls/minute for GEMINI.
Fallback: On HTTP 429, switches from GEMINI_MODEL → GEMINI_FALLBACK_MODEL.

The file-level context (overview from Agent 1) is programmatically injected
into the system prompt — true agentic handoff.
"""

import asyncio
import logging
import math
import os
from dotenv import load_dotenv

from openai import AsyncOpenAI, RateLimitError
from agents import custom_span

from structuring.config import (
    SLIDE_BATCH_SIZE,
    SLIDE_BATCH_MERGE_THRESHOLD,
    GEMINI_BASE_URL,
    GEMINI_MODEL,
    GEMINI_FALLBACK_MODEL,
    GEMINI_MAX_CALLS_PER_MINUTE,
)
from structuring.schemas import (
    ParsedSlide,
    DocumentOverview,
    SlideMetadata,
    SlideType,
    SlideBatchResponse,
)
from structuring.rate_limiter import RedisRateLimiter

log = logging.getLogger(__name__)
load_dotenv()

# ── Custom exception for quota exhaustion ────────────────────────────────

class GeminiQuotaExhausted(Exception):
    """Raised when both primary and fallback Gemini models hit rate limits."""
    pass


# ── Rate Limiter (distributed via Redis, local fallback) ─────────────────

_limiter = RedisRateLimiter(
    name="gemini",
    max_calls=GEMINI_MAX_CALLS_PER_MINUTE,
    window=60.0,
)


# ── Batch sizing ─────────────────────────────────────────────────────────

def compute_batches(total_slides: int) -> list[tuple[int, int]]:
    """
    Return a list of (start, end) index pairs for batching slides.

    Optimization: if total_slides <= SLIDE_BATCH_SIZE + SLIDE_BATCH_MERGE_THRESHOLD,
    process all slides in a single call to avoid wasting an API call on a
    tiny remainder.  Otherwise, distribute evenly across batches.

    Examples (BATCH_SIZE=25, MERGE_THRESHOLD=12):
        32 slides → [(0, 32)]                   (1 call, merged)
        37 slides → [(0, 37)]                   (1 call, merged)
        38 slides → [(0, 19), (19, 38)]         (2 calls, even split)
        50 slides → [(0, 25), (25, 50)]         (2 calls, even split)
        52 slides → [(0, 18), (18, 35), (35, 52)]  (3 calls, even)
        75 slides → [(0, 25), (25, 50), (50, 75)]  (3 calls, even)
    """
    if total_slides == 0:
        return []

    max_single = SLIDE_BATCH_SIZE + SLIDE_BATCH_MERGE_THRESHOLD

    if total_slides <= max_single:
        return [(0, total_slides)]

    num_batches = math.ceil(total_slides / SLIDE_BATCH_SIZE)
    batch_size = math.ceil(total_slides / num_batches)

    batches = []
    for i in range(num_batches):
        start = i * batch_size
        end = min(start + batch_size, total_slides)
        if start < total_slides:
            batches.append((start, end))

    return batches


def build_instructions_slide_agent(overview: DocumentOverview):
    """
    Create a slide classification agent with the file-level context
    baked into its instructions. This is the programmatic handoff:
    Agent 1's output → Agent 2's system prompt.
    """
    chapters_text = "\n".join(
        f"  - {ch.chapter_name} (slides {ch.slide_range}): {', '.join(ch.key_topics)}"
        for ch in overview.chapters
    )

    instructions = (
        f"You are an academic slide classifier for the document:\n"
        f"  Title: {overview.document_title}\n"
        f"  Subject: {overview.subject}\n"
        f"  Summary: {overview.overarching_summary}\n"
        f"  Chapters:\n{chapters_text}\n\n"
        "For each slide in the batch, classify it:\n"
        "- parent_topic: which chapter it belongs to (from the list above)\n"
        "- slide_type: one of definition, syntax/code, comparison, "
        "numerical_example, diagram_explanation, summary, concept, example, table, other\n"
        "- core_concepts: key concepts on this slide\n"
        "- exam_signals: true if slide has hints like 'Summary', 'Comparison', "
        "'Note:', 'Important', 'Remember', 'Key'\n"
        "- slide_summary: 1-2 sentence clean human-readable summary\n\n"
        "Rules:\n"
        "- Do NOT hallucinate. Only use what is in the slide text.\n"
        "- If a slide is mostly empty or just a title, classify as 'other'.\n"
        "- slide_summary should be clean text, not raw OCR noise."
        "Instructions: Return exactly one object per slide in the same order as the input slides.Do not skip slides."
    )
    return instructions


# ── Public API ───────────────────────────────────────────────────────────

def _is_rate_limit_error(exc: Exception) -> bool:
    """Check if an exception is a 429 rate-limit error."""
    if isinstance(exc, RateLimitError):
        return True
    # Some OpenAI-compatible endpoints raise APIStatusError with status 429
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    return False


async def run_slide_agent(
    overview: DocumentOverview,
    slides: list[ParsedSlide],
) -> list[SlideMetadata]:
    """
    Classify all slides using GEMINI in sliding-window batches.

    Batches are dispatched concurrently via asyncio.gather (rate-limited
    to GEMINI_MAX_CALLS_PER_MINUTE calls/min).  The rate limiter ensures
    we never exceed the API quota even when all batches launch at once.

    Fallback: If the primary model returns HTTP 429, the batch is retried
    with GEMINI_FALLBACK_MODEL. If the fallback also 429s, a
    GeminiQuotaExhausted error is raised with a user-friendly message.

    Dynamic batching: Small remainders are merged into a single call to
    save API usage (see compute_batches).
    """
    with custom_span("slide_agent"):
        instructions = build_instructions_slide_agent(overview)

        client = AsyncOpenAI(
            api_key=os.environ.get("GEMINI_API_KEY", ""),
            base_url=GEMINI_BASE_URL,
        )

        # Compute dynamic batches
        batch_ranges = compute_batches(len(slides))
        total_batches = len(batch_ranges)

        # Track which model is being used (shared across batches)
        # Once we switch to fallback, all subsequent batches use fallback too.
        active_model = GEMINI_MODEL
        model_lock = asyncio.Lock()

        async def _call_gemini(model: str, messages: list[dict]) -> SlideBatchResponse:
            """Make a single Gemini API call (rate-limited)."""
            await _limiter.acquire()
            completion = await client.beta.chat.completions.parse(
                model=model,
                messages=messages,
                response_format=SlideBatchResponse,
            )
            return completion.choices[0].message.parsed

        async def _process_batch(batch: list[ParsedSlide], batch_num: int) -> list[SlideMetadata]:
            """Process a single batch with 429 fallback logic."""
            nonlocal active_model

            slide_nums = [s.slide_number for s in batch]
            log.info(f"[Agent 2] Batch {batch_num}/{total_batches} — slides {slide_nums} ({len(batch)} slides)")

            batch_text = "\n\n".join(
                f"--- Slide {s.slide_number} ---\n{s.content}" for s in batch
            )

            messages = [
                {"role": "system", "content": instructions},
                {"role": "user", "content": batch_text},
            ]

            with custom_span(f"batch_{batch_num}"):
                try:
                    # Try with the current active model
                    async with model_lock:
                        current_model = active_model

                    batch_response = await _call_gemini(current_model, messages)
                    log.info(f"[Agent 2] Batch {batch_num} — {len(batch_response.slides)} slides classified ({current_model})")
                    return batch_response.slides

                except Exception as primary_err:
                    if not _is_rate_limit_error(primary_err):
                        log.error(f"[Agent 2] Batch {batch_num} failed (non-429): {primary_err}")
                        return _fallback_metadata(batch)

                    # ── 429 on primary → switch to fallback model ────────
                    async with model_lock:
                        if active_model != GEMINI_FALLBACK_MODEL:
                            log.warning(
                                f"[Agent 2] Rate limit (429) on {active_model}. "
                                f"Switching to fallback: {GEMINI_FALLBACK_MODEL}"
                            )
                            active_model = GEMINI_FALLBACK_MODEL

                    try:
                        batch_response = await _call_gemini(GEMINI_FALLBACK_MODEL, messages)
                        log.info(
                            f"[Agent 2] Batch {batch_num} — {len(batch_response.slides)} "
                            f"slides classified ({GEMINI_FALLBACK_MODEL})"
                        )
                        return batch_response.slides

                    except Exception as fallback_err:
                        if _is_rate_limit_error(fallback_err):
                            raise GeminiQuotaExhausted(
                                "Gemini API daily quota exhausted on both "
                                f"'{GEMINI_MODEL}' and '{GEMINI_FALLBACK_MODEL}'. "
                                "Ingestion was completed successfully — your raw "
                                "knowledge files are saved. Please re-upload this "
                                "file tomorrow and it will resume from structuring "
                                "(ingestion will be skipped automatically)."
                            )
                        log.error(f"[Agent 2] Batch {batch_num} fallback failed (non-429): {fallback_err}")
                        return _fallback_metadata(batch)

        # Build batch tasks using dynamic batch ranges
        tasks = []
        for batch_num, (start, end) in enumerate(batch_ranges, 1):
            batch = slides[start:end]
            tasks.append(_process_batch(batch, batch_num))

        log.info(
            f"[Agent 2] {len(slides)} slides → {total_batches} batch(es) "
            f"(sizes: {[e - s for s, e in batch_ranges]})"
        )

        # Fire all batches concurrently (rate limiter gates actual API calls)
        batch_results = await asyncio.gather(*tasks)

        all_metadata: list[SlideMetadata] = []
        for result in batch_results:
            all_metadata.extend(result)

        all_metadata.sort(key=lambda m: m.slide_number)
        return all_metadata


def _fallback_metadata(batch: list[ParsedSlide]) -> list[SlideMetadata]:
    """Generate placeholder metadata when classification fails for non-429 reasons."""
    return [
        SlideMetadata(
            slide_number=slide.slide_number,
            parent_topic="Unknown",
            slide_type=SlideType.OTHER,
            core_concepts=[],
            exam_signals=False,
            slide_summary=f"[Classification failed] {slide.header}",
            chapter="Unknown",
        )
        for slide in batch
    ]
