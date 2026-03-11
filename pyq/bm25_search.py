"""
bm25_search.py — BM25 sparse search over slide texts stored in SQLite.

Builds an in-memory BM25 index from all embedded slides, then supports
querying by question text. Returns ranked slide IDs with BM25 scores.

Uses rank_bm25 library for the scoring algorithm.
"""

import logging
import re

from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session, joinedload

from indexing.models import Slide

log = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer with lowercasing."""
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    return tokens


class BM25Index:
    """
    In-memory BM25 index built from all embedded slides in SQLite.

    Each slide's searchable text is: summary + concepts + raw_text
    (mirrors the embedding text construction in the indexing pipeline).
    """

    def __init__(self, session: Session):
        """
        Build the BM25 index from all embedded slides.

        Parameters
        ----------
        session : Session
            Active SQLAlchemy session to read slide data.
        """
        # Eager-load the document relationship so we can read
        # source_file after the session is closed.
        slides = (
            session.query(Slide)
            .filter(Slide.is_embedded == True)
            .options(joinedload(Slide.document))
            .order_by(Slide.id)
            .all()
        )

        if not slides:
            log.warning("[BM25] No embedded slides found — index will be empty")
            self._slide_data: dict[int, dict] = {}
            self._bm25 = None
            return

        # Store plain dicts instead of ORM objects so the index
        # stays usable after the building session is closed.
        self._slide_data: dict[int, dict] = {}
        self._index_order: list[int] = []  # slide_id in BM25 corpus order
        corpus: list[list[str]] = []

        for slide in slides:
            parts = []
            if slide.summary:
                parts.append(slide.summary)
            if slide.concepts:
                parts.append(slide.concepts)
            if slide.raw_text:
                parts.append(slide.raw_text)
            text = " ".join(parts)

            tokens = _tokenize(text)
            if not tokens:
                continue

            self._slide_data[slide.id] = {
                "doc_id": slide.doc_id,
                "page_number": slide.page_number,
                "source_file": slide.document.filename if slide.document else "",
            }
            self._index_order.append(slide.id)
            corpus.append(tokens)

        if not corpus:
            log.warning("[BM25] All slides had empty text — index will be empty")
            self._bm25 = None
            return

        self._bm25 = BM25Okapi(corpus)
        log.info(f"[BM25] Index built: {len(corpus)} slides indexed")

    def search(self, query: str, top_n: int = 20) -> list[dict]:
        """
        Search the BM25 index with a query string.

        Parameters
        ----------
        query : str
            The question text to search for.
        top_n : int
            Number of top results to return.

        Returns
        -------
        list[dict]
            Each dict has: slide_id, doc_id, page_number, source_file, bm25_score
            Sorted by descending BM25 score.
        """
        if self._bm25 is None:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)

        # Pair scores with slide IDs and sort descending
        scored = [
            (self._index_order[i], scores[i])
            for i in range(len(scores))
            if scores[i] > 0
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        results = []
        for slide_id, score in scored[:top_n]:
            data = self._slide_data[slide_id]
            results.append({
                "slide_id": slide_id,
                "doc_id": data["doc_id"],
                "page_number": data["page_number"],
                "source_file": data["source_file"],
                "bm25_score": float(score),
            })

        return results
