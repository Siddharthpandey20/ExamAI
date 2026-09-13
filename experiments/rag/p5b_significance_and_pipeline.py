"""
Phase 5b — are the Phase 5 gains real, and do they fix the thing that blocked
promotion?

Two questions, in order of importance:

1. SIGNIFICANCE. A +0.050 R@1 on 40 questions is two questions. Paired
   exact McNemar over the per-question win/loss pattern says whether that is
   distinguishable from noise. Most of Phase 5 will not survive this, and
   reporting it as a win without the test would be the easy mistake.

2. END-TO-END. Phase 3 blocked promotion on one number: 25% of keyword queries
   falsely refused. Recall going up is only interesting if it moves THAT.
   So the abstention analysis is re-run, with the same cross-validated
   protocol, on each variant's distances.

Reads experiments/benchmarks/p5_rewriting_rows.json. Computes only.
"""

import json
import random
import statistics
import sys
from math import comb
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

RAW = REPO / "experiments" / "benchmarks" / "p5_rewriting_rows.json"
POSITIVE_CATS = ("positive", "positive_noisy", "positive_keyword", "positive_verbose")
NEGATIVE_CATS = ("in_subject_absent", "cross_subject_overlap", "out_of_domain")
FOLDS, SEEDS = 5, 5


def mcnemar_exact(base, variant, field="hit_at_1"):
    """Two-sided exact McNemar on paired binary outcomes.

    b = questions the baseline got right and the variant lost
    c = questions the variant gained
    Under H0 each discordant pair is a fair coin.
    """
    by_id = {r["id"]: r for r in variant}
    b = c = 0
    for r in base:
        v = by_id.get(r["id"])
        if v is None:
            continue
        if r[field] and not v[field]:
            b += 1
        elif v[field] and not r[field]:
            c += 1
    n = b + c
    if n == 0:
        return b, c, 1.0
    k = min(b, c)
    p = sum(comb(n, i) for i in range(0, k + 1)) / (2 ** n) * 2
    return b, c, min(1.0, p)


def cv_threshold(rows):
    """Stratified k-fold CV of a dense_top1 threshold - the P3 protocol."""
    vals = [(r["dense_top1"], r["answerable"], r["category"]) for r in rows
            if r["dense_top1"] is not None]
    labs = [a for _, a, _ in vals]
    preds, truth, cats, ths = [], [], [], []
    for seed in range(SEEDS):
        rng = random.Random(seed)
        pos = [i for i, l in enumerate(labs) if l]
        neg = [i for i, l in enumerate(labs) if not l]
        rng.shuffle(pos); rng.shuffle(neg)
        folds = [[] for _ in range(FOLDS)]
        for i, idx in enumerate(pos): folds[i % FOLDS].append(idx)
        for i, idx in enumerate(neg): folds[i % FOLDS].append(idx)
        for f in range(FOLDS):
            test = folds[f]
            train = [i for g in range(FOLDS) if g != f for i in folds[g]]
            best = (-1.0, None)
            for t in sorted({vals[i][0] for i in train}):
                tp = sum(1 for i in train if vals[i][0] <= t and labs[i])
                np_ = sum(1 for i in train if labs[i])
                tn = sum(1 for i in train if vals[i][0] > t and not labs[i])
                nn = len(train) - np_
                bal = ((tp / np_ if np_ else 0) + (tn / nn if nn else 0)) / 2
                if bal > best[0]:
                    best = (bal, t)
            t = best[1]
            ths.append(t)
            for i in test:
                preds.append(vals[i][0] <= t)
                truth.append(labs[i])
                cats.append(vals[i][2])

    tp = sum(1 for p, y in zip(preds, truth) if p and y)
    fp = sum(1 for p, y in zip(preds, truth) if p and not y)
    tn = sum(1 for p, y in zip(preds, truth) if not p and not y)
    fn = sum(1 for p, y in zip(preds, truth) if not p and y)
    rec = tp / (tp + fn) if tp + fn else 0
    spec = tn / (tn + fp) if tn + fp else 0

    per_cat = {}
    for c in POSITIVE_CATS + NEGATIVE_CATS:
        idx = [i for i, cc in enumerate(cats) if cc == c]
        if not idx:
            continue
        if c in POSITIVE_CATS:      # rate of wrongly refusing
            per_cat[c] = sum(1 for i in idx if not preds[i]) / len(idx)
        else:                       # rate of wrongly answering
            per_cat[c] = sum(1 for i in idx if preds[i]) / len(idx)
    return {"bal": (rec + spec) / 2, "rec": rec, "spec": spec,
            "t": statistics.mean(ths), "per_cat": per_cat}


