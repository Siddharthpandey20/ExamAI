"""
Step 2 (analysis) — does the abstention threshold generalize?

P3 fitted 0.1768 with stratified k-fold CV. That protocol shuffles items
randomly, so every fold contains questions from every subject and every
phrasing style. It answers "does the threshold transfer to unseen questions of
a kind I have already seen", which is the easy version of the question.

Three harder tests here, in increasing order of severity:

1. NEW QUESTION TYPE. The 40 negation items did not exist when 0.1768 was
   fitted. Applying the old threshold to them is an honest out-of-sample test
   of a kind the CV could not perform.

2. LEAVE-ONE-SUBJECT-OUT. Fit on all subjects but one, test on the held-out
   subject. A threshold that only works when its own subject was in the
   training data is a per-corpus constant, not a decision rule. This is the
   test that matters for a system where a student uploads new material.

3. REFIT WITH NEGATION INCLUDED. Does the fitted value move once a realistic
   question type is present?

No threshold is promoted by this script, and 0.194 is not used anywhere.

Computes only. Reads experiments/benchmarks/expanded_features.json.
"""

import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

DATA = REPO / "experiments" / "benchmarks" / "expanded_features.json"
PRIOR_THRESHOLD = 0.1768          # fitted in P3, WITHOUT negation items
POSITIVE_CATS = ("positive", "positive_noisy", "positive_keyword",
                 "positive_verbose", "positive_negation")


def bal_acc(rows, t):
    pos = [r for r in rows if r["answerable"]]
    neg = [r for r in rows if not r["answerable"]]
    if not pos or not neg:
        return None
    rec = sum(1 for r in pos if r["dense_top1"] <= t) / len(pos)
    spec = sum(1 for r in neg if r["dense_top1"] > t) / len(neg)
    return (rec + spec) / 2


def fit(rows):
    best = (-1.0, None)
    for t in sorted({r["dense_top1"] for r in rows}):
        b = bal_acc(rows, t)
        if b is not None and b > best[0]:
            best = (b, t)
    return best[1], best[0]


