"""
db_chroma.py — ChromaDB vector store for slide embeddings.

Each slide is stored as:
{
  id:        "doc{doc_id}_page{page_number}"
  embedding: [...]   # from sentence-transformers
  document:  "summary + concepts + cleaned_text merged"
  metadata: {
    source_file, page_number, slide_type, exam_signal,
    concepts, chapter, pyq_hit_count, importance_score
  }
}

ChromaDB is used ONLY for vector search.
All raw data and state live in SQLite.
"""

import logging

import chromadb
from chromadb.config import Settings

from indexing.config import CHROMA_DB_DIR, CHROMA_COLLECTION

log = logging.getLogger(__name__)


class ChromaStore:
    """Persistent ChromaDB collection for slide embeddings."""

    def __init__(self, persist_dir: str = CHROMA_DB_DIR):
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        log.info(
            f"[Chroma] Collection '{CHROMA_COLLECTION}' ready  "
            f"({self.collection.count()} existing records)"
        )

    # ── Write ────────────────────────────────────────────────────────

    def upsert_slides(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ):
        """
        Upsert a batch of slide records.

        Parameters match the ChromaDB collection.upsert signature.
        Uses upsert so re-runs are idempotent.
        """
        self.collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        log.info(f"[Chroma] Upserted {len(ids)} slides")

    # ── Read (for future search) ─────────────────────────────────────

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where: dict | None = None,
    ) -> dict:
        """
        Semantic search over slide embeddings.

        Returns ChromaDB QueryResult dict with keys:
          ids, embeddings, documents, metadatas, distances
        """
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where
        return self.collection.query(**kwargs)

    def delete_by_source(self, source_file: str):
        """Remove all slides belonging to a specific source file."""
        self.collection.delete(where={"source_file": source_file})
        log.info(f"[Chroma] Deleted all slides for source '{source_file}'")

    def count(self) -> int:
        return self.collection.count()
