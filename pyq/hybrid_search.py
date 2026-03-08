"""
hybrid_search.py — Reciprocal Rank Fusion (RRF) combining dense + sparse search.

For each question:
  1. Dense search  → ChromaDB cosine similarity (top N)
  2. Sparse search → BM25 on slide text (top N)
  3. RRF score per unique slide_id:
       RRF(d) = Σ  1 / (K + rank_i(d))
     where K is a smoothing constant (default 60)

Only slides in the Top K RRF results AND above the score threshold
are considered matches.
"""

import logging

from sqlalchemy.orm import Session

from indexing.db_chroma import ChromaStore
from indexing.embedder import Embedder
from pyq.bm25_search import BM25Index
from pyq.config import DENSE_TOP_N, SPARSE_TOP_N, RRF_K, RRF_TOP_K, RRF_SCORE_THRESHOLD
from pyq.schemas import RRFResult

log = logging.getLogger(__name__)


def _parse_chroma_id(chroma_id: str) -> tuple[int, int]:
    """
    Parse ChromaDB ID format 'doc{doc_id}_page{page_number}'.
    Returns (doc_id, page_number).
    """
    # e.g. "doc1_page3" → (1, 3)
    parts = chroma_id.replace("doc", "").replace("page", "").split("_")
    return int(parts[0]), int(parts[1])


def _dense_search(
    query: str,
    embedder: Embedder,
    chroma: ChromaStore,
    top_n: int = DENSE_TOP_N,
) -> list[dict]:
    """
    Run dense (vector) search via ChromaDB.

    Returns list of dicts with: slide_id_key, doc_id, page_number, source_file, rank
    where slide_id_key is "doc{doc_id}_page{page_number}" for matching.
    """
    query_embedding = embedder.embed_query(query)
    results = chroma.query(query_embedding=query_embedding, n_results=top_n)

    ranked = []
    if results and results["ids"] and results["ids"][0]:
        for rank, (cid, meta) in enumerate(
            zip(results["ids"][0], results["metadatas"][0]), start=1
        ):
            doc_id, page_number = _parse_chroma_id(cid)
            ranked.append({
                "slide_id_key": f"{doc_id}_{page_number}",
                "doc_id": doc_id,
                "page_number": page_number,
                "source_file": meta.get("source_file", ""),
                "rank": rank,
            })

    return ranked


def _sparse_search(
    query: str,
    bm25_index: BM25Index,
    top_n: int = SPARSE_TOP_N,
) -> list[dict]:
    """
    Run sparse (BM25) search.

    Returns list of dicts with: slide_id, slide_id_key, doc_id, page_number, source_file, rank
    """
    bm25_results = bm25_index.search(query, top_n=top_n)

    ranked = []
    for rank, r in enumerate(bm25_results, start=1):
        ranked.append({
            "slide_id": r["slide_id"],
            "slide_id_key": f"{r['doc_id']}_{r['page_number']}",
            "doc_id": r["doc_id"],
            "page_number": r["page_number"],
            "source_file": r["source_file"],
            "rank": rank,
        })

    return ranked


def _compute_rrf(
    dense_results: list[dict],
    sparse_results: list[dict],
    session: Session,
    k: int = RRF_K,
) -> list[RRFResult]:
    """
    Compute Reciprocal Rank Fusion scores.

    RRF(d) = Σ 1/(K + rank_i(d))

    Returns list of RRFResult sorted by descending RRF score.
    """
    from indexing.models import Slide

    # Build rank maps: slide_id_key → rank
    dense_rank_map = {r["slide_id_key"]: r["rank"] for r in dense_results}
    sparse_rank_map = {r["slide_id_key"]: r["rank"] for r in sparse_results}

    # Collect all unique slide keys
    all_keys = set(dense_rank_map.keys()) | set(sparse_rank_map.keys())

    # Build metadata lookup from both result lists
    meta_lookup: dict[str, dict] = {}
    for r in dense_results + sparse_results:
        if r["slide_id_key"] not in meta_lookup:
            meta_lookup[r["slide_id_key"]] = r

    # Compute RRF scores
    rrf_results = []
    for key in all_keys:
        score = 0.0
        d_rank = dense_rank_map.get(key)
        s_rank = sparse_rank_map.get(key)

        if d_rank is not None:
            score += 1.0 / (k + d_rank)
        if s_rank is not None:
            score += 1.0 / (k + s_rank)

        meta = meta_lookup[key]
        doc_id = meta["doc_id"]
        page_number = meta["page_number"]

        # Resolve the actual slide_id from SQLite
        slide = (
            session.query(Slide)
            .filter(Slide.doc_id == doc_id, Slide.page_number == page_number)
            .first()
        )
        if not slide:
            continue

        rrf_results.append(RRFResult(
            slide_id=slide.id,
            doc_id=doc_id,
            page_number=page_number,
            source_file=meta.get("source_file", ""),
            rrf_score=score,
            dense_rank=d_rank,
            sparse_rank=s_rank,
        ))

    rrf_results.sort(key=lambda r: r.rrf_score, reverse=True)
    return rrf_results


def hybrid_search(
    query: str,
    session: Session,
    embedder: Embedder,
    chroma: ChromaStore,
    bm25_index: BM25Index,
    top_k: int = RRF_TOP_K,
    threshold: float = RRF_SCORE_THRESHOLD,
) -> list[RRFResult]:
    """
    Run hybrid search (dense + sparse + RRF fusion) for a single question.

    Parameters
    ----------
    query : str
        The exam question text.
    session : Session
        SQLAlchemy session for slide_id resolution.
    embedder : Embedder
        Sentence-transformer encoder for dense search.
    chroma : ChromaStore
        ChromaDB instance for dense search.
    bm25_index : BM25Index
        Pre-built BM25 index for sparse search.
    top_k : int
        Only return top K results after RRF sorting.
    threshold : float
        Minimum RRF score to count as a match.

    Returns
    -------
    list[RRFResult]
        Matched slides with RRF scores, filtered by top_k and threshold.
    """
    # Step 1: Dense search (ChromaDB)
    dense_results = _dense_search(query, embedder, chroma)
    log.debug(f"[Hybrid] Dense search returned {len(dense_results)} results")

    # Step 2: Sparse search (BM25)
    sparse_results = _sparse_search(query, bm25_index)
    log.debug(f"[Hybrid] Sparse search returned {len(sparse_results)} results")

    # Step 3: RRF fusion
    rrf_results = _compute_rrf(dense_results, sparse_results, session)

    # Step 4: Apply top_k and threshold filters
    filtered = [r for r in rrf_results[:top_k] if r.rrf_score >= threshold]

    log.info(
        f"[Hybrid] Q: '{query[:60]}...' → "
        f"{len(dense_results)} dense + {len(sparse_results)} sparse "
        f"→ {len(rrf_results)} fused → {len(filtered)} matched"
    )

    return filtered
