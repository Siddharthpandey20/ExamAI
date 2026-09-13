"""
Phase 3b — the operating curve for dense-distance abstention.

p3 found a best-balanced threshold of 0.1768, but "best balanced" is only one
operating point and it refuses 25% of keyword-style queries. A production
decision needs the whole trade-off, because the two errors are not equally bad:

  false abstention  the system refuses a question it could have answered
  false acceptance  the system answers from evidence it does not have

For a study tool, a false abstention is visible and recoverable (the student
rephrases); a false acceptance is a confident wrong answer the student may not
catch. But refusing a quarter of keyword queries would make the feature feel
broken, so the curve matters more than any single number.

Computes only. Reads experiments/benchmarks/hard_features.json.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

DATA = REPO / "experiments" / "benchmarks" / "hard_features.json"
KEY = "dense_top1"


def main():
    rows = [r for r in json.loads(DATA.read_text(encoding="utf-8"))
            if r[KEY] is not None]
    pos = [r for r in rows if r["answerable"]]
    neg = [r for r in rows if not r["answerable"]]
    print(f"Phase 3b — operating curve for '{KEY}', "
          f"{len(pos)} answerable / {len(neg)} not\n")
    print("rule: answer when distance <= T, otherwise abstain\n")

    hdr = (f"{'T':>7s} {'answered':>9s} {'false_abst':>11s} {'false_acc':>10s} "
           f"{'prec':>6s} {'rec':>6s} {'spec':>6s} {'bal.acc':>8s} "
           f"{'kw_refused':>11s} {'absent_ok':>10s}")
    print(hdr)
    print("-" * len(hdr))

    kw = [r for r in rows if r["category"] == "positive_keyword"]
    absent = [r for r in rows if r["category"] == "in_subject_absent"]

    best = None
    for t in [round(x * 0.005, 4) for x in range(30, 46)]:
        tp = sum(1 for r in pos if r[KEY] <= t)
        fn = len(pos) - tp
        fp = sum(1 for r in neg if r[KEY] <= t)
        tn = len(neg) - fp
        prec = tp / (tp + fp) if tp + fp else 0
        rec = tp / len(pos)
        spec = tn / len(neg)
        bal = (rec + spec) / 2
        kw_ref = sum(1 for r in kw if r[KEY] > t) / len(kw) if kw else 0
        abs_ok = sum(1 for r in absent if r[KEY] > t) / len(absent) if absent else 0
        mark = ""
        if best is None or bal > best[1]:
            best = (t, bal)
        print(f"{t:>7.4f} {tp + fp:>9d} {fn:>11d} {fp:>10d} {prec:>6.3f} {rec:>6.3f} "
              f"{spec:>6.3f} {bal:>8.3f} {kw_ref:>11.1%} {abs_ok:>10.1%}{mark}")

    print(f"\nbest balanced accuracy at T={best[0]:.4f} ({best[1]:.3f})")

    # Recall-protective operating point: how permissive must T be to refuse
    # at most 5% of answerable questions, and what does that cost?
    for target in (0.02, 0.05, 0.10):
        chosen = None
        for t in [round(x * 0.001, 4) for x in range(150, 260)]:
            fn_rate = sum(1 for r in pos if r[KEY] > t) / len(pos)
            if fn_rate <= target:
                chosen = t
                break
        if chosen is None:
            continue
        fp = sum(1 for r in neg if r[KEY] <= chosen)
        kw_ref = sum(1 for r in kw if r[KEY] > chosen) / len(kw)
        print(f"\nto refuse at most {target:.0%} of answerable questions: T >= {chosen:.4f}")
        print(f"  then {fp}/{len(neg)} unanswerable questions ({fp/len(neg):.1%}) "
              f"are still answered")
        print(f"  and {kw_ref:.1%} of keyword-style queries are refused")


if __name__ == "__main__":
    main()
