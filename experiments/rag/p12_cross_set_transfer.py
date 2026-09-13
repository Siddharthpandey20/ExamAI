"""
Does a threshold fitted on one evaluation set work on a different one?

This is the sharpest form of the generalization question. p9 showed the
threshold transfers across SUBJECTS, but every subject there came from the same
evaluation lineage. Set B is built from real PYQ exam questions with lexically
assigned gold labels and shares nothing with that lineage.

So: fit ONLY on the original set, apply to the independent set, never refit.
The gap between "applied" and "refitted here" is the cost of not having the
target data - which is the situation production is always in.

Also reported: the same test in reverse, and what happens to the transform
benefit, which p11 found does not replicate.

Computes only.
"""

import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

DATA = REPO / "experiments" / "benchmarks" / "p11_negation_safe.json"
EXPANDED = REPO / "experiments" / "benchmarks" / "expanded_features.json"


def metrics(rows, t):
    pos = [r for r in rows if r["answerable"]]
    neg = [r for r in rows if not r["answerable"]]
    rec = sum(1 for r in pos if r["dense_top1"] <= t) / len(pos)
    spec = sum(1 for r in neg if r["dense_top1"] > t) / len(neg)
    return {"bal": (rec + spec) / 2, "rec": rec, "spec": spec,
            "false_abstain": sum(1 for r in pos if r["dense_top1"] > t),
            "false_accept": sum(1 for r in neg if r["dense_top1"] <= t),
            "n_pos": len(pos), "n_neg": len(neg)}


def fit(rows):
    best = (-1.0, None)
    for t in sorted({r["dense_top1"] for r in rows}):
        b = metrics(rows, t)["bal"]
        if b > best[0]:
            best = (b, t)
    return best[1], best[0]


def main():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    A = d["expanded"]["baseline"]      # original lineage, 290 items
    B = d["independent"]["baseline"]   # real PYQ, 68 items

    print("=" * 76)
    print("Threshold transfer between two independently built evaluation sets")
    print("=" * 76)
    print("SET A  original lineage (eval_set.json + my degradations), n=%d" % len(A))
    print("SET B  real PYQ exam questions, lexical gold labels,       n=%d" % len(B))

    tA, bA = fit(A)
    tB, bB = fit(B)

    print(f"\nfitted on A : T={tA:.4f}  bal.acc {bA:.3f}")
    print(f"fitted on B : T={tB:.4f}  bal.acc {bB:.3f}")
    print(f"the two independently fitted thresholds differ by {abs(tA-tB):.4f}")

    print("\n" + "-" * 76)
    print("APPLYING A's THRESHOLD TO B (no refitting - the production situation)")
    print("-" * 76)
    m = metrics(B, tA)
    print(f"  bal.acc {m['bal']:.3f}   recall {m['rec']:.3f}   specificity {m['spec']:.3f}")
    print(f"  false abstentions {m['false_abstain']}/{m['n_pos']}, "
          f"false acceptances {m['false_accept']}/{m['n_neg']}")
    print(f"  cost of not having B to fit on: {bB - m['bal']:+.3f} balanced accuracy")

    print("\n" + "-" * 76)
    print("AND IN REVERSE - B's threshold applied to A")
    print("-" * 76)
    m2 = metrics(A, tB)
    print(f"  bal.acc {m2['bal']:.3f}   recall {m2['rec']:.3f}   "
          f"specificity {m2['spec']:.3f}")
    print(f"  cost: {bA - m2['bal']:+.3f} balanced accuracy")

    # What the distributions look like side by side.
    print("\n" + "-" * 76)
    print("Distance distributions, the reason transfer works or does not")
    print("-" * 76)
    print(f"{'set':28s} {'n':>4s} {'mean':>8s} {'p25':>8s} {'median':>8s} {'p75':>8s}")
    for label, rows, want in (("A answerable", A, True), ("A unanswerable", A, False),
                              ("B answerable", B, True), ("B unanswerable", B, False)):
        v = sorted(r["dense_top1"] for r in rows if r["answerable"] == want)
        print(f"{label:28s} {len(v):>4d} {statistics.mean(v):>8.4f} "
              f"{v[len(v)//4]:>8.4f} {statistics.median(v):>8.4f} "
              f"{v[3*len(v)//4]:>8.4f}")

    # The transform, on both sets, at a threshold that was NOT fitted to it.
    print("\n" + "=" * 76)
    print("The transform benefit, re-checked with no refitting")
    print("=" * 76)
    print(f"{'set':10s} {'variant':14s} {'bal.acc @ A-fitted T':>21s} {'R@1':>7s}")
    for setname, rows_by_variant in (("A", d["expanded"]), ("B", d["independent"])):
        for variant in ("baseline", "content_only", "content_safe"):
            rows = rows_by_variant[variant]
            m = metrics(rows, tA)
            pos = [r for r in rows if r["answerable"]]
            print(f"{setname:10s} {variant:14s} {m['bal']:>21.3f} "
                  f"{sum(r['hit_at_1'] for r in pos)/len(pos):>7.3f}")

    # The question-type effect, which is the one that did not generalize.
    print("\n" + "=" * 76)
    print("For contrast: what DID break generalization was question type")
    print("=" * 76)
    exp = [r for r in json.loads(EXPANDED.read_text(encoding="utf-8"))
           if r["dense_top1"] is not None]
    print(f"{'question type':26s} {'n':>4s} {'refused at A-fitted T':>22s}")
    for cat in ("positive", "positive_noisy", "positive_verbose",
                "positive_keyword", "positive_negation"):
        grp = [r for r in exp if r["category"] == cat]
        if not grp:
            continue
        ref = sum(1 for r in grp if r["dense_top1"] > tA)
        print(f"{cat:26s} {len(grp):>4d} {ref}/{len(grp)} = {ref/len(grp):>13.1%}")

    print("\nThe threshold moves very little between corpora, subjects and even")
    print("evaluation lineages. It moves a great deal between QUESTION TYPES.")
    print("Generalization here is about what users ask, not about the data.")


if __name__ == "__main__":
    main()
