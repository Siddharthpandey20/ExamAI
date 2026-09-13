"""
Q1 — audit the coverage confidence gate that is ALREADY IN PRODUCTION.

engine/fast_mode.py::fast_coverage classifies a topic as covered like this:

    top_score = slides[0].get("rrf_score", 0)
    if   top_score > 0.025: confidence = "high"
    elif top_score > 0.015: confidence = "medium"
    else:                   confidence = "low"
    ...
    "covered": confidence in ("high", "medium")

That boolean is returned to the user, and the confidence string is also
interpolated into the LLM prompt ("Match confidence: high (top RRF score ...)").

Earlier phases established that RRF score is structurally rank-only:
1/(RRF_K + rank) with RRF_K = 60, so a rank-1 hit contributes exactly
1/61 = 0.01639. The arithmetic therefore predicts:

    found by BOTH retrievers at rank 1 -> 0.01639 * 2 = 0.03279 -> "high"
    found by ONE  retriever  at rank 1 -> 0.01639          -> "medium"
    "low" requires <= 0.015, which a rank-1 hit cannot produce at all

If that holds, `covered` is True whenever ANY slide survives filtering,
regardless of how unrelated it is, and the only path to "not covered" is an
empty result list. The gate would not be measuring coverage; it would be
measuring whether dense and sparse retrieval happened to agree.

This script tests the prediction on REAL user queries taken from query_cache -
including "kaju katli" (an Indian sweet) asked against the ML corpus.

READ-ONLY. Nothing is written, no cache entry is created or modified.
"""

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from indexing.database import SessionFactory      # noqa: E402
from indexing.db_chroma import ChromaStore        # noqa: E402
from indexing.embedder import Embedder            # noqa: E402
from indexing.models import QueryCache            # noqa: E402
from engine.tools import run_hybrid_search        # noqa: E402

OUT = REPO / "experiments" / "benchmarks" / "q1_coverage_audit.json"
RRF_K = 60


def classify(top_score):
    """Verbatim reproduction of the production rule."""
    if top_score > 0.025:
        return "high"
    if top_score > 0.015:
        return "medium"
    return "low"


def main():
    print("Predicted RRF scores for a rank-1 hit (RRF_K = %d):" % RRF_K)
    one = 1.0 / (RRF_K + 1)
    print(f"  found by one retriever at rank 1 : {one:.5f} -> {classify(one)}")
    print(f"  found by both at rank 1          : {2*one:.5f} -> {classify(2*one)}")
    print(f"  found by one at rank 2           : {1/(RRF_K+2):.5f} -> "
          f"{classify(1/(RRF_K+2))}")
    print(f"  'low' needs top_score <= 0.015, i.e. rank >= "
          f"{int(1/0.015) - RRF_K} for a single retriever\n")

    session = SessionFactory()
    try:
        cached = session.query(QueryCache).all()
        queries = []
        seen = set()
        for c in cached:
            q = (c.query_text or "").strip()
            if (not q or q.startswith(("revision:", "study-plan:"))
                    or (q, c.subject) in seen):
                continue
            seen.add((q, c.subject))
            queries.append((q, c.subject, c.endpoint))

        print(f"replaying {len(queries)} real user queries from query_cache\n")
        embedder, chroma = Embedder(), ChromaStore()

        rows = []
        for q, subject, endpoint in queries:
            stats = {}
            slides = run_hybrid_search(q, subject, session, embedder, chroma,
                                       top_k=8, stats=stats)
            top = slides[0].get("rrf_score", 0) if slides else 0
            conf = classify(top) if slides else "none"
            rows.append({
                "query": q, "subject": subject, "endpoint": endpoint,
                "n_words": len(q.split()),
                "n_slides": len(slides),
                "rrf_top1": top,
                "confidence": conf,
                "covered": conf in ("high", "medium"),
                "dense_top1": stats["dense_top1"],
                "both_retrievers": bool(slides
                                        and slides[0].get("dense_rank") is not None
                                        and slides[0].get("sparse_rank") is not None),
                "top_slide_summary": (slides[0].get("summary", "")[:70]
                                      if slides else ""),
            })
    finally:
        session.close()

    print("=" * 100)
    print(f"{'query':42s} {'subj':5s} {'n':>2s} {'rrf':>7s} {'conf':>6s} "
          f"{'covered':>7s} {'dense':>7s}")
    print("=" * 100)
    for r in sorted(rows, key=lambda x: -x["dense_top1"]):
        print(f"{r['query'][:42]:42s} {r['subject'][:5]:5s} {r['n_slides']:>2d} "
              f"{r['rrf_top1']:>7.5f} {r['confidence']:>6s} "
              f"{str(r['covered']):>7s} {r['dense_top1']:>7.4f}")

    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)
    print("confidence labels produced :", dict(Counter(r["confidence"] for r in rows)))
    print("covered=True               :",
          f"{sum(1 for r in rows if r['covered'])}/{len(rows)}")
    distinct = sorted({round(r["rrf_top1"], 5) for r in rows})
    print("distinct rrf_top1 values   :", distinct)
    print("distinct dense_top1 range  : "
          f"{min(r['dense_top1'] for r in rows):.4f} - "
          f"{max(r['dense_top1'] for r in rows):.4f}")

    # The decisive comparison: queries whose answer is obviously absent.
    print("\nObviously out-of-domain queries, and what the gate says:")
    for r in rows:
        ql = r["query"].lower()
        if any(k in ql for k in ("kaju", "katli", "linear algebra",
                                 "linear regression")):
            print(f"  {r['query']!r} against {r['subject']}")
            print(f"     -> covered={r['covered']} confidence={r['confidence']} "
                  f"rrf={r['rrf_top1']:.5f} dense={r['dense_top1']:.4f}")
            print(f"     -> top slide: {r['top_slide_summary']!r}")

    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
