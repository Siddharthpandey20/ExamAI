"""
slide_agent.py — Slide-Level Agent using GROQ via OpenAI SDK.

Processes slides in batches of SLIDE_BATCH_SIZE (10-15) using a "Sliding Window"
pattern. Each batch is sent as one GROQ API call. A rate limiter enforces
max GROQ_MAX_CALLS_PER_MINUTE calls per minute.

The file-level context (overarching summary + chapters) is included in every
call so GROQ can assign parent_topic accurately.
"""

import json
import re
import logging

from openai import OpenAI

from structuring.config import (
    GROQ_API_KEY,
    GROQ_OPENAI_BASE,
    GROQ_MODEL,
    SLIDE_BATCH_SIZE,
    LLM_TIMEOUT,
)
from structuring.schemas import (
    ParsedSlide,
    DocumentOverview,
    SlideMetadata,
    SlideType,
    SlideBatchResponse,
)
from structuring.rate_limiter import GROQ_limiter

log = logging.getLogger(__name__)

# ── GROQ client (OpenAI-compatible) ────────────────────────────────────

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Lazy-init the GROQ client. Fails early if API key is missing."""
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY not set. Export it as an environment variable:\n"
                "  set GROQ_API_KEY=your-key-here   (Windows)\n"
                "  export GROQ_API_KEY=your-key-here (Linux/Mac)"
            )
        _client = OpenAI(
            base_url=GROQ_OPENAI_BASE,
            api_key=GROQ_API_KEY,
            timeout=LLM_TIMEOUT,
        )
    return _client


def _extract_json_array(raw: str) -> list[dict]:
    """
    Extract a JSON object with a 'slides' array from LLM output.
    Handles markdown fences and extra text around the JSON.
    """
    # Try ```json ... ``` fences first
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence_match:
        data = json.loads(fence_match.group(1))
        return data.get("slides", [data] if "slide_number" in data else [])

    # Try bare { ... } with a "slides" key
    brace_start = raw.find("{")
    brace_end = raw.rfind("}")
    if brace_start != -1 and brace_end != -1:
        data = json.loads(raw[brace_start:brace_end + 1])
        return data.get("slides", [data] if "slide_number" in data else [])

    # Try bare [ ... ] array
    bracket_start = raw.find("[")
    bracket_end = raw.rfind("]")
    if bracket_start != -1 and bracket_end != -1:
        return json.loads(raw[bracket_start:bracket_end + 1])

    raise ValueError(f"Could not extract JSON from Gemini response:\n{raw[:500]}")


# ── Prompt ───────────────────────────────────────────────────────────────

SLIDE_SYSTEM = """You are an academic slide classifier. You will receive:
1. Document context: title, subject, overarching summary, and chapter structure.
2. A batch of slides (each with slide number and content).

For EACH slide, output structured metadata. Your response must be a STRICT JSON object:
{
  "slides": [
    {
      "slide_number": <int>,
      "parent_topic": "<the chapter/topic this slide belongs to>",
      "slide_type": "<one of: definition, syntax/code, comparison, numerical_example, diagram_explanation, summary, concept, example, table, other>",
      "core_concepts": ["concept1", "concept2"],
      "exam_signals": <true if slide has exam hints like 'Summary', 'Comparison', 'Note:', 'Important', 'Remember', 'Key', otherwise false>,
      "slide_summary": "<1-2 sentence clean summary>"
    }
  ]
}

Rules:
- Output ONLY the JSON object. No extra text before or after.
- One entry per slide in the batch.
- slide_type must be exactly one of the allowed values.
- parent_topic should match one of the chapters from the document context.
- slide_summary should be a clean, human-readable summary — not raw OCR noise.
- Do NOT hallucinate content. Only use what is in the slide text.
- If a slide is mostly empty or just a title, classify as "other" and summarize as "Title slide" or "Section header"."""


def _build_batch_prompt(
    overview: DocumentOverview,
    batch: list[ParsedSlide],
) -> str:
    """Build the user prompt for a batch of slides."""
    # Document context
    chapters_text = "\n".join(
        f"  - {ch.chapter_name} (slides {ch.slide_range}): {', '.join(ch.key_topics)}"
        for ch in overview.chapters
    )

    context = (
        f"Document: {overview.document_title}\n"
        f"Subject: {overview.subject}\n"
        f"Summary: {overview.overarching_summary}\n"
        f"Chapters:\n{chapters_text}\n"
    )

    # Slide content
    slides_text = "\n\n".join(
        f"--- Slide {s.slide_number} ---\n{s.content}"
        for s in batch
    )

    return f"{context}\n--- SLIDES TO CLASSIFY ---\n{slides_text}"


def _call_groq_batch(
    overview: DocumentOverview,
    batch: list[ParsedSlide],
) -> list[SlideMetadata]:
    """
    Send one batch of slides to GROQ and parse the response.
    Respects rate limiting.
    """
    client = _get_client()
    user_prompt = _build_batch_prompt(overview, batch)

    slide_nums = [s.slide_number for s in batch]
    log.info(f"[GROQ] Classifying slides {slide_nums} ({len(user_prompt)} chars)")

    # Rate limit: wait for a slot
    GROQ_limiter.acquire()

    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SLIDE_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    raw = resp.choices[0].message.content.strip()
    items = _extract_json_array(raw)

    results: list[SlideMetadata] = []
    for item in items:
        try:
            results.append(SlideMetadata(**item))
        except Exception as e:
            log.warning(f"[GROQ] Failed to parse slide metadata: {e}\nRaw item: {item}")

    log.info(f"[GROQ] Got {len(results)} slide metadata objects")
    return results


# ── Public API ───────────────────────────────────────────────────────────

def classify_all_slides(
    overview: DocumentOverview,
    slides: list[ParsedSlide],
) -> list[SlideMetadata]:
    """
    Classify all slides using GROQ in batches of SLIDE_BATCH_SIZE.

    The "Sliding Window" batch pattern:
      - Slides are grouped into batches of 10-15.
      - Each batch = 1 API call.
      - Rate limiter ensures max 12-13 calls/minute.

    Parameters
    ----------
    overview : DocumentOverview
        File-level context from Ollama (Step 1).
    slides : list[ParsedSlide]
        All parsed slides from the markdown file.

    Returns
    -------
    list[SlideMetadata]
        Structured metadata for every slide.
    """
    all_metadata: list[SlideMetadata] = []
    total_batches = (len(slides) + SLIDE_BATCH_SIZE - 1) // SLIDE_BATCH_SIZE

    for i in range(0, len(slides), SLIDE_BATCH_SIZE):
        batch = slides[i:i + SLIDE_BATCH_SIZE]
        batch_num = (i // SLIDE_BATCH_SIZE) + 1
        log.info(f"[GROQ] Processing batch {batch_num}/{total_batches}")

        try:
            metadata = _call_groq_batch(overview, batch)
            all_metadata.extend(metadata)
        except Exception as e:
            log.error(f"[GROQ] Batch {batch_num} failed: {e}")
            # Create fallback entries for slides in this batch
            for slide in batch:
                all_metadata.append(SlideMetadata(
                    slide_number=slide.slide_number,
                    parent_topic="Unknown",
                    slide_type=SlideType.OTHER,
                    core_concepts=[],
                    exam_signals=False,
                    slide_summary=f"[Classification failed] {slide.header}",
                ))

    # Sort by slide number to ensure consistent ordering
    all_metadata.sort(key=lambda m: m.slide_number)
    return all_metadata
