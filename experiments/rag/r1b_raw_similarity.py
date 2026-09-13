"""
R1b — does the raw similarity RRF discards separate in-corpus from
out-of-corpus questions?

R1 showed every out-of-domain question ("how long should I roast a chicken")
returns five confident-looking slides, with top-1 RRF scores indistinguishable
from real questions. The mechanism is structural: RRF scores a rank,
1/(60+rank), so the top hit scores the same whether the match is perfect or
absurd. The similarity magnitude is thrown away.

Chroma returns that magnitude as `distances` and run_hybrid_search ignores it.

Hypothesis: top-1 cosine distance separates answerable from unanswerable
questions where RRF score cannot.

Success criterion: leave-one-out accuracy meaningfully above the majority
baseline on the combined positive + negative set.

Read-only: queries Chroma directly, writes only to experiments/benchmarks/.

Usage:  python experiments/rag/r1b_raw_similarity.py
"""

import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from indexing.db_chroma import ChromaStore     # noqa: E402
from indexing.embedder import Embedder         # noqa: E402

OUT = REPO / "experiments" / "benchmarks" / "r1b_raw_similarity.json"
POSITIVES = REPO / "eval" / "eval_set.json"
NEGATIVES = REPO / "experiments" / "benchmarks" / "r1_negative_probes.json"


def top_distance(embedder, chroma, question, subject, n=5):
    """Raw cosine distances Chroma returns, which RRF discards."""
    vec = embedder.embed_query(question)
    try:
        res = chroma.query(query_embedding=vec, n_results=n, where={"subject": subject})
    except Exception:
        res = chroma.query(query_embedding=vec, n_results=n)
    dists = (res.get("distances") or [[]])[0]
    return list(dists)


def fit_threshold(values, labels):
    best = (0.0, None, True)
    for higher in (True, False):
        for t in sorted(set(values)):
            pred = [(v >= t) if higher else (v <= t) for v in values]
            acc = sum(int(p == bool(l)) for p, l in zip(pred, labels)) / len(labels)
            if acc > best[0]:
                best = (acc, t, higher)
    return best


def loocv(values, labels):
    correct = 0
    for i in range(len(values)):
        _, t, higher = fit_threshold(values[:i] + values[i + 1:],
                                     labels[:i] + labels[i + 1:])
        if t is None:
            continue
        pred = (values[i] >= t) if higher else (values[i] <= t)
        correct += int(pred == bool(labels[i]))
    return correct / len(values)


def main():
    pos = json.loads(POSITIVES.read_text(encoding="utf-8"))
    neg = json.loads(NEGATIVES.read_text(encoding="utf-8"))
    embedder, chroma = Embedder(), ChromaStore()

    rows = []
    for qa in pos:
        d = top_distance(embedder, chroma, qa["question"], qa["subject"])
        if d:
            rows.append({"id": qa["id"], "answerable": True, "category": "positive",
                         "top1_distance": d[0], "mean_distance": statistics.mean(d)})
    for p in neg:
        d = top_distance(embedder, chroma, p["question"], p["subject"])
        if d:
            rows.append({"id": p["id"], "answerable": False, "category": p["category"],
                         "top1_distance": d[0], "mean_distance": statistics.mean(d)})

    n = len(rows)
    n_pos = sum(1 for r in rows if r["answerable"])
    baseline = max(n_pos, n - n_pos) / n
    print(f"R1b — raw cosine distance, {n} questions "
          f"({n_pos} answerable / {n - n_pos} not)\n")

    print(f"{'group':16s} {'n':>4s} {'mean top1_dist':>15s} {'min':>8s} {'max':>8s}")
    for cat in ("positive", "out_of_domain", "cross_subject"):
        grp = [r["top1_distance"] for r in rows if r["category"] == cat]
        if grp:
            print(f"{cat:16s} {len(grp):>4d} {statistics.mean(grp):>15.4f} "
                  f"{min(grp):>8.4f} {max(grp):>8.4f}")

    print(f"\nmajority baseline = {baseline:.3f}")
    print(f"{'signal':18s} {'in-sample':>10s} {'LOOCV':>8s} {'vs baseline':>12s}")
    labels = [r["answerable"] for r in rows]
    results = []
    for sig in ("top1_distance", "mean_distance"):
        vals = [r[sig] for r in rows]
        ins, thr, higher = fit_threshold(vals, labels)
        cv = loocv(vals, labels)
        results.append((sig, ins, cv, cv - baseline, thr, higher))
        print(f"{sig:18s} {ins:>10.3f} {cv:>8.3f} {cv - baseline:>+12.3f}")

    best = max(results, key=lambda x: x[2])
    print(f"\nbest: {best[0]}  LOOCV {best[2]:.3f} ({best[3]:+.3f} vs baseline)")
    print(f"      rule: answerable when distance "
          f"{'>=' if best[5] else '<='} {best[4]:.4f}")

    # Separation of the two distributions.
    pa = [r["top1_distance"] for r in rows if r["answerable"]]
    na = [r["top1_distance"] for r in rows if not r["answerable"]]
    pooled = statistics.pstdev([r["top1_distance"] for r in rows]) or 1e-9
    print(f"\nstandardised separation: "
          f"{(statistics.mean(na) - statistics.mean(pa)) / pooled:+.2f} "
          f"(answerable mean {statistics.mean(pa):.4f}, "
          f"unanswerable mean {statistics.mean(na):.4f})")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
