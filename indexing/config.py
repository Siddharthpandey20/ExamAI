"""
config.py — Configuration for the indexing pipeline.

Paths, model names, and tuning constants.
Both databases live in the ExamAI root directory.
"""

import os

# ── Paths ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "knowledge")
DATA_DIR = os.path.join(BASE_DIR, "data")

# Databases — stored in the ExamAI root, not inside indexing/
SQLITE_DB_PATH = os.path.join(BASE_DIR, "examai.db")
SQLITE_DB_URL = f"sqlite:///{SQLITE_DB_PATH}"
CHROMA_DB_DIR = os.path.join(BASE_DIR, "chromadb_store")
CHROMA_COLLECTION = "slides"

# ── Embedding model ──────────────────────────────────────────────────────
EMBEDDING_MODEL = "intfloat/e5-large-v2"   
EMBEDDING_BATCH_SIZE = 64               # slides per batch for encode()

# ── Pipeline tuning ──────────────────────────────────────────────────────
MAX_WORKERS = 4                         # threads for parallel I/O


# ── Subject directory helpers ────────────────────────────────────────────

def get_subject_dirs(subject: str) -> dict[str, str]:
    """Return paths for a subject's data directories."""
    base = os.path.join(DATA_DIR, subject)
    return {
        "base": base,
        "uploads": os.path.join(base, "uploads"),
        "pyq_uploads": os.path.join(base, "pyq_uploads"),
        "knowledge": os.path.join(base, "knowledge"),
    }


def ensure_subject_dirs(subject: str):
    """Create all directories for a subject if they don't exist."""
    dirs = get_subject_dirs(subject)
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
