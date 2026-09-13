"""
Phase 5c — is content_only's abstention improvement real, or 5 lucky questions?

P5b showed keyword false-abstention falling 26.5% -> 13.5% and balanced accuracy
rising 0.941 -> 0.963. Those are averages over 5 seeds x 5 folds, but they rest
on only 250 distinct items, and the R@1 gains behind them were NOT individually
significant. So the improvement needs its own test rather than inheriting
credibility from the recall table.

Paired bootstrap over ITEMS (not over folds): resample the 250 items with
replacement, recompute each variant's best balanced accuracy on the same
resample, and take the difference. Pairing matters - both variants are scored on
the identical resample, so the shared difficulty of the drawn items cancels.

The reported interval is of the DIFFERENCE. If it straddles zero, the
improvement is not established, regardless of how good the point estimate looks.

Computes only.
"""

import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

RAW = REPO / "experiments" / "benchmarks" / "p5_rewriting_rows.json"
N_BOOT = 2000
POSITIVE_CATS = ("positive", "positive_noisy", "positive_keyword", "positive_verbose")


def best_bal(pairs):
    """Best achievable balanced accuracy over a threshold on (dist, answerable)."""
    pos = [d for d, a in pairs if a]
    neg = [d for d, a in pairs if not a]
    if not pos or not neg:
        return None
    best = -1.0
    for t in sorted({d for d, _ in pairs}):
        rec = sum(1 for d in pos if d <= t) / len(pos)
        spec = sum(1 for d in neg if d > t) / len(neg)
        best = max(best, (rec + spec) / 2)
    return best


def main():
    data = json.loads(RAW.read_text(encoding="utf-8"))
    base = {r["id"]: r for r in data["baseline"]}
    ids = [i for i, r in base.items() if r["dense_top1"] is not None]
    rng = random.Random(7)

    print(f"Paired bootstrap over {len(ids)} items, {N_BOOT} resamples\n")
    print(f"{'variant':16s} {'d_bal.acc':>9s} {'95% CI':>20s} {'P(better)':>10s}  verdict")
    print("-" * 72)

    for v in [k for k in data if k != "baseline"]:
        var = {r["id"]: r for r in data[v]}
        diffs = []
        for _ in range(N_BOOT):
            draw = [ids[rng.randrange(len(ids))] for _ in range(len(ids))]
            bp = [(base[i]["dense_top1"], base[i]["answerable"]) for i in draw]
            vp = [(var[i]["dense_top1"], var[i]["answerable"]) for i in draw
                  if var[i]["dense_top1"] is not None]
            b, w = best_bal(bp), best_bal(vp)
            if b is not None and w is not None:
                diffs.append(w - b)
        diffs.sort()
        lo = diffs[int(0.025 * len(diffs))]
        hi = diffs[int(0.975 * len(diffs))]
        point = best_bal([(var[i]["dense_top1"], var[i]["answerable"]) for i in ids]) \
            - best_bal([(base[i]["dense_top1"], base[i]["answerable"]) for i in ids])
        p_better = sum(1 for d in diffs if d > 0) / len(diffs)
        verdict = ("established" if lo > 0 else
                   "likely" if p_better >= 0.95 else
                   "not established")
        print(f"{v:16s} {point:>+9.4f} {f'[{lo:+.4f}, {hi:+.4f}]':>20s} "
              f"{p_better:>10.1%}  {verdict}")

    # The blocker, tested on its own: keyword false-abstention at a fixed
    # policy threshold. Uses the P3 operating band rather than a refitted
    # threshold, because that is what production would actually ship.
    print("\n\nKeyword false-abstention at fixed policy thresholds")
    print("(no refitting - the threshold is chosen by policy, then applied)\n")
    kw_ids = [i for i in ids if base[i]["category"] == "positive_keyword"]
    print(f"{'variant':16s}" + "".join(f"{f'T={t}':>14s}"
                                       for t in (0.165, 0.1768, 0.18, 0.19)))
    for v in ["baseline"] + [k for k in data if k != "baseline"]:
        var = {r["id"]: r for r in data[v]}
        line = f"{v:16s}"
        for t in (0.165, 0.1768, 0.18, 0.19):
            ref = sum(1 for i in kw_ids if var[i]["dense_top1"] > t)
            line += f"{ref}/{len(kw_ids)} = {ref/len(kw_ids):>4.0%}".rjust(14)
        print(line)

    print("\nand the matching false-acceptance on unanswerable questions\n")
    neg_ids = [i for i in ids if not base[i]["answerable"]]
    print(f"{'variant':16s}" + "".join(f"{f'T={t}':>14s}"
                                       for t in (0.165, 0.1768, 0.18, 0.19)))
    for v in ["baseline"] + [k for k in data if k != "baseline"]:
        var = {r["id"]: r for r in data[v]}
        line = f"{v:16s}"
        for t in (0.165, 0.1768, 0.18, 0.19):
            acc = sum(1 for i in neg_ids if var[i]["dense_top1"] <= t)
            line += f"{acc}/{len(neg_ids)} = {acc/len(neg_ids):>4.0%}".rjust(14)
        print(line)


if __name__ == "__main__":
    main()
