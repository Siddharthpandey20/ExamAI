"""
embedder.py — Sentence-transformer embedding wrapper using intfloat/e5-large-v2.

Model: intfloat/e5-large-v2  (1024 dims, HuggingFace — no API key required)
  - Downloads automatically on first run via sentence-transformers
  - ~1.3 GB model size

IMPORTANT: e5 models require instruction prefixes:
  - "passage: " for documents being indexed
  - "query: "   for search queries at retrieval time
Without these prefixes, embedding quality degrades significantly.

The embedding input for each slide is a merged string:
    summary + " | " + concepts + " | " + cleaned_text
"""

import logging

from sentence_transformers import SentenceTransformer

from indexing.config import EMBEDDING_MODEL, EMBEDDING_BATCH_SIZE

log = logging.getLogger(__name__)

# e5 model instruction prefixes
_PASSAGE_PREFIX = "passage: "
_QUERY_PREFIX = "query: "


class Embedder:
    """Sentence-transformer encoder tuned for intfloat/e5-large-v2."""

    def __init__(self, model_name: str = EMBEDDING_MODEL):
        log.info(f"[Embedder] Loading model '{model_name}' ...")
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_sentence_embedding_dimension()
        log.info(f"[Embedder] Ready — dimension={self.dim}")

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        """
        Encode document passages for indexing.
        Adds "passage: " prefix as required by e5 models.

        Returns list[list[float]] — one 1024-dim vector per input.
        """
        prefixed = [f"{_PASSAGE_PREFIX}{t}" for t in texts]
        embeddings = self.model.encode(
            prefixed,
            batch_size=EMBEDDING_BATCH_SIZE,
            show_progress_bar=len(texts) > EMBEDDING_BATCH_SIZE,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        """
        Encode a search query for retrieval.
        Adds "query: " prefix as required by e5 models.

        Returns list[float] — single 1024-dim vector.
        """
        prefixed = f"{_QUERY_PREFIX}{text}"
        embedding = self.model.encode(
            [prefixed],
            normalize_embeddings=True,
        )
        return embedding[0].tolist()


def build_embed_text(summary: str, concepts: str, raw_text: str) -> str:
    """
    Merge slide fields into a single string for embedding.

    Format: "summary | concepts | cleaned_text"
    Truncated to ~2000 chars to stay within e5 model context.
    """
    parts = []
    if summary:
        parts.append(summary.strip())
    if concepts:
        parts.append(concepts.strip())
    if raw_text:
        parts.append(raw_text.strip())

    merged = " | ".join(parts)

    max_chars = 2000
    if len(merged) > max_chars:
        merged = merged[:max_chars]

    return merged
