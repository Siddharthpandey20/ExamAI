"""
engine/reasoning_mode.py — Reasoning mode: multi-step AI agent with tools.

Uses the OpenAI Agents SDK with Groq as the LLM backend.
The agent receives the student's query plus a set of tools (hybrid search,
slide lookup, priority check, PYQ data, etc.) and decides how to combine
them to formulate a thorough answer.

Each tool creates its own short-lived SQLAlchemy session so there are no
cross-thread session issues (the SDK runs sync tools in an executor).
"""

import json
import logging

from openai import AsyncOpenAI
from agents import Agent, Runner, function_tool, custom_span
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from engine import get_embedder, get_chroma
from engine.config import GROQ_API_KEY, GROQ_BASE_URL, TOOL_OUTPUT_MAX_CHARS
from engine.llm import pool
from engine.cache import smart_cache_check, store_cache
from engine.tools import (
    run_hybrid_search,
    get_slide_detail,
    search_by_type,
    search_by_concept,
    get_priority_slides,
    get_pyq_report,
    get_chapter_structure,
    get_subject_overview,
    get_weak_spots,
)
from indexing.database import SessionFactory
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)


def _trim(text: str, limit: int = TOOL_OUTPUT_MAX_CHARS) -> str:
    """Truncate tool output to keep agent context manageable."""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[trimmed]"


def _get_agent_model() -> tuple[OpenAIChatCompletionsModel, str]:
    """Pick the best available Groq model for the agent."""
    model_name = pool.get_best_model_name()
    client = AsyncOpenAI(base_url=GROQ_BASE_URL, api_key=GROQ_API_KEY)
    model = OpenAIChatCompletionsModel(model=model_name, openai_client=client)
    return model, model_name


# ── System prompt ────────────────────────────────────────────────────────

_SYSTEM = """\
You are an expert exam study assistant with deep access to a student's \
indexed lecture material for the subject {subject}. You can search slides, \
check priorities, look up PYQ mappings, and analyse the material in detail.

WORKFLOW:
1. Use tools to gather the information you need before answering.
2. If one search doesn't yield good results, try different keywords.
3. For study plans, always fetch priorities AND PYQ data first.
4. For topic questions, search first then check surrounding slides for context.

RESPONSE RULES:
- Always cite specific slides: "Page X of filename"
- Never say "Based on the provided data" — speak as a knowledgeable tutor
- Highlight what is most likely to appear in exams (high PYQ hits, exam signals)
- Mention numerical problems when relevant
- Structure long answers with clear headings
- Filter out heading-only or index slides that lack real content
"""


# ── Tool factory (closures capture *subject*) ───────────────────────────

