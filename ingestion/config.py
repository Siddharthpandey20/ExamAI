"""
Ingestion configuration — single source of truth for paths and settings.
"""

import os

# ── Paths ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
TRACKER_FILE = os.path.join(BASE_DIR, "ingestion", "processed.json")

# ── Supported file types ─────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".ppt"}

# ── OCR settings ─────────────────────────────────────────────────────────
OCR_LANG = "en"

# ── Ollama settings ──────────────────────────────────────────────────────
# Native Ollama API (/api/generate), so the /v1 suffix must be stripped if
# the shared OLLAMA_BASE_URL value carries it.
_OLLAMA_RAW = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_BASE_URL = _OLLAMA_RAW[:-3].rstrip("/") if _OLLAMA_RAW.endswith("/v1") else _OLLAMA_RAW
OLLAMA_MODEL = "llama3:latest"

# ── Parallelism ──────────────────────────────────────────────────────────
MAX_WORKERS = 4