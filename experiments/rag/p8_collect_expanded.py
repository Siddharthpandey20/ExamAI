"""
Step 2 — run the expanded evaluation (250 original + 40 negation items) using
the new `stats` out-parameter, and prove the plumbing changed nothing.

Two jobs:

1. INERTNESS ON REAL DATA. The unit tests prove the default path is unchanged
   against stubs. This re-runs the 250 original items through the modified
   engine and diffs the retrieved slide ids against the rows recorded BEFORE
   the change (p5_rewriting_rows.json, "baseline"). Any difference is a
   regression, and stubs would not have caught it.

2. Collect dense_top1 for the expanded set, now read from the SAME retrieval
   call that produced the ranking rather than from a second Chroma query. The
   earlier scripts issued their own query to get distances; if that query ever
   diverged from the one inside run_hybrid_search, every threshold number would
   have been measured against the wrong retrieval. Using stats removes that
   whole class of error.

Read-only. Writes experiments/benchmarks/expanded_features.json.
"""

import json
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from indexing.database import SessionFactory    # noqa: E402
from indexing.db_chroma import ChromaStore      # noqa: E402
from indexing.embedder import Embedder          # noqa: E402
from engine.tools import run_hybrid_search      # noqa: E402

HARD = REPO / "experiments" / "benchmarks" / "hard_eval_set.json"
NEG = REPO / "experiments" / "benchmarks" / "negation_eval.json"
PRIOR = REPO / "experiments" / "benchmarks" / "hard_features.json"
OUT = REPO / "experiments" / "benchmarks" / "expanded_features.json"
TOP_K = 5


def main():
    items = json.loads(HARD.read_text(encoding="utf-8"))
    neg = json.loads(NEG.read_text(encoding="utf-8"))
    items = items + neg["retrieval_items"]
    print(f"evaluating {len(items)} items "
          f"({len(neg['retrieval_items'])} of them new negation items)\n")

    embedder, chroma = Embedder(), ChromaStore()
    session = SessionFactory()
    rows = []
    try:
        for n, it in enumerate(items, 1):
            stats = {}
            t0 = time.perf_counter()
            res = run_hybrid_search(it["question"], it["subject"], session,
                                    embedder, chroma, top_k=TOP_K, stats=stats)
            latency_ms = (time.perf_counter() - t0) * 1000
            ids = [r["slide_id"] for r in res]
            gold = it.get("gold_slide_id")
            rows.append({
                "id": it["id"], "category": it["category"],
                "subject": it["subject"], "answerable": it["answerable"],
                "gold_slide_id": gold, "retrieved": ids,
                "hit_at_1": bool(gold) and ids[:1] == [gold],
                "hit_at_3": bool(gold) and gold in ids[:3],
                "hit_at_5": bool(gold) and gold in ids,
                "rank_of_gold": (ids.index(gold) + 1) if gold and gold in ids else None,
                "dense_top1": stats["dense_top1"],
                "dense_mean": stats["dense_mean"],
                "top_result_distance": stats["top_result_distance"],
                "n_dense": stats["n_dense"], "n_sparse": stats["n_sparse"],
                "latency_ms": round(latency_ms, 2),
            })
            if n % 50 == 0:
                print(f"  {n}/{len(items)}", flush=True)
    finally:
        session.close()

    # ── 1. inertness check against the pre-change run ────────────────────
    print("\n" + "=" * 70)
    print("INERTNESS CHECK - retrieval before vs after the stats parameter")
    print("=" * 70)
    prior = {r["id"]: r for r in json.loads(PRIOR.read_text(encoding="utf-8"))}
    now = {r["id"]: r for r in rows}
    shared = [i for i in prior if i in now]
    id_mismatch = [i for i in shared if prior[i]["retrieved"] != now[i]["retrieved"]]
    hit_mismatch = [i for i in shared if prior[i]["hit_at_1"] != now[i]["hit_at_1"]]
    print(f"items compared            : {len(shared)}")
    print(f"retrieved-id differences  : {len(id_mismatch)}")
    print(f"hit@1 differences         : {len(hit_mismatch)}")
    if id_mismatch:
        print("REGRESSION - retrieval changed for:")
        for i in id_mismatch[:10]:
            print(f"    {i}: {prior[i]['retrieved']} -> {now[i]['retrieved']}")
    else:
        print("PASS - retrieval is identical on all shared items")

    # The distances now come from inside run_hybrid_search instead of a
    # separate query. If the old second query was equivalent they will match.
    dist_diff = [(i, prior[i]["dense_top1"], now[i]["dense_top1"])
                 for i in shared
                 if prior[i]["dense_top1"] is not None
                 and now[i]["dense_top1"] is not None
                 and abs(prior[i]["dense_top1"] - now[i]["dense_top1"]) > 1e-9]
    print(f"dense_top1 differences    : {len(dist_diff)}")
    if dist_diff:
        print("  (the separate probe query was NOT equivalent to the real one)")
        for i, a, b in dist_diff[:5]:
            print(f"    {i}: probe {a:.6f} vs in-search {b:.6f}")

    # ── 2. how the new negation items behave ─────────────────────────────
    print("\n" + "=" * 70)
    print("NEGATION ITEMS - retrieval quality vs their source questions")
    print("=" * 70)
    negrows = [r for r in rows if r["category"] == "positive_negation"]
    posrows = [r for r in rows if r["category"] == "positive"]
    for label, grp in (("positive (source)", posrows), ("positive_negation", negrows)):
        n = len(grp)
        mrr = sum(1 / r["rank_of_gold"] if r["rank_of_gold"] else 0 for r in grp) / n
        d = [r["dense_top1"] for r in grp if r["dense_top1"] is not None]
        print(f"{label:20s} n={n:3d}  R@1 {sum(r['hit_at_1'] for r in grp)/n:.3f}  "
              f"R@5 {sum(r['hit_at_5'] for r in grp)/n:.3f}  MRR {mrr:.3f}  "
              f"dense {statistics.mean(d):.4f}")

    print(f"\n{'class':24s} {'n':>4s} {'dense_top1':>11s} {'range':>19s}")
    for cat in ("positive", "positive_noisy", "positive_keyword",
                "positive_verbose", "positive_negation", "in_subject_absent",
                "cross_subject_overlap", "out_of_domain"):
        grp = [r for r in rows if r["category"] == cat
               and r["dense_top1"] is not None]
        if not grp:
            continue
        d = [r["dense_top1"] for r in grp]
        print(f"{cat:24s} {len(grp):>4d} {statistics.mean(d):>11.4f} "
              f"{min(d):>8.4f}-{max(d):<10.4f}")

    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lat = sorted(r["latency_ms"] for r in rows)
    print(f"\nlatency p50 {statistics.median(lat):.1f} ms  "
          f"p95 {lat[int(len(lat)*0.95)]:.1f} ms")
    print(f"saved {len(rows)} rows -> {OUT}")


if __name__ == "__main__":
    main()
