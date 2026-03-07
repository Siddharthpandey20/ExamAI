"""
slide_agent.py — Slide-Level Agent (GEMINI) using OpenAI Agents SDK.

Uses `output_type=SlideBatchResponse` so the SDK auto-parses the structured
output — the prompt focuses purely on classification logic.

Sliding Window pattern: 25 slides per API call.
Rate limiter: max 20 calls/minute for GEMINI.

The file-level context (overview from Agent 1) is programmatically injected
into the system prompt — true agentic handoff.
"""

import asyncio
import logging
import os
import time
import threading
from unittest import result
from dotenv import load_dotenv

from openai import AsyncOpenAI
from agents import Agent, Runner, ModelSettings, RunConfig
from agents.models.openai_provider import OpenAIProvider
from agents.tracing import trace

from structuring.config import (
    SLIDE_BATCH_SIZE,
    GEMINI_BASE_URL,
    GEMINI_MODEL,
    GEMINI_MAX_CALLS_PER_MINUTE,
)
from structuring.schemas import (
    ParsedSlide,
    DocumentOverview,
    SlideMetadata,
    SlideType,
    SlideBatchResponse,
)

log = logging.getLogger(__name__)
load_dotenv()

# ── Rate Limiter ─────────────────────────────────────────────────────────

class _RateLimiter:
    """Token-bucket rate limiter. Thread-safe + async-friendly."""

    def __init__(self, max_calls: int, window: float = 60.0):
        self.max_calls = max_calls
        self.window = window
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self):
        while True:
            async with self._lock:
                now = time.time()
                self._timestamps = [t for t in self._timestamps if now - t < self.window]
                if len(self._timestamps) < self.max_calls:
                    self._timestamps.append(now)
                    return
                wait = self.window - (now - self._timestamps[0]) + 0.1

            log.info(f"[RateLimiter] Limit hit ({self.max_calls}/min). Waiting {wait:.1f}s...")
            await asyncio.sleep(wait)


# _limiter = _RateLimiter(max_calls=GROQ_MAX_CALLS_PER_MINUTE)
_limiter= _RateLimiter(max_calls=GEMINI_MAX_CALLS_PER_MINUTE)

def build_instructions_slide_agent(overview: DocumentOverview) :
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
    )
    return instructions


# ── Public API ───────────────────────────────────────────────────────────

async def run_slide_agent(
    overview: DocumentOverview,
    slides: list[ParsedSlide],
) -> list[SlideMetadata]:
    """
    Classify all slides using GEMINI in sliding-window batches.

    The overview from Agent 1 is injected into Agent 2's instructions.
    Rate-limited to GEMINI_MAX_CALLS_PER_MINUTE calls/min.
    """
    with trace("slide_agent_pipeline", metadata={"slides": str(len(slides))}):
        instructions = build_instructions_slide_agent(overview)

        all_metadata: list[SlideMetadata] = []
        total_batches = (len(slides) + SLIDE_BATCH_SIZE - 1) // SLIDE_BATCH_SIZE
        client = AsyncOpenAI(
                    api_key=os.environ.get("GEMINI_API_KEY", ""),
                    base_url=GEMINI_BASE_URL
        )

        for i in range(0, len(slides), SLIDE_BATCH_SIZE):
            batch = slides[i : i + SLIDE_BATCH_SIZE]
            batch_num = (i // SLIDE_BATCH_SIZE) + 1
            slide_nums = [s.slide_number for s in batch]

            log.info(f"[Agent 2] Batch {batch_num}/{total_batches} — slides {slide_nums}")

            # Build batch input
            batch_text = "\n\n".join(
                f"--- Slide {s.slide_number} ---\n{s.content}" for s in batch
            )

            # Rate limit
            await _limiter.acquire()

            try:
                completion =await client.beta.chat.completions.parse(
                    model=GEMINI_MODEL,
                    messages=[
                        {"role": "system", "content": instructions},
                        {"role": "user", "content": batch_text},
                    ],
                    response_format=SlideBatchResponse,
                )
                batch_response: SlideBatchResponse = completion.choices[0].message.parsed
                all_metadata.extend(batch_response.slides)
                log.info(f"[Agent 2] Batch {batch_num} — {len(batch_response.slides)} slides classified")
            except Exception as e:
                log.error(f"[Agent 2] Batch {batch_num} failed: {e}")
                for slide in batch:
                    all_metadata.append(SlideMetadata(
                        slide_number=slide.slide_number,
                        parent_topic="Unknown",
                        slide_type=SlideType.OTHER,
                        core_concepts=[],
                        exam_signals=False,
                        slide_summary=f"[Classification failed] {slide.header}",
                    ))

        all_metadata.sort(key=lambda m: m.slide_number)
        return all_metadata
