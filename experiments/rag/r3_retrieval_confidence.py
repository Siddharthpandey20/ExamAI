"""
R3 — can retrieval confidence be estimated without asking another LLM?

Question: do cheap, deterministic signals available at retrieval time predict
whether the gold slide was actually retrieved? If so, a low-confidence branch
could retry or abstain instead of answering from weak evidence.

Signals are derived only from what run_hybrid_search already returns, so a
positive result would cost nothing at query time.

Isolated: reads the committed evaluation set and queries the production
retrieval function READ-ONLY. Writes nothing to the database or to eval/.

Usage:  python experiments/rag/r3_retrieval_confidence.py
Writes: experiments/benchmarks/r3_confidence.json
"""

import json
import re
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from indexing.database import SessionFactory          # noqa: E402
from indexing.db_chroma import ChromaStore            # noqa: E402
from indexing.embedder import Embedder                # noqa: E402
from engine.tools import run_hybrid_search            # noqa: E402

OUT = REPO / "experiments" / "benchmarks" / "r3_confidence.json"
EVAL_SET = REPO / "eval" / "eval_set.json"
TOP_K = 5


def _tok(text):
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def signals(query, results):
    """Deterministic confidence signals from a fused result list."""
    if not results:
        return None
    scores = [r["rrf_score"] for r in results]
    top = results[0]

    both = [r for r in results
            if r.get("dense_rank") is not None and r.get("sparse_rank") is not None]
    q = _tok(query)
    top_text = _tok(f"{top.get('summary','')} {top.get('concepts','')}")

    return {
        "top1_rrf": scores[0],
        "gap_1_2": scores[0] - scores[1] if len(scores) > 1 else scores[0],
        "gap_ratio": (scores[1] / scores[0]) if len(scores) > 1 and scores[0] else 0.0,
        "top1_in_both_lists": 1.0 if (top.get("dense_rank") is not None
                                      and top.get("sparse_rank") is not None) else 0.0,
        "n_in_both_lists": float(len(both)),
        "n_candidates": float(len(results)),
        "mean_rrf": statistics.mean(scores),
        "score_spread": max(scores) - min(scores),
        "lexical_overlap": (len(q & top_text) / len(q)) if q else 0.0,
    }


def best_threshold(values, labels, higher_is_better=True):
    """Best achievable accuracy separating labels with a single threshold."""
    if len(set(labels)) < 2:
        return None
    best = {"accuracy": 0.0, "threshold": None}
    for t in sorted(set(values)):
        pred = [(v >= t) if higher_is_better else (v <= t) for v in values]
        acc = sum(int(p == bool(l)) for p, l in zip(pred, labels)) / len(labels)
        if acc > best["accuracy"]:
            best = {"accuracy": round(acc, 4), "threshold": round(t, 6)}
    return best


def main():
    eval_set = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    embedder, chroma = Embedder(), ChromaStore()
    session = SessionFactory()

    rows = []
    try:
        for qa in eval_set:
            res = run_hybrid_search(qa["question"], qa["subject"], session,
                                    embedder, chroma, top_k=TOP_K)
            sig = signals(qa["question"], res)
            if sig is None:
                continue
            ids = [r["slide_id"] for r in res]
            rows.append({
                "id": qa["id"],
                "question_type": qa.get("question_type", "?"),
                "hit_at_1": ids[0] == qa["gold_slide_id"],
                "hit_at_5": qa["gold_slide_id"] in ids,
                **sig,
            })
    finally:
        session.close()

    n = len(rows)
    print(f"R3 — retrieval confidence signals over {n} questions\n")

    for outcome in ("hit_at_1", "hit_at_5"):
        labels = [r[outcome] for r in rows]
        pos, neg = sum(labels), n - sum(labels)
        base = max(pos, neg) / n
        print(f"=== predicting {outcome} "
              f"({pos} correct / {neg} incorrect, majority baseline {base:.3f}) ===")
        print(f"{'signal':22s} {'mean(correct)':>14s} {'mean(wrong)':>12s} "
              f"{'sep':>8s} {'best acc':>9s} {'thresh':>10s}")

        table = []
        for key in signals("x", [{"rrf_score": 0, "summary": "", "concepts": "",
                                  "dense_rank": None, "sparse_rank": None}]):
            vals = [r[key] for r in rows]
            good = [v for v, l in zip(vals, labels) if l]
            bad = [v for v, l in zip(vals, labels) if not l]
            if not good or not bad:
                continue
            mg, mb = statistics.mean(good), statistics.mean(bad)
            pooled = statistics.pstdev(vals) or 1e-9
            sep = (mg - mb) / pooled          # standardised mean difference
            bt = best_threshold(vals, labels, higher_is_better=(mg >= mb))
            table.append((key, mg, mb, sep, bt))

        for key, mg, mb, sep, bt in sorted(table, key=lambda x: -abs(x[3])):
            print(f"{key:22s} {mg:>14.4f} {mb:>12.4f} {sep:>8.2f} "
                  f"{bt['accuracy']:>9.3f} {bt['threshold']:>10.4f}")
        print()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()
