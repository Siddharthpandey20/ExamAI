"""
config.py — Configuration for the PYQ (Past Year Question) pipeline.

Paths, model settings, search thresholds, and scoring weights.
"""

import os

# ── Paths ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYQ_UPLOAD_DIR = os.path.join(BASE_DIR, "pyq_uploads")
TRACKER_FILE = os.path.join(BASE_DIR, "pyq", "pyq_processed.json")

# ── Ollama (Llama 3 for question extraction) ─────────────────────────────
OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
OLLAMA_MODEL = "llama3"

# ── Search parameters ────────────────────────────────────────────────────
DENSE_TOP_N = 20          # top N results from ChromaDB dense search
SPARSE_TOP_N = 20         # top N results from BM25 sparse search
RRF_K = 60                # RRF smoothing constant (standard default)
RRF_TOP_K = 5             # only consider top K after RRF fusion
RRF_SCORE_THRESHOLD = 0.01  # minimum RRF score to count as a "match"

# ── Importance scoring weights ───────────────────────────────────────────
WEIGHT_PYQ_FREQUENCY = 0.5
WEIGHT_SLIDE_EMPHASIS = 0.3
WEIGHT_CONCEPT_IMPORTANCE = 0.2

# ── Parallelism ──────────────────────────────────────────────────────────
MAX_WORKERS = 3             # concurrent PYQ files being processed

# ── Supported file types for PYQ upload ──────────────────────────────────
SUPPORTED_EXTENSIONS = {".pdf", ".pptx", ".ppt"}
