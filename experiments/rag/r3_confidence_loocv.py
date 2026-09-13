"""
R3b — honest evaluation of the confidence signals.

r3_retrieval_confidence.py chose each threshold on the same 40 questions it
then scored. That is in-sample fitting: with 9 signals and n=40, beating the
majority baseline by a few questions is expected by chance.

This re-evaluates with leave-one-out cross-validation — the threshold is fitted
on 39 questions and tested on the held-out one — which is what the number has
to be for a production decision to rest on it.

Reads only the benchmark JSON produced by the previous script. No model, no
database, no network.

Usage:  python experiments/rag/r3_confidence_loocv.py
"""

import json
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "experiments" / "benchmarks" / "r3_confidence.json"

SIGNALS = ["top1_rrf", "mean_rrf", "lexical_overlap", "n_in_both_lists",
           "top1_in_both_lists", "gap_1_2", "gap_ratio", "score_spread"]


def fit_threshold(values, labels):
    """Threshold and direction maximising accuracy on the given data."""
    best = (0.0, None, True)
    for higher in (True, False):
        for t in sorted(set(values)):
            pred = [(v >= t) if higher else (v <= t) for v in values]
            acc = sum(int(p == bool(l)) for p, l in zip(pred, labels)) / len(labels)
            if acc > best[0]:
                best = (acc, t, higher)
    return best


def loocv(values, labels):
    """Leave-one-out accuracy: fit on n-1, predict the held-out point."""
    correct = 0
    for i in range(len(values)):
        tr_v = values[:i] + values[i + 1:]
        tr_l = labels[:i] + labels[i + 1:]
        _, t, higher = fit_threshold(tr_v, tr_l)
        if t is None:
            continue
        pred = (values[i] >= t) if higher else (values[i] <= t)
        correct += int(pred == bool(labels[i]))
    return correct / len(values)


def main():
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    n = len(rows)
    print(f"R3b — leave-one-out validation, n={n}\n")

    for outcome in ("hit_at_1", "hit_at_5"):
        labels = [bool(r[outcome]) for r in rows]
        pos = sum(labels)
        baseline = max(pos, n - pos) / n
        print(f"=== {outcome}  ({pos} correct / {n - pos} wrong) ===")
        print(f"    majority baseline = {baseline:.3f}  "
              f"(always predict '{'correct' if pos >= n - pos else 'wrong'}')")
        print(f"{'signal':22s} {'in-sample':>10s} {'LOOCV':>8s} {'vs baseline':>12s}")

        results = []
        for sig in SIGNALS:
            vals = [r[sig] for r in rows]
            if len(set(vals)) < 2:
                continue
            in_sample, _, _ = fit_threshold(vals, labels)
            cv = loocv(vals, labels)
            results.append((sig, in_sample, cv, cv - baseline))

        for sig, ins, cv, delta in sorted(results, key=lambda x: -x[2]):
            flag = "" if delta > 0 else "  (no better than guessing)"
            print(f"{sig:22s} {ins:>10.3f} {cv:>8.3f} {delta:>+12.3f}{flag}")

        best = max(results, key=lambda x: x[2])
        print(f"\n    best honest signal: {best[0]} at LOOCV {best[2]:.3f} "
              f"({best[3]:+.3f} vs baseline = "
              f"{round(best[3] * n)} questions out of {n})\n")


if __name__ == "__main__":
    main()
