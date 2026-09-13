"""
G4 — is the query-length routing signal real?

G2's sweep produced one positive result among many negatives:

    subset               RRF K=60      dense only
    short (<=6 words)   0.633/0.709   0.694/0.715
    long  (>6 words)    0.692/0.733   0.600/0.666
    independent PYQ     0.706/0.744   0.471/0.575

The crossover is the interesting part - not that one retriever is better, but
that the ORDER REVERSES with query length. A reversal is harder to produce by
chance than a difference, and it has a mechanism behind it: Q5 showed that a
one-token query gives BM25 nothing to discriminate with, since `tcp` matches
477 slides equally, while a long question gives it many terms to match.

But 0.694 vs 0.633 on 49 items is three questions. This applies the paired test
the difference deserves before it is written up as a finding, plus a bootstrap
on the interaction effect itself (the thing that would justify routing).

READ-ONLY, deterministic, no LLM.
"""

import json
import math
import random
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from indexing.database import SessionFactory          # noqa: E402
from indexing.db_chroma import ChromaStore            # noqa: E402
from indexing.embedder import Embedder                # noqa: E402
from indexing.models import Slide                     # noqa: E402
from engine.tools import (_get_bm25_index, _tokenize,  # noqa: E402
                          _parse_chroma_id, is_substantive)

EVAL = REPO / "eval" / "eval_set.json"
HARD = REPO / "experiments" / "benchmarks" / "hard_eval_set.json"
INDEP = REPO / "experiments" / "benchmarks" / "independent_eval.json"
OUT = REPO / "experiments" / "benchmarks" / "g4_routing.json"
N_BOOT = 2000


def mcnemar(a_hits, b_hits):
    """Exact two-sided McNemar on paired binary outcomes."""
    b = sum(1 for x, y in zip(a_hits, b_hits) if x and not y)
    c = sum(1 for x, y in zip(a_hits, b_hits) if y and not x)
    n = b + c
    if n == 0:
        return b, c, 1.0
    k = min(b, c)
    p = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n) * 2
    return b, c, min(1.0, p)


