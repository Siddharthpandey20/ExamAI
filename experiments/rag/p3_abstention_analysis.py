"""
Phase 3/4 — can dense distance (alone or combined) support reliable abstention
once the negatives are HARD?

The previous session found near-perfect separation, but its negatives were
out-of-domain questions that sit far from the corpus by construction. This set
adds in_subject_absent negatives — topics that plausibly belong to the subject
and are verified (lexically) not to occur in it.

Evaluated with stratified 5-fold cross-validation repeated over several seeds:
the threshold is fitted on the training folds only and scored on the held-out
fold, so no number here is in-sample.

Reads experiments/benchmarks/hard_features.json. Computes only.
"""

import json
import random
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

DATA = REPO / "experiments" / "benchmarks" / "hard_features.json"
OUT = REPO / "experiments" / "benchmarks" / "p3_abstention.json"

SINGLE = ["dense_top1", "dense_mean", "dense_min", "rrf_top1", "rrf_mean",
          "rrf_gap", "lex_top1", "lex_topk", "n_in_both", "top1_in_both"]
FOLDS, SEEDS = 5, 5


def metrics(pred, truth):
    """pred/truth are 'answerable' booleans."""
    tp = sum(1 for p, t in zip(pred, truth) if p and t)
    fp = sum(1 for p, t in zip(pred, truth) if p and not t)
    tn = sum(1 for p, t in zip(pred, truth) if not p and not t)
    fn = sum(1 for p, t in zip(pred, truth) if not p and t)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    spec = tn / (tn + fp) if tn + fp else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"accuracy": (tp + tn) / len(truth), "precision": prec, "recall": rec,
            "specificity": spec, "f1": f1, "balanced_acc": (rec + spec) / 2,
            "false_abstain": fn, "false_accept": fp, "tp": tp, "tn": tn}


def fit(values, labels, objective="balanced_acc"):
    """Best threshold on the training data, by the chosen objective."""
    best = (-1.0, None, True)
    for higher in (True, False):
        for t in sorted(set(values)):
            pred = [(v >= t) if higher else (v <= t) for v in values]
            score = metrics(pred, labels)[objective]
            if score > best[0]:
                best = (score, t, higher)
    return best[1], best[2]


def cv_single(rows, key, objective="balanced_acc"):
    """Stratified k-fold CV, repeated over seeds. Returns held-out metrics."""
    vals = [r[key] for r in rows]
    labs = [r["answerable"] for r in rows]
    if any(v is None for v in vals) or len(set(vals)) < 2:
        return None

    preds_all, truth_all, thresholds = [], [], []
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
            t, higher = fit([vals[i] for i in train], [labs[i] for i in train], objective)
            if t is None:
                continue
            thresholds.append(t)
            for i in test:
                preds_all.append((vals[i] >= t) if higher else (vals[i] <= t))
                truth_all.append(labs[i])

    m = metrics(preds_all, truth_all)
    m["threshold_mean"] = round(statistics.mean(thresholds), 4)
    m["threshold_stdev"] = round(statistics.pstdev(thresholds), 4)
    return m


def logistic_cv(rows, keys):
    """Interpretable multi-signal baseline, same CV protocol."""
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import make_pipeline
    except ImportError:
        return None

    X = [[r[k] for k in keys] for r in rows]
    y = [1 if r["answerable"] else 0 for r in rows]
    preds, truth = [], []
    for seed in range(SEEDS):
        rng = random.Random(seed)
        pos = [i for i, l in enumerate(y) if l]
        neg = [i for i, l in enumerate(y) if not l]
        rng.shuffle(pos); rng.shuffle(neg)
        folds = [[] for _ in range(FOLDS)]
        for i, idx in enumerate(pos): folds[i % FOLDS].append(idx)
        for i, idx in enumerate(neg): folds[i % FOLDS].append(idx)
        for f in range(FOLDS):
            test = folds[f]
            train = [i for g in range(FOLDS) if g != f for i in folds[g]]
            clf = make_pipeline(StandardScaler(),
                                LogisticRegression(max_iter=2000, class_weight="balanced"))
            clf.fit([X[i] for i in train], [y[i] for i in train])
            for i, p in zip(test, clf.predict([X[i] for i in test])):
                preds.append(bool(p)); truth.append(bool(y[i]))
    return metrics(preds, truth)


