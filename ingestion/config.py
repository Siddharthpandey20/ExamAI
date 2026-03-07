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
OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "llama3:latest"

# ── Parallelism ──────────────────────────────────────────────────────────
MAX_WORKERS = 4