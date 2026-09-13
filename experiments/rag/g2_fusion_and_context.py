"""
G2 — fusion weighting, candidate-pool size, context depth, adjacency, and
whether any of it should depend on query type.

Covers the retrieval-side workstreams in one controlled sweep, because they all
share the same expensive part (embedding every query once) and differ only in
how the candidate lists are combined and cut.

Questions, each with a baseline and a stated hypothesis:

  FUSION       RRF with K=60 is the current design and was never compared with
               anything. RRF deliberately discards score magnitude; for a
               2-list fusion a weighted sum of normalised scores keeps it.
               Hypothesis: weighting helps, because Q5 showed dense and sparse
               disagree on exactly the queries that matter.

  RRF_K        K=60 is the value from the original paper, tuned for TREC runs
               with hundreds of candidates. With fetch_n = 3*top_k = 15-36,
               K=60 flattens almost everything: 1/(60+1) vs 1/(60+15) is a
               1.25x spread across the whole list. Hypothesis: a smaller K
               sharpens the ranking.

  POOL SIZE    fetch_n is 3*top_k. Larger pools cost only BM25 scoring.

  CONTEXT K    production sends 6 slides. More context is more evidence but
               more tokens and more distractors.

  ADJACENCY    slides are pages of a deck, so page N-1/N+1 are often the same
               topic continued. Cheap to add, no extra retrieval.

  ROUTING      does the best configuration differ between short keyword queries
               and full questions? Only worth routing if it does.

Retrieval-only and deterministic: no LLM, no generation. Measures Recall@k,
MRR and nDCG, plus the token cost of each context option. Answer quality is
measured separately in G1/G3 - a retrieval gain that does not survive
generation is not a gain.

READ-ONLY.
"""

import json
import math
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from indexing.database import SessionFactory          # noqa: E402
from indexing.db_chroma import ChromaStore            # noqa: E402
from indexing.embedder import Embedder                # noqa: E402
from indexing.models import Slide, Document           # noqa: E402
from engine.tools import (_get_bm25_index, _tokenize,  # noqa: E402
                          _parse_chroma_id, is_substantive)

EVAL = REPO / "eval" / "eval_set.json"
HARD = REPO / "experiments" / "benchmarks" / "hard_eval_set.json"
INDEP = REPO / "experiments" / "benchmarks" / "independent_eval.json"
OUT = REPO / "experiments" / "benchmarks" / "g2_fusion_context.json"


def ndcg(ranked_ids, gold_set, k):
    dcg = sum(1 / math.log2(i + 2) for i, sid in enumerate(ranked_ids[:k])
              if sid in gold_set)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(gold_set), k)))
    return dcg / ideal if ideal else 0.0


def retrieve_lists(query, subject, session, embedder, chroma, fetch_n):
    """Dense and sparse candidate lists with their raw scores."""
    vec = embedder.embed_query(query)
    try:
        raw = chroma.query(query_embedding=vec, n_results=fetch_n,
                           where={"subject": subject})
    except Exception:
        raw = chroma.query(query_embedding=vec, n_results=fetch_n)
    dense = []
    if raw and raw.get("ids") and raw["ids"][0]:
        dists = (raw.get("distances") or [[]])[0] or []
        for i, cid in enumerate(raw["ids"][0]):
            d, p = _parse_chroma_id(cid)
            dense.append({"key": f"{d}_{p}", "rank": i + 1,
                          "score": 1.0 - (dists[i] if i < len(dists) else 1.0)})

    sparse = []
    bm25, corpus = _get_bm25_index(session, subject)
    if bm25 is not None:
        toks = _tokenize(query)
        if toks:
            sc = bm25.get_scores(toks)
            order = sorted((i for i in range(len(sc)) if sc[i] > 0),
                           key=lambda i: -sc[i])[:fetch_n]
            mx = max((sc[i] for i in order), default=1.0) or 1.0
            for r, i in enumerate(order, 1):
                sl = corpus[i]
                sparse.append({"key": f"{sl.doc_id}_{sl.page_number}",
                               "rank": r, "score": sc[i] / mx})
    return dense, sparse


def fuse(dense, sparse, method, rrf_k=60, w_dense=0.5):
    d = {x["key"]: x for x in dense}
    s = {x["key"]: x for x in sparse}
    keys = set(d) | set(s)
    out = {}
    for k in keys:
        if method == "rrf":
            v = 0.0
            if k in d:
                v += 1.0 / (rrf_k + d[k]["rank"])
            if k in s:
                v += 1.0 / (rrf_k + s[k]["rank"])
        elif method == "weighted":
            v = (w_dense * d[k]["score"] if k in d else 0.0) + \
                ((1 - w_dense) * s[k]["score"] if k in s else 0.0)
        elif method == "dense_only":
            v = d[k]["score"] if k in d else -1.0
        elif method == "sparse_only":
            v = s[k]["score"] if k in s else -1.0
        else:
            raise ValueError(method)
        out[k] = v
    return sorted(out.items(), key=lambda kv: (-kv[1], kv[0]))