def main():
    rows = [r for r in json.loads(DATA.read_text(encoding="utf-8"))
            if r["dense_top1"] is not None]
    old = [r for r in rows if r["category"] != "positive_negation"]
    neg_items = [r for r in rows if r["category"] == "positive_negation"]

    print(f"expanded set: {len(rows)} items "
          f"({len(neg_items)} negation items new since the threshold was fitted)\n")

    # ── 1. the old threshold against the new question type ───────────────
    print("=" * 74)
    print(f"TEST 1 - the P3 threshold ({PRIOR_THRESHOLD}) against a question")
    print("         type that did not exist when it was fitted")
    print("=" * 74)
    refused = [r for r in neg_items if r["dense_top1"] > PRIOR_THRESHOLD]
    print(f"negation items refused: {len(refused)}/{len(neg_items)} "
          f"= {len(refused)/len(neg_items):.1%}")
    print(f"  their mean distance   : "
          f"{statistics.mean([r['dense_top1'] for r in neg_items]):.4f}")
    print(f"  plain positives       : "
          f"{statistics.mean([r['dense_top1'] for r in rows if r['category']=='positive']):.4f}")
    print(f"  in_subject_absent     : "
          f"{statistics.mean([r['dense_top1'] for r in rows if r['category']=='in_subject_absent']):.4f}")

    print(f"\nfalse-abstention by class at T={PRIOR_THRESHOLD}:")
    for cat in POSITIVE_CATS:
        grp = [r for r in rows if r["category"] == cat]
        if not grp:
            continue
        ref = sum(1 for r in grp if r["dense_top1"] > PRIOR_THRESHOLD)
        flag = "  <-- NEW" if cat == "positive_negation" else ""
        print(f"  {cat:24s} {ref:>3d}/{len(grp):<3d} {ref/len(grp):>7.1%}{flag}")

    print(f"\nbalanced accuracy on the set the threshold was fitted for : "
          f"{bal_acc(old, PRIOR_THRESHOLD):.3f}")
    print(f"balanced accuracy once negation items are included        : "
          f"{bal_acc(rows, PRIOR_THRESHOLD):.3f}")

    # ── 2. leave-one-subject-out ─────────────────────────────────────────
    print("\n" + "=" * 74)
    print("TEST 2 - leave-one-subject-out: fit without a subject, test on it")
    print("=" * 74)
    subjects = sorted({r["subject"] for r in rows})
    print(f"{'held-out subject':22s} {'n':>4s} {'T fitted elsewhere':>19s} "
          f"{'bal.acc held-out':>17s} {'T refitted here':>16s} {'gap':>7s}")
    gaps, ts = [], []
    for s in subjects:
        test = [r for r in rows if r["subject"] == s]
        train = [r for r in rows if r["subject"] != s]
        if not test or not train:
            continue
        has_pos = any(r["answerable"] for r in test)
        has_neg = any(not r["answerable"] for r in test)
        if not (has_pos and has_neg):
            print(f"{s:22s} {len(test):>4d} {'(single-class, skipped)':>19s}")
            continue
        t_train, _ = fit(train)
        held = bal_acc(test, t_train)
        t_self, best_self = fit(test)
        gaps.append(best_self - held)
        ts.append(t_train)
        print(f"{s:22s} {len(test):>4d} {t_train:>19.4f} {held:>17.3f} "
              f"{t_self:>16.4f} {best_self - held:>+7.3f}")

    if gaps:
        print(f"\nmean held-out balanced accuracy gap vs a threshold refitted on")
        print(f"the held-out subject itself: {statistics.mean(gaps):+.3f}")
        print(f"threshold fitted on other subjects: "
              f"{statistics.mean(ts):.4f} +/- {statistics.pstdev(ts):.4f}")
        print("\nA small gap and a stable threshold mean the value is a property")
        print("of the embedding space, not of one subject's vocabulary.")

    # ── 3. refit including negation ──────────────────────────────────────
    print("\n" + "=" * 74)
    print("TEST 3 - refit with the new question type included")
    print("=" * 74)
    t_old, b_old = fit(old)
    t_new, b_new = fit(rows)
    print(f"fitted without negation items : T={t_old:.4f}  bal.acc {b_old:.3f}")
    print(f"fitted with negation items    : T={t_new:.4f}  bal.acc {b_new:.3f}")
    print(f"threshold moved {t_new - t_old:+.4f}, best achievable "
          f"accuracy moved {b_new - b_old:+.3f}")

    # What the negation items cost at the refitted value.
    ref = sum(1 for r in neg_items if r["dense_top1"] > t_new)
    print(f"\neven at the refitted threshold, {ref}/{len(neg_items)} "
          f"({ref/len(neg_items):.1%}) negation items are still refused")

    # ── distribution overlap, the underlying cause ───────────────────────
    print("\n" + "=" * 74)
    print("Why: where positive_negation sits relative to the negatives")
    print("=" * 74)
    negd = sorted(r["dense_top1"] for r in neg_items)
    absent = sorted(r["dense_top1"] for r in rows
                    if r["category"] == "in_subject_absent")
    print(f"positive_negation  p25 {negd[len(negd)//4]:.4f}  "
          f"median {statistics.median(negd):.4f}  p75 {negd[3*len(negd)//4]:.4f}")
    print(f"in_subject_absent  p25 {absent[len(absent)//4]:.4f}  "
          f"median {statistics.median(absent):.4f}  p75 {absent[3*len(absent)//4]:.4f}")
    overlap = sum(1 for d in negd if d >= absent[0]) / len(negd)
    print(f"\n{overlap:.0%} of negation items sit at or beyond the CLOSEST "
          f"unanswerable question ({absent[0]:.4f}).")
    print("Answerable-but-negated questions look, to the embedding, much like")
    print("questions about material that is not there.")


if __name__ == "__main__":
    main()
