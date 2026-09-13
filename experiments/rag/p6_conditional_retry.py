"""
Phase 6 — is it better to rewrite every query, or only the ones that look bad?

P5 established that content_only improves separation, but it costs -0.025 R@1 on
plain well-formed questions: rewriting a query that was already fine can only
lose information. A conditional policy should keep the gain and skip the cost -
run normal retrieval, and only pay for a second pass when the first one looks
weak.

Policies simulated (both passes are already recorded per item, so this is exact,
not modelled):

  always_baseline   what production does today
  always_rewrite    P5's content_only on every query
  retry_if_far      if baseline distance > trigger, redo with the rewrite and
                    USE the rewrite's result
  retry_take_min    same trigger, but keep whichever pass scored closer

retry_take_min looks obviously better and probably is not: a negative gets two
independent chances to look close to something, so min() drags the negatives
down too. Measuring that is the point.

Every policy is compared at MATCHED false-acceptance risk (the P5d method),
because a policy that answers more questions by accepting more risk has not
improved anything.

Computes only. Reads experiments/benchmarks/p5_rewriting_rows.json.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

RAW = REPO / "experiments" / "benchmarks" / "p5_rewriting_rows.json"
TRIGGERS = (0.13, 0.15, 0.16, 0.17, 0.18)
BUDGETS = (0.0, 0.02, 0.05)


def build(base, rw, policy, trigger):
    """Return per-item (distance, hit_at_1, answerable, category, retried)."""
    out = {}
    for i, b in base.items():
        r = rw[i]
        if policy == "always_baseline":
            chosen, retried = b, False
        elif policy == "always_rewrite":
            chosen, retried = r, True
        elif b["dense_top1"] <= trigger:
            chosen, retried = b, False          # first pass was confident
        elif policy == "retry_if_far":
            chosen, retried = r, True
        elif policy == "retry_take_min":
            chosen = r if r["dense_top1"] < b["dense_top1"] else b
            retried = True
        out[i] = {"d": chosen["dense_top1"], "hit": chosen["hit_at_1"],
                  "ans": b["answerable"], "cat": b["category"], "retried": retried}
    return out


def at_budget(rows, budget):
    neg = [v for v in rows.values() if not v["ans"]]
    pos = [v for v in rows.values() if v["ans"]]
    kw = [v for v in rows.values() if v["cat"] == "positive_keyword"]
    t = None
    for c in sorted({v["d"] for v in rows.values()}):
        if sum(1 for v in neg if v["d"] <= c) / len(neg) <= budget:
            t = c
        else:
            break
    if t is None:
        return None
    answered = [v for v in pos if v["d"] <= t]
    kw_ans = [v for v in kw if v["d"] <= t]
    return {
        "t": t,
        "fa": sum(1 for v in neg if v["d"] <= t) / len(neg),
        "answered": len(answered) / len(pos),
        "kw_refused": sum(1 for v in kw if v["d"] > t) / len(kw),
        "r1_answered": (sum(1 for v in answered if v["hit"]) / len(answered)
                        if answered else 0),
        "r1_kw_answered": (sum(1 for v in kw_ans if v["hit"]) / len(kw_ans)
                           if kw_ans else 0),
        # end-to-end: right answer delivered, over ALL answerable questions.
        # Abstaining counts as a miss here, which is the user's experience.
        "useful": sum(1 for v in answered if v["hit"]) / len(pos),
        "retry_rate": sum(1 for v in rows.values() if v["retried"]) / len(rows),
    }


def main():
    data = json.loads(RAW.read_text(encoding="utf-8"))
    base = {r["id"]: r for r in data["baseline"] if r["dense_top1"] is not None}
    rw = {r["id"]: r for r in data["content_only"]}

    print("Policies at matched false-acceptance risk.\n")
    print("'useful' = fraction of ALL answerable questions that got a correct")
    print("top-1 slide AND were not refused. This is the end-to-end number;")
    print("everything else is diagnostic.\n")

    for budget in BUDGETS:
        print(f"=== false-acceptance budget <= {budget:.0%} ===")
        print(f"{'policy':22s} {'T':>7s} {'useful':>7s} {'answ':>6s} "
              f"{'kw ref':>7s} {'R@1|ans':>8s} {'retry%':>7s}")
        rows = []
        for policy in ("always_baseline", "always_rewrite"):
            r = at_budget(build(base, rw, policy, None), budget)
            rows.append((policy, r))
        for trig in TRIGGERS:
            for policy in ("retry_if_far", "retry_take_min"):
                r = at_budget(build(base, rw, policy, trig), budget)
                rows.append((f"{policy}@{trig}", r))
        for name, r in rows:
            if r is None:
                continue
            print(f"{name:22s} {r['t']:>7.4f} {r['useful']:>7.3f} "
                  f"{r['answered']:>6.1%} {r['kw_refused']:>7.1%} "
                  f"{r['r1_answered']:>8.3f} {r['retry_rate']:>7.0%}")
        best = max((r for _, r in rows if r), key=lambda r: r["useful"])
        best_name = [n for n, r in rows if r is best][0]
        print(f"  -> best end-to-end: {best_name} (useful {best['useful']:.3f})\n")

    # Does take-min actually damage the negatives, as predicted?
    print("=" * 70)
    print("Diagnostic: what min() does to each class (trigger 0.15)\n")
    bmap = build(base, rw, "always_baseline", None)
    mmap = build(base, rw, "retry_take_min", 0.15)
    print(f"{'class':24s} {'baseline':>10s} {'take_min':>10s} {'shift':>8s}")
    for cat in ("positive", "positive_noisy", "positive_keyword",
                "positive_verbose", "in_subject_absent", "cross_subject_overlap",
                "out_of_domain"):
        ids = [i for i in base if bmap[i]["cat"] == cat]
        if not ids:
            continue
        b = sum(bmap[i]["d"] for i in ids) / len(ids)
        m = sum(mmap[i]["d"] for i in ids) / len(ids)
        print(f"{cat:24s} {b:>10.4f} {m:>10.4f} {m - b:>+8.4f}")


if __name__ == "__main__":
    main()
