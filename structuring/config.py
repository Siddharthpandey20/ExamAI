"""
config.py — Configuration for the structuring module.

Centralized settings for Ollama (file-level agent) and Gemini (slide-level agent).
"""

import os

# ── Paths ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
STRUCTURED_DIR = os.path.join(BASE_DIR, "structured_output")
TRACKER_FILE = os.path.join(BASE_DIR, "structuring", "structured.json")

# ── Ollama (File-Level Agent) ────────────────────────────────────────────
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "llama3"

# OpenAI-compatible endpoint for Ollama
OLLAMA_OPENAI_BASE = f"{OLLAMA_BASE_URL}/v1"

# Max characters for the "preview" sent to Ollama Step 1.
# If the entire file is shorter than this, send the whole thing.
PREVIEW_CHAR_LIMIT = 6000

# Max slides to include in a single Ollama chapter-summary call
OLLAMA_CHAPTER_BATCH_SIZE = 20

# ── AI (Slide-Level Agent) ───────────────────────────────────────────
# Set your API key via environment variable: GROQ_API_KEY
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama3-8b-8192"

# OpenAI-compatible endpoint for GROQ
GROQ_OPENAI_BASE = "https://api.groq.com/openai/v1"

# Sliding window: how many slides per GROQ API call
SLIDE_BATCH_SIZE = 12

# Rate limiting: max GROQ API calls per minute
GROQ_MAX_CALLS_PER_MINUTE = 20

# ── General ──────────────────────────────────────────────────────────────
# Timeout for LLM API calls (seconds)
LLM_TIMEOUT = 80
