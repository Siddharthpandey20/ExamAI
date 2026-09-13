"""
Phase 2 — run the production retrieval path over the hard evaluation set and
capture every signal that could support an abstention decision.

Collects, per question:
  dense      top-1 / mean / min cosine distance from Chroma (currently discarded
             by run_hybrid_search)
  rrf        top-1, mean, gap, ratio from the fused ranking
  agreement  whether the top hit appears in both dense and sparse lists
  lexical    query-term coverage of the top slide, and of the whole top-k
  latency    wall time of the full hybrid call

Read-only. Writes experiments/benchmarks/hard_features.json.
"""

import json
import re
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

IN = REPO / "experiments" / "benchmarks" / "hard_eval_set.json"
OUT = REPO / "experiments" / "benchmarks" / "hard_features.json"
TOP_K = 5

STOP = set("what how why is are the a an of in on for to and or not does do can which "
           "when where who explain describe define tell me about between with from that "
           "this it its their there they be been being has have had will would should "
           "hi was going through slides exam got bit confused could please help "
           "understand thanks lot".split())


def terms(t):
    return {w for w in re.findall(r"[a-z0-9]+", (t or "").lower())
            if len(w) > 3 and w not in STOP}


def main():
    items = json.loads(IN.read_text(encoding="utf-8"))
    embedder, chroma = Embedder(), ChromaStore()
    session = SessionFactory()

    rows = []
    try:
        for n, it in enumerate(items, 1):
            q, subject = it["question"], it["subject"]

            # Dense distances straight from Chroma - the magnitude RRF discards.
            vec = embedder.embed_query(q)
            try:
                dres = chroma.query(query_embedding=vec, n_results=TOP_K,
                                    where={"subject": subject})
            except Exception:
                dres = chroma.query(query_embedding=vec, n_results=TOP_K)
            dists = (dres.get("distances") or [[]])[0]

            t0 = time.perf_counter()
            res = run_hybrid_search(q, subject, session, embedder, chroma, top_k=TOP_K)
            latency_ms = (time.perf_counter() - t0) * 1000

            qt = terms(q)
            top_terms = terms(f"{res[0].get('summary','')} {res[0].get('concepts','')}") if res else set()
            all_terms = set()
            for r in res:
                all_terms |= terms(f"{r.get('summary','')} {r.get('concepts','')}")
            scores = [r["rrf_score"] for r in res] or [0.0]
            ids = [r["slide_id"] for r in res]

            rows.append({
                "id": it["id"],
                "category": it["category"],
                "subject": subject,
                "answerable": it["answerable"],
                "gold_slide_id": it.get("gold_slide_id"),
                "retrieved": ids,
                "hit_at_1": bool(it.get("gold_slide_id")) and ids[:1] == [it["gold_slide_id"]],
                "hit_at_3": bool(it.get("gold_slide_id")) and it["gold_slide_id"] in ids[:3],
                "hit_at_5": bool(it.get("gold_slide_id")) and it["gold_slide_id"] in ids,
                "rank_of_gold": (ids.index(it["gold_slide_id"]) + 1
                                 if it.get("gold_slide_id") in ids else None),
                # dense
                "dense_top1": dists[0] if dists else None,
                "dense_mean": statistics.mean(dists) if dists else None,
                "dense_min": min(dists) if dists else None,
                "dense_spread": (max(dists) - min(dists)) if len(dists) > 1 else 0.0,
                # rrf
                "rrf_top1": scores[0],
                "rrf_mean": statistics.mean(scores),
                "rrf_gap": scores[0] - scores[1] if len(scores) > 1 else 0.0,
                "rrf_ratio": (scores[1] / scores[0]) if len(scores) > 1 and scores[0] else 0.0,
                # agreement
                "top1_in_both": 1.0 if (res and res[0].get("dense_rank") is not None
                                        and res[0].get("sparse_rank") is not None) else 0.0,
                "n_in_both": float(sum(1 for r in res
                                       if r.get("dense_rank") is not None
                                       and r.get("sparse_rank") is not None)),
                # lexical
                "lex_top1": (len(qt & top_terms) / len(qt)) if qt else 0.0,
                "lex_topk": (len(qt & all_terms) / len(qt)) if qt else 0.0,
                "n_query_terms": float(len(qt)),
                "n_results": float(len(res)),
                "latency_ms": round(latency_ms, 2),
            })
            if n % 50 == 0:
                print(f"  {n}/{len(items)}", flush=True)
    finally:
        session.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\ncollected {len(rows)} rows -> {OUT}")

    # Retrieval quality on the answerable half, per phrasing.
    print(f"\n{'category':20s} {'n':>4s} {'R@1':>6s} {'R@3':>6s} {'R@5':>6s} {'MRR':>6s}")
    for cat in ("positive", "positive_noisy", "positive_keyword", "positive_verbose"):
        grp = [r for r in rows if r["category"] == cat]
        if not grp:
            continue
        n = len(grp)
        mrr = sum(1 / r["rank_of_gold"] if r["rank_of_gold"] else 0 for r in grp) / n
        print(f"{cat:20s} {n:>4d} "
              f"{sum(r['hit_at_1'] for r in grp)/n:>6.3f} "
              f"{sum(r['hit_at_3'] for r in grp)/n:>6.3f} "
              f"{sum(r['hit_at_5'] for r in grp)/n:>6.3f} {mrr:>6.3f}")

    # Separation by class - the Phase 3 input.
    print(f"\n{'class':24s} {'n':>4s} {'dense_top1':>11s} {'range':>18s} {'rrf_top1':>9s}")
    for cat in ("positive", "positive_noisy", "positive_keyword", "positive_verbose",
                "out_of_domain", "cross_subject_overlap", "in_subject_absent"):
        grp = [r for r in rows if r["category"] == cat and r["dense_top1"] is not None]
        if not grp:
            continue
        d = [r["dense_top1"] for r in grp]
        print(f"{cat:24s} {len(grp):>4d} {statistics.mean(d):>11.4f} "
              f"{min(d):>8.4f}-{max(d):<9.4f} "
              f"{statistics.mean([r['rrf_top1'] for r in grp]):>9.5f}")

    lat = sorted(r["latency_ms"] for r in rows)
    print(f"\nhybrid latency p50 {statistics.median(lat):.1f} ms  "
          f"p95 {lat[int(len(lat)*0.95)]:.1f} ms")


if __name__ == "__main__":
    main()
