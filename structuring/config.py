"""
config.py — Configuration for the structuring module.

Centralized settings for:
  - Ollama  (file-level agent)  via OpenAI Agents SDK + OpenAIProvider
  - Gemini (slide-level agent) via OpenAI Agents SDK + OpenAIProvider
"""

import os

# ── Paths ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
TRACKER_FILE = os.path.join(BASE_DIR, "structuring", "structured.json")

# ── Ollama (File-Level Agent) ────────────────────────────────────────────
OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
OLLAMA_MODEL = "llama3"

# Max chars for preview sent to Ollama Step 1.
# If entire file is shorter, send the whole thing.
PREVIEW_CHAR_LIMIT = 6000

# ── Groq (Slide-Level Agent) ────────────────────────────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = "llama-3.3-70b-versatile"

# ── Gemini(Slide-Level Agent) ────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-2.5-flash"

# Sliding window: slides per Gemini API call
SLIDE_BATCH_SIZE = 25

# Rate limiting: max calls per minute
GROQ_MAX_CALLS_PER_MINUTE = 20
GEMINI_MAX_CALLS_PER_MINUTE = 10
