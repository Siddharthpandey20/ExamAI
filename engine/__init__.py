"""
engine — Search and exam intelligence module.

Provides two modes for answering student queries:
  Fast Mode:      hybrid search → context build → Groq → response  (1 LLM call)
  Reasoning Mode: AI agent with DB/search tools → multi-step reasoning (N calls)

Heavy resources (embedding model, ChromaDB) are lazy-loaded singletons
so they are initialized once and shared across requests.
"""

import threading
import logging

log = logging.getLogger(__name__)

# ── Lazy singletons ──────────────────────────────────────────────────────
_embedder = None
_chroma = None
_init_lock = threading.Lock()


def get_embedder():
    """Return the shared Embedder instance (lazy, thread-safe)."""
    global _embedder
    if _embedder is None:
        with _init_lock:
            if _embedder is None:
                from indexing.embedder import Embedder
                _embedder = Embedder()
    return _embedder


def get_chroma():
    """Return the shared ChromaStore instance (lazy, thread-safe)."""
    global _chroma
    if _chroma is None:
        with _init_lock:
            if _chroma is None:
                from indexing.db_chroma import ChromaStore
                _chroma = ChromaStore()
    return _chroma