def main():
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    rows = [r for r in rows if r["dense_top1"] is not None]
    n = len(rows)
    n_pos = sum(1 for r in rows if r["answerable"])
    baseline = max(n_pos, n - n_pos) / n
    print(f"Phase 3/4 — abstention with HARD negatives, n={n} "
          f"({n_pos} answerable / {n - n_pos} not)")
    print(f"always-answer baseline: accuracy {baseline:.3f}, "
          f"balanced accuracy 0.500\n")

    print(f"{'signal':16s} {'bal.acc':>8s} {'acc':>6s} {'prec':>6s} {'rec':>6s} "
          f"{'spec':>6s} {'F1':>6s} {'thresh':>8s} {'±':>6s}")
    results = {}
    for key in SINGLE:
        m = cv_single(rows, key)
        if not m:
            continue
        results[key] = m
        print(f"{key:16s} {m['balanced_acc']:>8.3f} {m['accuracy']:>6.3f} "
              f"{m['precision']:>6.3f} {m['recall']:>6.3f} {m['specificity']:>6.3f} "
              f"{m['f1']:>6.3f} {m['threshold_mean']:>8.4f} {m['threshold_stdev']:>6.4f}")

    best_key = max(results, key=lambda k: results[k]["balanced_acc"])
    best = results[best_key]
    print(f"\nbest single signal: {best_key}  balanced accuracy {best['balanced_acc']:.3f}")
    print(f"  held-out errors: {best['false_abstain']} false abstentions "
          f"(refused an answerable question), "
          f"{best['false_accept']} false acceptances (answered an unanswerable one)")

    # Multi-signal
    combos = {
        "dense+lex": ["dense_top1", "lex_topk"],
        "dense+rrf+lex": ["dense_top1", "rrf_top1", "lex_topk"],
        "all": ["dense_top1", "dense_mean", "dense_spread", "rrf_top1", "rrf_gap",
                "lex_top1", "lex_topk", "n_in_both"],
    }
    print(f"\n{'combination':16s} {'bal.acc':>8s} {'acc':>6s} {'prec':>6s} {'rec':>6s} {'spec':>6s}")
    for name, keys in combos.items():
        m = logistic_cv(rows, keys)
        if m is None:
            print("  (scikit-learn unavailable - single-signal results only)")
            break
        results[f"logreg_{name}"] = m
        print(f"{name:16s} {m['balanced_acc']:>8.3f} {m['accuracy']:>6.3f} "
              f"{m['precision']:>6.3f} {m['recall']:>6.3f} {m['specificity']:>6.3f}")

    # Per-category false acceptance at the best single threshold.
    t = best["threshold_mean"]
    print(f"\nfalse-acceptance by negative class, using {best_key} <= {t:.4f}:")
    print(f"{'class':24s} {'n':>4s} {'answered':>9s} {'rate':>7s}")
    for cat in ("out_of_domain", "cross_subject_overlap", "in_subject_absent"):
        grp = [r for r in rows if r["category"] == cat]
        if not grp:
            continue
        answered = sum(1 for r in grp if r[best_key] <= t)
        print(f"{cat:24s} {len(grp):>4d} {answered:>9d} {answered/len(grp):>7.1%}")
    print(f"\nfalse-abstention by positive class, same threshold:")
    print(f"{'class':24s} {'n':>4s} {'refused':>9s} {'rate':>7s}")
    for cat in ("positive", "positive_noisy", "positive_keyword", "positive_verbose"):
        grp = [r for r in rows if r["category"] == cat]
        if not grp:
            continue
        refused = sum(1 for r in grp if not (r[best_key] <= t))
        print(f"{cat:24s} {len(grp):>4d} {refused:>9d} {refused/len(grp):>7.1%}")

    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
