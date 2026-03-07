"""
file_agent.py — File-Level Agent using Ollama (Llama3) via OpenAI SDK.

Two-step process:
  Step 1: Send document preview → get DocumentOverview (chapters, overarching summary)
  Step 2: Map-Reduce over chapters → get GlobalDocumentSummary

Uses the OpenAI SDK pointed at Ollama's /v1 endpoint for structured output.
"""

import json
import logging

from openai import OpenAI

from structuring.config import OLLAMA_OPENAI_BASE, OLLAMA_MODEL, LLM_TIMEOUT
from structuring.schemas import (
    ParsedSlide,
    DocumentOverview,
    ChapterSummary,
    GlobalDocumentSummary,
)
from structuring.md_parser import build_preview_document, get_chapter_slides

log = logging.getLogger(__name__)

# ── Ollama client (OpenAI-compatible) ────────────────────────────────────

_client = OpenAI(
    base_url=OLLAMA_OPENAI_BASE,
    api_key="ollama",  # Ollama doesn't need a real key
    timeout=LLM_TIMEOUT,
)


def _call_ollama(system_prompt: str, user_prompt: str) -> str:
    """Send a chat completion to Ollama and return the assistant message."""
    try:
        resp = _client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        log.error(f"Ollama call failed: {e}")
        raise


def _extract_json(raw: str) -> dict:
    """
    Extract a JSON object from LLM output that may contain markdown fences
    or extra text around the JSON.
    """
    # Try to find JSON between ```json ... ``` fences
    import re
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1))

    # Try to find the first { ... } block
    brace_start = raw.find("{")
    brace_end = raw.rfind("}")
    if brace_start != -1 and brace_end != -1:
        return json.loads(raw[brace_start:brace_end + 1])

    raise ValueError(f"Could not extract JSON from Ollama response:\n{raw[:500]}")


# ── Step 1: Document Overview ────────────────────────────────────────────

STEP1_SYSTEM = """You are an academic document analyzer. You will receive a preview of a lecture document (slide headers and short excerpts).

Your job is to output a STRICT JSON object with this exact schema:
{
  "document_title": "<title of the document>",
  "subject": "<academic subject>",
  "overarching_summary": "<2-3 sentence summary of the entire document>",
  "chapters": [
    {
      "chapter_name": "<topic name>",
      "slide_range": "<start-end, e.g. 1-5>",
      "key_topics": ["topic1", "topic2"]
    }
  ],
  "total_slides": <number>
}

Rules:
- Group consecutive slides that cover the same topic into one chapter.
- A chapter can span 1 to many slides.
- Output ONLY the JSON object, no extra text.
- Do not hallucinate content — only use what is in the preview."""


def step1_document_overview(
    document_title: str, slides: list[ParsedSlide]
) -> DocumentOverview:
    """
    Step 1: Send slide previews to Ollama → get DocumentOverview.
    """
    preview_doc = build_preview_document(slides)
    user_prompt = (
        f"Document: {document_title}\n"
        f"Total slides: {len(slides)}\n\n"
        f"--- Slide Previews ---\n{preview_doc}"
    )

    log.info(f"[Step 1] Sending preview ({len(user_prompt)} chars) to Ollama")
    raw = _call_ollama(STEP1_SYSTEM, user_prompt)
    data = _extract_json(raw)
    overview = DocumentOverview(**data)
    log.info(f"[Step 1] Detected {len(overview.chapters)} chapters")
    return overview


# ── Step 2: Map-Reduce Chapter Summaries ─────────────────────────────────

MAP_SYSTEM = """You are an academic content summarizer. You will receive:
1. An overarching summary of the entire document (for context).
2. The full text of one chapter (group of slides).

Output a STRICT JSON object:
{
  "chapter_name": "<name of this chapter>",
  "summary": "<3-5 sentence summary of the chapter content>",
  "key_concepts": ["concept1", "concept2", ...],
  "has_numerical_examples": true/false
}

Rules:
- Summarize ONLY the chapter content provided.
- Use the overarching summary only for context, not as content.
- Output ONLY the JSON object, no extra text.
- Do not hallucinate or invent concepts not present in the slides."""


REDUCE_SYSTEM = """You are an academic document summarizer. You will receive:
1. The document title and subject.
2. Summaries of each chapter.

Output a STRICT JSON object:
{
  "document_title": "<title>",
  "subject": "<subject>",
  "global_summary": "<comprehensive 4-6 sentence summary covering ALL chapters>",
  "chapter_summaries": [<the chapter summaries you received>],
  "core_topics": ["topic1", "topic2", ...],
  "total_chapters": <number>
}

Rules:
- The global_summary should synthesize all chapter summaries into one coherent overview.
- core_topics should list the most important topics across the entire document.
- Output ONLY the JSON object, no extra text."""


def _map_chapter(
    chapter_name: str,
    chapter_text: str,
    overarching_summary: str,
) -> ChapterSummary:
    """Map step: summarize one chapter."""
    user_prompt = (
        f"Overarching Document Summary:\n{overarching_summary}\n\n"
        f"--- Chapter: {chapter_name} ---\n{chapter_text}"
    )

    log.info(f"[Map] Summarizing chapter: {chapter_name} ({len(chapter_text)} chars)")
    raw = _call_ollama(MAP_SYSTEM, user_prompt)
    data = _extract_json(raw)
    return ChapterSummary(**data)


def step2_map_reduce(
    overview: DocumentOverview,
    slides: list[ParsedSlide],
) -> GlobalDocumentSummary:
    """
    Step 2: Map-Reduce summarization.
      Map   — Summarize each chapter individually (with overarching context).
      Reduce — Combine all chapter summaries into a GlobalDocumentSummary.
    """
    chapter_summaries: list[ChapterSummary] = []

    for chapter in overview.chapters:
        # Get the slides belonging to this chapter
        chapter_slides = get_chapter_slides(slides, chapter.slide_range)
        if not chapter_slides:
            log.warning(f"[Map] No slides found for chapter '{chapter.chapter_name}' range {chapter.slide_range}")
            continue

        # Build the full text of the chapter
        chapter_text = "\n\n".join(
            f"{s.header}\n{s.content}" for s in chapter_slides
        )

        summary = _map_chapter(
            chapter_name=chapter.chapter_name,
            chapter_text=chapter_text,
            overarching_summary=overview.overarching_summary,
        )
        chapter_summaries.append(summary)

    # ── Reduce: combine all chapter summaries ────────────────────────────
    summaries_text = "\n\n".join(
        f"Chapter: {cs.chapter_name}\n"
        f"Summary: {cs.summary}\n"
        f"Key Concepts: {', '.join(cs.key_concepts)}"
        for cs in chapter_summaries
    )

    reduce_prompt = (
        f"Document: {overview.document_title}\n"
        f"Subject: {overview.subject}\n\n"
        f"--- Chapter Summaries ---\n{summaries_text}"
    )

    log.info(f"[Reduce] Combining {len(chapter_summaries)} chapter summaries")
    raw = _call_ollama(REDUCE_SYSTEM, reduce_prompt)
    data = _extract_json(raw)

    # Ensure the chapter_summaries in the reduced output are our actual summaries
    data["chapter_summaries"] = [cs.model_dump() for cs in chapter_summaries]
    return GlobalDocumentSummary(**data)
