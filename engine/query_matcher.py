"""
engine/query_matcher.py — Fuzzy query matching against cached queries using Ollama.

When a user asks "is tcp covered in ppt?" and the cache already has
"tcp is covered in ppt or not", an exact hash match fails.  This module
uses a local Ollama model (no rate-limit cost) with Pydantic structured
output to detect semantic equivalence and also normalise the query for
better future caching.

Flow:
  1. Fetch cached query_text entries for (subject, endpoint).
  2. Ask Ollama: "Is the user's query equivalent to any cached query?"
  3. Ollama returns a Pydantic QueryMatchResult:
       - is_existing: bool
       - matched_query_hash: str | None
       - normalized_query: str
"""

import json
import logging

from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from agents import Agent, Runner, custom_span
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel

from engine.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from indexing.database import SessionFactory
from indexing.models import QueryCache

log = logging.getLogger(__name__)

# ── Pydantic output schema ──────────────────────────────────────────────

class QueryMatchResult(BaseModel):
    """Structured output from the query matcher."""
    is_existing: bool = Field(
        description="True if the user's query is semantically equivalent to a cached query",
    )
    matched_query_hash: str | None = Field(
        None,
        description="query_hash of the matching cached query, or null if no match",
    )
    normalized_query: str = Field(
        description="A clean, concise, normalised version of the user's query",
    )


# ── Ollama model (local, free, no rate limits) ──────────────────────────

_ollama_client = AsyncOpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
_ollama_model = OpenAIChatCompletionsModel(
    model=OLLAMA_MODEL,
    openai_client=_ollama_client,
)

_STOP_WORDS = frozenset(
    "is are was were the a an of in on for to and or not how what why when "
    "where which who whom do does did can could will would should shall may "
    "might be been being have has had it its this that these those my your "
    "covered explain describe define tell me about ppt slides".split()
)


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful lowercase keywords from a query."""
    import re
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    return words - _STOP_WORDS


def _has_keyword_overlap(query: str, cached_text: str, min_overlap: int = 1) -> bool:
    """Return True if the two texts share at least *min_overlap* keywords."""
    q_kw = _extract_keywords(query)
    c_kw = _extract_keywords(cached_text)
    return len(q_kw & c_kw) >= min_overlap


_MATCH_SYSTEM = """\
You are a STRICT query equivalence detector.  Given a user's query and a list \
of previously cached queries, determine whether the user's query is asking \
about the EXACT SAME TOPIC as any cached query.

CRITICAL RULES — read carefully:
- Two queries match ONLY if they are about the SAME specific topic/concept.
- Different topics are NEVER a match, even if they are from the same subject.
- When in doubt, return is_existing=false.  False negatives are acceptable; \
  false positives are NOT.
- A match must share the SAME core subject matter, not just be vaguely related.
-For matching optimised revision schedule you make sure the current given hour matches the hour of the last revision of the same topic. If it does, then you return a match, otherwise no match.It is very important to strictly follow this rule to ensure the effectiveness of the revision schedule.
Examples of MATCHES (same topic, different wording):
  "is tcp covered in ppt?" ↔ "tcp is covered in ppt or not"  → MATCH
  "explain tcp"           ↔ "what is tcp"                    → MATCH
  "linear regression derivation" ↔ "derive linear regression" → MATCH

Examples of NON-matches (different topics — MUST return is_existing=false):
  "Waterfall Model"   ↔ "why software effort grows exponentially" → NO MATCH
  "tcp vs udp"        ↔ "explain tcp"                            → NO MATCH
  "study plan for ML" ↔ "weak spots ML"                          → NO MATCH
  "binary search"     ↔ "sorting algorithms"                     → NO MATCH
  "pipelining"        ↔ "ARM assembly"                           → NO MATCH

If NO cached query matches, set is_existing=false and matched_query_hash=null.
Always produce a clean, normalised version of the user's query.
"""

_match_agent = Agent(
    name="QueryMatcher",
    model=_ollama_model,
    instructions=_MATCH_SYSTEM,
    output_type=QueryMatchResult,
)


# ── Public API ───────────────────────────────────────────────────────────

async def find_matching_query(
    query: str,
    subject: str,
    endpoint: str,
) -> QueryMatchResult | None:
    """
    Check if a semantically equivalent query already exists in the cache.

    Returns a QueryMatchResult with match info + normalized query,
    or None if Ollama is unavailable or an error occurs.
    """
    session = SessionFactory()
    try:
        cached = (
            session.query(QueryCache)
            .filter(
                QueryCache.subject == subject,
                QueryCache.endpoint == endpoint,
            )
            .order_by(QueryCache.created_at.desc())
            .limit(30)
            .all()
        )

        if not cached:
            # No cached queries to match against — just normalise
            return QueryMatchResult(
                is_existing=False,
                matched_query_hash=None,
                normalized_query=query.strip(),
            )

        cached_list = [
            {"hash": c.query_hash, "text": c.query_text}
            for c in cached
            if _has_keyword_overlap(query, c.query_text)
        ]
    finally:
        session.close()

    if not cached_list:
        # No cached query shares even a single keyword — skip Ollama
        return QueryMatchResult(
            is_existing=False,
            matched_query_hash=None,
            normalized_query=query.strip(),
        )

    user_prompt = (
        f'User query: "{query}"\n\n'
        f"Cached queries:\n{json.dumps(cached_list, indent=2)}"
    )

    try:
        with custom_span("query_matcher_ollama"):
            result = await Runner.run(_match_agent, input=user_prompt)
        return result.final_output  # type: ignore[return-value]
    except Exception:
        log.warning("Ollama query matcher unavailable, skipping fuzzy match",
                     exc_info=True)
        return None
