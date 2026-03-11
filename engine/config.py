"""
engine/config.py — Configuration for search & exam intelligence engine.

Two modes:
  - Fast Mode:      hybrid search → context build → Groq format → response
  - Reasoning Mode: AI agent with DB/search tools → multi-step reasoning → response

LLM:
  - Groq (free tier) with 3-model fallback chain + round-robin distribution
  - Ollama Llama3 (local) — for structured Pydantic output when needed
"""

import os

# ── Groq API (OpenAI-compatible) ─────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Fallback model chain — ordered by quality.
# Tokens distribute across models to avoid hitting any single limit.
GROQ_MODELS = [
    {
        "model": "llama-3.3-70b-versatile",
        "rpm": 30,           # requests / minute
        "tpm": 12_000,       # tokens / minute
        "rpd": 1_000,        # requests / day
        "tpd": 100_000,      # tokens / day
    },
    {
        "model": "openai/gpt-oss-120b",
        "rpm": 60,
        "tpm": 10_000,
        "rpd": 1_000,
        "tpd": 300_000,
    },
    {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "rpm": 30,
        "tpm": 30_000,
        "rpd": 1_000,
        "tpd": 500_000,
    },
]

# Legacy single-model alias (for reasoning agent init)
GROQ_MODEL = GROQ_MODELS[0]["model"]

# ── Ollama (local, for structured output) ────────────────────────────────
OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
OLLAMA_MODEL = "llama3"

# ── Search tuning ────────────────────────────────────────────────────────
SEARCH_TOP_K = 12          # slides retrieved from hybrid search
CONTEXT_MAX_SLIDES = 6     # max slides sent to LLM in context window
MIN_SLIDE_TEXT_LEN = 30    # filter heading-only slides (< N chars)
RRF_K = 60                 # RRF smoothing constant

# ── Context limits (chars, ~4 chars/token) ───────────────────────────────
MAX_CONTEXT_CHARS = 6000   # max chars sent as slide context per LLM call
CHUNK_SIZE_CHARS = 3000    # per-chunk size when splitting large context
TOOL_OUTPUT_MAX_CHARS = 2500  # max chars per tool output in reasoning mode

# ── Priority thresholds ─────────────────────────────────────────────────
HIGH_PRIORITY_THRESHOLD = 0.4
MEDIUM_PRIORITY_THRESHOLD = 0.15

# ── Cache ────────────────────────────────────────────────────────────────
# Cache persists until new docs/PYQ are added for the subject, or user
# forces a refresh.  No time-based TTL.