def main():
    session = SessionFactory()
    embedder, chroma = Embedder(), ChromaStore()
    by_key = {f"{s.doc_id}_{s.page_number}": s for s in session.query(Slide).all()}

    items = []
    for q in json.loads(EVAL.read_text(encoding="utf-8")):
        items.append({"q": q["question"], "subject": q["subject"],
                      "gold": {q["gold_slide_id"]}, "set": "generated"})
    for it in json.loads(HARD.read_text(encoding="utf-8")):
        if it["category"] == "positive_keyword":
            items.append({"q": it["question"], "subject": it["subject"],
                          "gold": {it["gold_slide_id"]}, "set": "keyword"})
    for it in json.loads(INDEP.read_text(encoding="utf-8")):
        if it["answerable"]:
            items.append({"q": it["question"], "subject": it["subject"],
                          "gold": set(it.get("gold_slide_ids")
                                      or [it["gold_slide_id"]]),
                          "set": "independent"})
    for it in items:
        it["nwords"] = len(it["q"].split())

    def rank(it, method):
        vec = embedder.embed_query(it["q"])
        try:
            raw = chroma.query(query_embedding=vec, n_results=15,
                               where={"subject": it["subject"]})
        except Exception:
            raw = chroma.query(query_embedding=vec, n_results=15)
        dense = {}
        if raw and raw.get("ids") and raw["ids"][0]:
            for i, cid in enumerate(raw["ids"][0]):
                d, p = _parse_chroma_id(cid)
                dense[f"{d}_{p}"] = i + 1
        sparse = {}
        bm25, corpus = _get_bm25_index(session, it["subject"])
        if bm25 is not None:
            toks = _tokenize(it["q"])
            if toks:
                sc = bm25.get_scores(toks)
                order = sorted((i for i in range(len(sc)) if sc[i] > 0),
                               key=lambda i: -sc[i])[:15]
                for r, i in enumerate(order, 1):
                    sl = corpus[i]
                    sparse[f"{sl.doc_id}_{sl.page_number}"] = r
        keys = set(dense) | set(sparse)
        scored = {}
        for k in keys:
            if method == "rrf":
                v = (1/(60+dense[k]) if k in dense else 0) + \
                    (1/(60+sparse[k]) if k in sparse else 0)
            elif method == "dense":
                v = -dense.get(k, 9999)
            else:
                v = -sparse.get(k, 9999)
            scored[k] = v
        ids = []
        for k, _ in sorted(scored.items(), key=lambda kv: (-kv[1], kv[0])):
            sl = by_key.get(k)
            if sl and is_substantive(sl):
                ids.append(sl.id)
            if len(ids) >= 5:
                break
        return ids

    print(f"{len(items)} items; computing both rankings per item ...")
    for n, it in enumerate(items, 1):
        it["rrf"] = rank(it, "rrf")
        it["dense"] = rank(it, "dense")
        it["rrf_hit"] = bool(set(it["rrf"][:1]) & it["gold"])
        it["dense_hit"] = bool(set(it["dense"][:1]) & it["gold"])
        if n % 40 == 0:
            print(f"  {n}/{len(items)}", flush=True)
    session.close()

    print("\n" + "=" * 78)
    print("PAIRED TEST: dense-only vs RRF, by query length")
    print("=" * 78)
    print(f"{'subset':24s} {'n':>4s} {'RRF R@1':>8s} {'dense R@1':>10s} "
          f"{'b':>3s} {'c':>3s} {'p':>8s}  verdict")
    subsets = {
        "short (<=3 words)": [i for i in items if i["nwords"] <= 3],
        "short (<=6 words)": [i for i in items if i["nwords"] <= 6],
        "medium (7-12)": [i for i in items if 7 <= i["nwords"] <= 12],
        "long (>12 words)": [i for i in items if i["nwords"] > 12],
        "independent PYQ": [i for i in items if i["set"] == "independent"],
        "all": items,
    }
    results = {}
    for name, sub in subsets.items():
        if len(sub) < 5:
            continue
        r = [i["rrf_hit"] for i in sub]
        d = [i["dense_hit"] for i in sub]
        b, c, p = mcnemar(r, d)
        verdict = ("significant" if p < 0.05 else
                   "trend" if p < 0.15 else "noise")
        results[name] = {"n": len(sub), "rrf": sum(r)/len(r),
                         "dense": sum(d)/len(d), "b": b, "c": c, "p": p}
        print(f"{name:24s} {len(sub):>4d} {sum(r)/len(r):>8.3f} "
              f"{sum(d)/len(d):>10.3f} {b:>3d} {c:>3d} {p:>8.4f}  {verdict}")
    print("  b = RRF won, c = dense won")

    # ── the interaction: does the gap actually reverse with length? ──────
    print("\n" + "=" * 78)
    print("THE INTERACTION - routing is only justified if the gap REVERSES")
    print("=" * 78)
    short = [i for i in items if i["nwords"] <= 6]
    long_ = [i for i in items if i["nwords"] > 6]

    def gap(pool):
        return (sum(i["dense_hit"] for i in pool) / len(pool)
                - sum(i["rrf_hit"] for i in pool) / len(pool))

    obs = gap(short) - gap(long_)
    print(f"  dense-minus-RRF on short queries : {gap(short):+.3f}")
    print(f"  dense-minus-RRF on long queries  : {gap(long_):+.3f}")
    print(f"  interaction (short - long)       : {obs:+.3f}")

    rng = random.Random(3)
    diffs = []
    for _ in range(N_BOOT):
        s = [short[rng.randrange(len(short))] for _ in short]
        l = [long_[rng.randrange(len(long_))] for _ in long_]
        diffs.append(gap(s) - gap(l))
    diffs.sort()
    lo, hi = diffs[int(0.025*len(diffs))], diffs[int(0.975*len(diffs))]
    p_pos = sum(1 for d in diffs if d > 0) / len(diffs)
    print(f"  bootstrap 95% CI                 : [{lo:+.3f}, {hi:+.3f}]")
    print(f"  P(interaction > 0)               : {p_pos:.1%}")
    print("  " + ("ESTABLISHED - the reversal is real, routing has a basis"
                  if lo > 0 else
                  "NOT ESTABLISHED - the reversal could be chance"))

    # ── what routing would actually buy ──────────────────────────────────
    print("\n" + "=" * 78)
    print("CEILING: best achievable by perfect length-based routing")
    print("=" * 78)
    for cut in (3, 6, 8):
        routed = sum((i["dense_hit"] if i["nwords"] <= cut else i["rrf_hit"])
                     for i in items)
        allrrf = sum(i["rrf_hit"] for i in items)
        print(f"  route dense when <={cut} words: R@1 {routed/len(items):.3f} "
              f"vs {allrrf/len(items):.3f} all-RRF  "
              f"({(routed-allrrf)/len(items):+.3f}, {routed-allrrf:+d} questions)")

    Path(OUT).write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