def main():
    data = json.loads(RAW.read_text(encoding="utf-8"))
    base = data["baseline"]
    variants = [k for k in data if k != "baseline"]

    # ── 1. significance ──────────────────────────────────────────────────
    print("Paired exact McNemar on R@1, each variant vs baseline")
    print("b = lost by rewriting, c = gained, p = two-sided exact\n")
    hdr = f"{'variant':16s} {'scope':20s} {'b':>3s} {'c':>3s} {'net':>5s} {'p':>8s}  verdict"
    print(hdr)
    print("-" * len(hdr))
    for v in variants:
        for scope in ("ALL_POSITIVE",) + POSITIVE_CATS:
            if scope == "ALL_POSITIVE":
                bb = [r for r in base if r["category"] in POSITIVE_CATS]
                vv = [r for r in data[v] if r["category"] in POSITIVE_CATS]
            else:
                bb = [r for r in base if r["category"] == scope]
                vv = [r for r in data[v] if r["category"] == scope]
            b, c, p = mcnemar_exact(bb, vv)
            verdict = "significant" if p < 0.05 else ("trend" if p < 0.15 else "noise")
            print(f"{v:16s} {scope:20s} {b:>3d} {c:>3d} {c-b:>+5d} {p:>8.4f}  {verdict}")
        print()

    # ── 2. end-to-end abstention ─────────────────────────────────────────
    print("\nCross-validated abstention on each variant's distances")
    print("(same protocol as P3: threshold fitted on training folds only)\n")
    cols = ("positive", "positive_noisy", "positive_keyword", "positive_verbose",
            "in_subject_absent")
    hdr = (f"{'variant':16s} {'bal.acc':>8s} {'rec':>6s} {'spec':>6s} {'T':>7s} | "
           + " ".join(f"{c.replace('positive','pos')[:9]:>10s}" for c in cols))
    print(hdr)
    print("-" * len(hdr))
    print(f"{'':16s} {'':8s} {'':6s} {'':6s} {'':7s} | "
          + " ".join(f"{'refused' if c in POSITIVE_CATS else 'answered':>10s}"
                     for c in cols))
    results = {}
    for v in ["baseline"] + variants:
        r = cv_threshold(data[v])
        results[v] = r
        line = (f"{v:16s} {r['bal']:>8.3f} {r['rec']:>6.3f} {r['spec']:>6.3f} "
                f"{r['t']:>7.4f} | ")
        line += " ".join(f"{r['per_cat'].get(c, 0):>9.1%} " for c in cols)
        print(line)

    b = results["baseline"]
    print("\nchange vs baseline (negative = better for refused/answered):")
    for v in variants:
        r = results[v]
        d = " ".join(f"{r['per_cat'].get(c,0)-b['per_cat'].get(c,0):>+9.1%} "
                     for c in cols)
        print(f"{v:16s} {r['bal']-b['bal']:>+8.3f} {'':6s} {'':6s} {'':7s} | {d}")

    # ── 3. the promotion question ────────────────────────────────────────
    print("\n" + "=" * 78)
    print("Promotion-relevant summary")
    print("=" * 78)
    kw_base = b["per_cat"].get("positive_keyword", 0)
    print(f"baseline keyword false-abstention: {kw_base:.1%}  (the P3 blocker)")
    best = min(variants, key=lambda v: results[v]["per_cat"].get("positive_keyword", 1))
    kw_best = results[best]["per_cat"].get("positive_keyword", 0)
    print(f"best variant '{best}':               {kw_best:.1%}  "
          f"({kw_best - kw_base:+.1%})")
    print(f"  balanced accuracy {results[best]['bal']:.3f} "
          f"(baseline {b['bal']:.3f}, {results[best]['bal']-b['bal']:+.3f})")
    print(f"  in_subject_absent wrongly answered "
          f"{results[best]['per_cat'].get('in_subject_absent',0):.1%} "
          f"(baseline {b['per_cat'].get('in_subject_absent',0):.1%})")


if __name__ == "__main__":
    main()
