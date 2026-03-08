"""
extractor.py — LLM-based question extractor using Llama 3 via OpenAI Agents SDK.

Takes raw text extracted from a PYQ document (via the ingestion pipeline)
and uses Llama 3 to identify and clean individual exam questions.

Returns a list of ExtractedQuestion objects.
"""

import logging
import asyncio

from dotenv import load_dotenv

from openai import AsyncOpenAI
from agents import Agent, Runner, RunConfig
from agents.models.openai_provider import OpenAIProvider
from agents.tracing import trace

from pyq.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from pyq.schemas import ExtractedQuestionList

log = logging.getLogger(__name__)
load_dotenv()
# ── Ollama provider (OpenAI-compatible) ──────────────────────────────────

_ollama_client = AsyncOpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
_ollama_provider = OpenAIProvider(openai_client=_ollama_client, use_responses=False)
_run_config = RunConfig(model_provider=_ollama_provider)


# ── Question Extraction Agent ────────────────────────────────────────────

_extraction_agent = Agent(
    name="PYQExtractionAgent",
    instructions=(
        "You are an exam paper parser. You receive raw text extracted from a past year "
        "question paper (possibly noisy from OCR). Your job is to identify and extract "
        "every individual exam question.\n\n"
        "RULES:\n"
        "1. Extract ONLY actual exam questions. Ignore headers, footers, instructions "
        "   like 'Answer any 5', roll number fields, page numbers.\n"
        "2. Clean up OCR noise but do NOT change the meaning of any question.\n"
        "3. If a question has sub-parts (a, b, c), combine them into ONE question entry "
        "   with the full text including sub-parts.\n"
        "4. Preserve technical terms, formulas, and variable names exactly.\n"
        "5. If marks are mentioned (e.g. '[5 marks]', '(5M)'), extract them.\n"
        "6. Number questions sequentially starting from 1.\n"
        "7. If the text is empty or contains no questions, return an empty list.\n"
        "8. Do NOT fabricate questions. Only extract what is present."
    ),
    model=OLLAMA_MODEL,
    output_type=ExtractedQuestionList,
)


def _build_extraction_prompt(raw_text: str, source_hint: str = "") -> str:
    """Build the user prompt for the question extraction agent."""
    header = f"Source: {source_hint}\n\n" if source_hint else ""
    return (
        f"{header}"
        f"Extract all exam questions from the following text. "
        f"Clean up OCR noise, identify question boundaries, and extract marks if present.\n\n"
        f"---\n{raw_text}\n---"
    )


async def _extract_async(raw_text: str, source_hint: str = "") -> ExtractedQuestionList:
    """Run the extraction agent asynchronously."""
    with trace("PYQ EXTRACTION", metadata={"text_length": str(len(raw_text))}):
        prompt = _build_extraction_prompt(raw_text, source_hint)
        result = await Runner.run(
        _extraction_agent,
        input=prompt,
        run_config=_run_config,
        )
    return result.final_output


def extract_questions(raw_text: str, source_hint: str = "") -> ExtractedQuestionList:
    """
    Extract structured exam questions from raw PYQ text.

    Parameters
    ----------
    raw_text : str
        Raw text from the ingested PYQ document (all pages concatenated).
    source_hint : str
        Optional identifier like 'Midterm 2024' for context.

    Returns
    -------
    ExtractedQuestionList
        Pydantic model containing list of clean questions.
    """
    if not raw_text.strip():
        log.warning("[Extractor] Empty text — returning empty question list")
        return ExtractedQuestionList(source_info=source_hint, questions=[])

    log.info(f"[Extractor] Sending {len(raw_text)} chars to Llama 3 for question extraction...")

    result = asyncio.run(_extract_async(raw_text, source_hint))

    log.info(f"[Extractor] Extracted {len(result.questions)} questions")
    for q in result.questions:
        snippet = q.question_text[:80].replace("\n", " ")
        marks_str = f" [{q.marks}M]" if q.marks else ""
        log.info(f"  Q{q.question_number}: {snippet}...{marks_str}")

    return result
