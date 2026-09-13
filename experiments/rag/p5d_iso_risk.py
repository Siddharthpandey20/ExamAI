"""
Phase 5d — comparing rewrites at MATCHED RISK, not at a matched threshold.

P5c produced an apparent contradiction worth resolving rather than papering over:

  - the cross-validated pipeline said content_only cuts keyword false-abstention
    26.5% -> 13.5%
  - but at a FIXED threshold (0.165, 0.1768, 0.18) content_only refuses exactly
    as many keyword queries as the baseline

Both are true. The CV threshold moved up (0.1768 -> 0.1922) because content_only
separated the classes better, and the gain came from that headroom, not from
pulling keyword queries closer to their gold slide. content_only does NOT fix
keyword retrieval - keyword R@1 is 0.575 -> 0.600, nothing.

So the fair comparison holds the RISK constant, not the threshold: pick each
variant's threshold so that it wrongly answers the same fraction of unanswerable
questions, then ask what it costs in refusals. That is the comparison a
production decision actually faces, since the false-acceptance rate is the thing
being budgeted.

Computes only.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

RAW = REPO / "experiments" / "benchmarks" / "p5_rewriting_rows.json"
BUDGETS = (0.0, 0.01, 0.02, 0.05, 0.10)


def main():
    data = json.loads(RAW.read_text(encoding="utf-8"))
    base = {r["id"]: r for r in data["baseline"]}
    ids = [i for i, r in base.items() if r["dense_top1"] is not None]

    print("Iso-risk comparison: each variant's threshold is chosen so it answers")
    print("at most the stated fraction of UNANSWERABLE questions. The columns are")
    print("what that costs.\n")

    for budget in BUDGETS:
        print(f"=== false-acceptance budget <= {budget:.0%} "
              f"of 90 unanswerable questions ===")
        print(f"{'variant':16s} {'T':>8s} {'FA':>8s} {'answered':>9s} "
              f"{'kw refused':>11s} {'all refused':>12s} {'R@1 kw':>8s} {'R@1 all':>8s}")
        for v in ["baseline"] + [k for k in data if k != "baseline"]:
            var = {r["id"]: r for r in data[v]}
            neg = [i for i in ids if not var[i]["answerable"]]
            pos = [i for i in ids if var[i]["answerable"]]
            kw = [i for i in ids if var[i]["category"] == "positive_keyword"]

            # Largest threshold whose false-acceptance stays within budget.
            best_t = None
            for t in sorted({var[i]["dense_top1"] for i in ids}):
                fa = sum(1 for i in neg if var[i]["dense_top1"] <= t) / len(neg)
                if fa <= budget:
                    best_t = t
                else:
                    break
            if best_t is None:
                print(f"{v:16s} {'-':>8s}")
                continue

            fa = sum(1 for i in neg if var[i]["dense_top1"] <= best_t)
            ans = sum(1 for i in pos if var[i]["dense_top1"] <= best_t)
            kwref = sum(1 for i in kw if var[i]["dense_top1"] > best_t)
            allref = len(pos) - ans
            # R@1 counted only over questions the system agreed to answer -
            # abstaining on a question it would have got wrong is not a failure.
            kw_ans = [i for i in kw if var[i]["dense_top1"] <= best_t]
            all_ans = [i for i in pos if var[i]["dense_top1"] <= best_t]
            r1kw = (sum(1 for i in kw_ans if var[i]["hit_at_1"]) / len(kw_ans)
                    if kw_ans else 0)
            r1all = (sum(1 for i in all_ans if var[i]["hit_at_1"]) / len(all_ans)
                     if all_ans else 0)
            print(f"{v:16s} {best_t:>8.4f} {fa:>4d}/{len(neg):<3d} "
                  f"{ans:>4d}/{len(pos):<4d} {kwref/len(kw):>10.1%} "
                  f"{allref/len(pos):>11.1%} {r1kw:>8.3f} {r1all:>8.3f}")
        print()

    # The single sentence a promotion decision needs.
    print("=" * 78)
    v = "content_only"
    var = {r["id"]: r for r in data[v]}
    for label, d in (("baseline", base), (v, var)):
        neg = [i for i in ids if not d[i]["answerable"]]
        kw = [i for i in ids if d[i]["category"] == "positive_keyword"]
        t = None
        for c in sorted({d[i]["dense_top1"] for i in ids}):
            if sum(1 for i in neg if d[i]["dense_top1"] <= c) == 0:
                t = c
            else:
                break
        kwref = sum(1 for i in kw if d[i]["dense_top1"] > t) / len(kw)
        pos = [i for i in ids if d[i]["answerable"]]
        allref = sum(1 for i in pos if d[i]["dense_top1"] > t) / len(pos)
        print(f"{label:14s} at zero false-acceptance: T={t:.4f}, "
              f"refuses {kwref:.0%} of keyword queries, {allref:.0%} overall")


if __name__ == "__main__":
    main()