def _make_tools(subject: str):
    """Return a list of function_tool-decorated functions bound to *subject*."""

    @function_tool
    def search_slides(query: str, top_k: int = 10) -> str:
        """Search lecture slides using semantic + keyword matching. Returns ranked slides with metadata, content, and relevance scores."""
        embedder = get_embedder()
        chroma = get_chroma()
        session = SessionFactory()
        try:
            results = run_hybrid_search(
                query, subject, session, embedder, chroma, top_k=top_k,
            )
            if not results:
                return "No matching slides found for this query."
            return _trim(json.dumps(results, indent=2))
        finally:
            session.close()

    @function_tool
    def get_slide_content(slide_id: int) -> str:
        """Get the full content and metadata of a specific slide by its ID."""
        session = SessionFactory()
        try:
            result = get_slide_detail(slide_id, session)
            if not result:
                return "Slide not found."
            return _trim(json.dumps(result, indent=2))
        finally:
            session.close()

    @function_tool
    def find_slides_by_type(slide_type: str) -> str:
        """Find slides filtered by type. Available types: definition, concept, numerical_example, formula, comparison, syntax/code, diagram_explanation, summary, example, table, other."""
        session = SessionFactory()
        try:
            results = search_by_type(subject, slide_type, session)
            if not results:
                return f"No slides of type '{slide_type}' found."
            return _trim(json.dumps(results[:20], indent=2))
        finally:
            session.close()

    @function_tool
    def find_slides_by_concept(concept_keyword: str) -> str:
        """Find slides that mention a specific concept keyword in their extracted concepts list."""
        session = SessionFactory()
        try:
            results = search_by_concept(subject, concept_keyword, session)
            if not results:
                return f"No slides found with concept '{concept_keyword}'."
            return _trim(json.dumps(results[:15], indent=2))
        finally:
            session.close()

    @function_tool
    def get_priorities(unused_arg= None) -> str:
        """Get slides classified by priority tier: high (exam-critical, PYQ-heavy), medium, low. Returns counts and slide details per tier."""
        session = SessionFactory()
        try:
            tiers = get_priority_slides(subject, session)
            summary = {
                "high_count": len(tiers["high"]),
                "medium_count": len(tiers["medium"]),
                "low_count": len(tiers["low"]),
                "high_slides": tiers["high"][:15],
                "medium_slides": tiers["medium"][:10],
                "low_slides": tiers["low"][:5],
            }
            return _trim(json.dumps(summary, indent=2))
        finally:
            session.close()

    @function_tool
    def get_pyq_data(unused_arg: str = None) -> str:
        """Get past year questions and the slides they map to. Shows which exam questions are linked to which lecture slides with similarity scores."""
        session = SessionFactory()
        try:
            report = get_pyq_report(subject, session)
            for q in report.get("questions", []):
                q["question_text"] = q["question_text"][:300]
            return _trim(json.dumps(report, indent=2))
        finally:
            session.close()

    @function_tool
    def get_chapters(unused_arg: str = None) -> str:
        """Get chapter structure across all documents for this subject. Returns chapter names, slide ranges, and source files."""
        session = SessionFactory()
        try:
            chapters = get_chapter_structure(subject, session)
            if not chapters:
                return "No chapter structure available."
            return _trim(json.dumps(chapters, indent=2))
        finally:
            session.close()

    @function_tool
    def get_overview(unused_arg: str = None) -> str:
        """Get summary statistics: document count, slide count, PYQ question count, average importance score, high-priority slide count."""
        session = SessionFactory()
        try:
            overview = get_subject_overview(subject, session)
            return _trim(json.dumps(overview, indent=2))
        finally:
            session.close()

    @function_tool
    def find_weak_spots(unused_arg: str = None) -> str:
        """Find weak spots — chapters with high PYQ frequency but potentially low slide coverage. Useful for identifying areas that need extra study."""
        session = SessionFactory()
        try:
            weak = get_weak_spots(subject, session)
            if not weak:
                return "No weak spots detected (or no PYQ data available)."
            return _trim(json.dumps(weak, indent=2))
        finally:
            session.close()

    return [
        search_slides,
        get_slide_content,
        find_slides_by_type,
        find_slides_by_concept,
        get_priorities,
        get_pyq_data,
        get_chapters,
        get_overview,
        find_weak_spots,
    ]


# ── Public entry point ──────────────────────────────────────────────────

async def run_reasoning(query: str, subject: str, force: bool = False) -> dict:
    """
    Run reasoning mode: agent with tools for multi-step analysis.

    The agent autonomously decides which tools to call, how to combine
    results, and then formulates a final natural-language answer.
    """
    with custom_span("reasoning_agent"):
        # ── Two-level cache (exact → fuzzy) ──────────────────────────
        cached, query = await smart_cache_check(
            subject, "reasoning", query, force,
        )
        if cached:
            return cached
        
        tools = _make_tools(subject)
        model, model_name = _get_agent_model()

        agent = Agent(
            name="ExamPrepAssistant",
            model=model,
            instructions=_SYSTEM.format(subject=subject),
            tools=tools,
        )

        user_input = f"[Subject: {subject}]\n\n{query}"
        result = await Runner.run(agent, input=user_input)

        response = {
            "answer": result.final_output,
            "mode": "reasoning",
            "model_used": model_name,
        }
        store_cache(subject, "reasoning", query, response, model_name)
        return response