def resolve(fused_keys, slides_by_key, top_k):
    ids = []
    for key, _ in fused_keys:
        sl = slides_by_key.get(key)
        if sl is None or not is_substantive(sl):
            continue
        ids.append(sl.id)
        if len(ids) >= top_k:
            break
    return ids


def main():
    session = SessionFactory()
    embedder, chroma = Embedder(), ChromaStore()
    slides_by_key, slide_by_id = {}, {}
    for sl in session.query(Slide).all():
        slides_by_key[f"{sl.doc_id}_{sl.page_number}"] = sl
        slide_by_id[sl.id] = sl

    # ── items: generated eval + independent PYQ, kept separate ───────────
    gen = [{"q": q["question"], "subject": q["subject"],
            "gold": {q["gold_slide_id"]}, "set": "generated",
            "short": len(q["question"].split()) <= 6}
           for q in json.loads(EVAL.read_text(encoding="utf-8"))]
    kw = [{"q": it["question"], "subject": it["subject"],
           "gold": {it["gold_slide_id"]}, "set": "keyword-style",
           "short": True}
          for it in json.loads(HARD.read_text(encoding="utf-8"))
          if it["category"] == "positive_keyword"]
    ind = [{"q": it["question"], "subject": it["subject"],
            "gold": set(it.get("gold_slide_ids") or [it["gold_slide_id"]]),
            "set": "independent PYQ",
            "short": len(it["question"].split()) <= 6}
           for it in json.loads(INDEP.read_text(encoding="utf-8"))
           if it["answerable"]]
    items = gen + kw + ind
    print(f"items: {len(gen)} generated, {len(kw)} keyword-style, "
          f"{len(ind)} independent PYQ\n")

    # Cache candidate lists per (query, subject, fetch_n) - the expensive part.
    cache = {}

    def lists_for(it, fetch_n):
        key = (it["q"], it["subject"], fetch_n)
        if key not in cache:
            cache[key] = retrieve_lists(it["q"], it["subject"], session,
                                        embedder, chroma, fetch_n)
        return cache[key]

    def evaluate(cfg, subset=None):
        pool = subset if subset is not None else items
        r1 = r3 = r5 = 0
        rr, nd = [], []
        for it in pool:
            dense, sparse = lists_for(it, cfg["fetch_n"])
            fused = fuse(dense, sparse, cfg["method"],
                         cfg.get("rrf_k", 60), cfg.get("w_dense", 0.5))
            ids = resolve(fused, slides_by_key, cfg.get("top_k", 5))
            g = it["gold"]
            r1 += bool(set(ids[:1]) & g)
            r3 += bool(set(ids[:3]) & g)
            r5 += bool(set(ids[:5]) & g)
            hit = next((i for i, s in enumerate(ids) if s in g), None)
            rr.append(1 / (hit + 1) if hit is not None else 0.0)
            nd.append(ndcg(ids, g, 5))
        n = len(pool)
        return {"r1": r1/n, "r3": r3/n, "r5": r5/n,
                "mrr": statistics.mean(rr), "ndcg5": statistics.mean(nd), "n": n}

    results = {}
    base = {"method": "rrf", "rrf_k": 60, "fetch_n": 15, "top_k": 5}

    # ── 1. fusion method ─────────────────────────────────────────────────
    print("=" * 92)
    print("1. FUSION METHOD  (fetch_n=15, top_k=5)")
    print("=" * 92)
    print(f"{'config':38s} {'R@1':>6s} {'R@3':>6s} {'R@5':>6s} {'MRR':>6s} {'nDCG@5':>7s}")
    cfgs = [("RRF K=60 (production)", {**base}),
            ("dense only", {**base, "method": "dense_only"}),
            ("sparse only", {**base, "method": "sparse_only"})]
    for w in (0.3, 0.5, 0.7, 0.8, 0.9):
        cfgs.append((f"weighted dense={w}", {**base, "method": "weighted", "w_dense": w}))
    for name, cfg in cfgs:
        m = evaluate(cfg)
        results[name] = m
        print(f"{name:38s} {m['r1']:>6.3f} {m['r3']:>6.3f} {m['r5']:>6.3f} "
              f"{m['mrr']:>6.3f} {m['ndcg5']:>7.3f}")

    # ── 2. RRF K ─────────────────────────────────────────────────────────
    print("\n" + "=" * 92)
    print("2. RRF K  (K=60 is the paper's value, tuned for much longer lists)")
    print("=" * 92)
    print(f"{'config':38s} {'R@1':>6s} {'R@3':>6s} {'R@5':>6s} {'MRR':>6s} {'nDCG@5':>7s}")
    for k in (1, 3, 5, 10, 20, 60, 120):
        m = evaluate({**base, "rrf_k": k})
        results[f"RRF K={k}"] = m
        star = "   <- production" if k == 60 else ""
        print(f"{f'RRF K={k}':38s} {m['r1']:>6.3f} {m['r3']:>6.3f} {m['r5']:>6.3f} "
              f"{m['mrr']:>6.3f} {m['ndcg5']:>7.3f}{star}")

    # ── 3. candidate pool size ───────────────────────────────────────────
    print("\n" + "=" * 92)
    print("3. CANDIDATE POOL  (fetch_n; production is 3 x top_k = 15)")
    print("=" * 92)
    print(f"{'config':38s} {'R@1':>6s} {'R@3':>6s} {'R@5':>6s} {'MRR':>6s} {'nDCG@5':>7s}")
    for f in (5, 10, 15, 30, 60, 120):
        m = evaluate({**base, "fetch_n": f})
        results[f"fetch_n={f}"] = m
        star = "   <- production" if f == 15 else ""
        print(f"{f'fetch_n={f}':38s} {m['r1']:>6.3f} {m['r3']:>6.3f} {m['r5']:>6.3f} "
              f"{m['mrr']:>6.3f} {m['ndcg5']:>7.3f}{star}")

    # ── 4. does the best config depend on query type? ────────────────────
    print("\n" + "=" * 92)
    print("4. ROUTING - is the best configuration different for short queries?")
    print("=" * 92)
    subsets = {"all": items,
               "short (<=6 words)": [i for i in items if i["short"]],
               "long (>6 words)": [i for i in items if not i["short"]],
               "independent PYQ": [i for i in items if i["set"] == "independent PYQ"]}
    trials = {"RRF K=60 (production)": {**base},
              "RRF K=5": {**base, "rrf_k": 5},
              "dense only": {**base, "method": "dense_only"},
              "weighted 0.7": {**base, "method": "weighted", "w_dense": 0.7},
              "fetch_n=60": {**base, "fetch_n": 60}}
    print(f"{'subset':22s} {'n':>4s} " + " ".join(f"{t[:14]:>15s}" for t in trials))
    for sname, sub in subsets.items():
        if not sub:
            continue
        cells = []
        for tname, cfg in trials.items():
            m = evaluate(cfg, sub)
            cells.append(f"{m['r1']:.3f}/{m['mrr']:.3f}")
        print(f"{sname:22s} {len(sub):>4d} " + " ".join(f"{c:>15s}" for c in cells))
    print("  (cells are R@1/MRR)")

    # ── 5. context depth and adjacency ───────────────────────────────────
    print("\n" + "=" * 92)
    print("5. CONTEXT - how much evidence reaches the LLM, and what it costs")
    print("=" * 92)
    print(f"{'option':38s} {'gold in ctx':>12s} {'slides':>7s} {'~chars':>8s} {'~tokens':>8s}")

    def ctx_cost(ids):
        tot = 0
        for sid in ids:
            sl = slide_by_id.get(sid)
            if sl:
                tot += len(sl.summary or "") + len(sl.concepts or "") + 120
        return tot

    for label, k, adjacent in [("top 3", 3, False), ("top 5", 5, False),
                               ("top 6 (production)", 6, False),
                               ("top 8", 8, False), ("top 10", 10, False),
                               ("top 5 + adjacent pages", 5, True),
                               ("top 6 + adjacent pages", 6, True)]:
        hit = 0
        chars, nslides = [], []
        for it in items:
            dense, sparse = lists_for(it, 30)
            fused = fuse(dense, sparse, "rrf", 60)
            ids = resolve(fused, slides_by_key, k)
            if adjacent:
                extra = []
                for sid in list(ids):
                    sl = slide_by_id.get(sid)
                    if not sl:
                        continue
                    for p in (sl.page_number - 1, sl.page_number + 1):
                        nb = slides_by_key.get(f"{sl.doc_id}_{p}")
                        if nb and is_substantive(nb) and nb.id not in ids:
                            extra.append(nb.id)
                ids = ids + [e for e in dict.fromkeys(extra)]
            hit += bool(set(ids) & it["gold"])
            chars.append(ctx_cost(ids))
            nslides.append(len(ids))
        n = len(items)
        c = statistics.mean(chars)
        print(f"{label:38s} {hit/n:>12.3f} {statistics.mean(nslides):>7.1f} "
              f"{c:>8.0f} {c/4:>8.0f}")

    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    session.close()
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
