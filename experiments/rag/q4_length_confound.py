"""
Q4 — is dense_top1 measuring relevance, or is it measuring query length?

The suspicion comes from the evaluation data itself. Among queries that are all
ANSWERABLE and all point at the same gold slides, mean top-1 distance orders
like this:

    positive_verbose  (~30 words, padded with filler I wrote)   0.1313
    positive          (~13 words)                               0.1392
    positive_keyword  (~6 words)                                0.1544
    real user queries (~5 words median)                         0.1775

That is monotonic in length and backwards from relevance: the verbose queries
are the *least* informative - they are the plain questions plus meaningless
padding - yet they land closest to the corpus.

If that holds under control, a distance threshold is partly a LENGTH threshold,
and the reason real traffic fails it is simply that students type 5 words while
the evaluation set types 13.

Two tests:

1. OBSERVATIONAL. Correlation of word count with distance among answerable
   queries only, where answerability is constant by construction.

2. CONTROLLED. Take one question, hold its meaning fixed, and vary only the
   amount of irrelevant padding. Padding is domain-neutral English with no
   technical content, so any movement in distance is attributable to length
   alone. Also truncate the same question to k words to move the other way.

If distance falls as meaningless words are added, the signal is confounded and
no amount of threshold tuning fixes it.

READ-ONLY.
"""

import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from indexing.database import SessionFactory    # noqa: E402
from indexing.db_chroma import ChromaStore      # noqa: E402
from indexing.embedder import Embedder          # noqa: E402
from engine.tools import run_hybrid_search      # noqa: E402

EXPANDED = REPO / "experiments" / "benchmarks" / "expanded_features.json"
EVAL = REPO / "eval" / "eval_set.json"
OUT = REPO / "experiments" / "benchmarks" / "q4_length_confound.json"

# Domain-neutral padding: ordinary English, no technical vocabulary, nothing
# that overlaps any subject in the corpus. Each sentence is ~10 words.
PAD = [
    "I was sitting by the window earlier today thinking about this.",
    "The weather has been quite pleasant and calm all of this week.",
    "My friend mentioned something similar to me during lunch last Tuesday.",
    "It would be nice to finish this before the evening gets late.",
    "There is a small garden outside with several old wooden benches.",
    "Someone left a cup of tea on the table near the door.",
]


def pearson(xs, ys):
    n = len(xs)
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def main():
    # ── 1. observational ─────────────────────────────────────────────────
    rows = [r for r in json.loads(EXPANDED.read_text(encoding="utf-8"))
            if r["dense_top1"] is not None]
    print("=" * 78)
    print("1. OBSERVATIONAL - among ANSWERABLE queries only")
    print("=" * 78)
    ans = [r for r in rows if r["answerable"]]
    # word counts must come from the eval sets, so re-derive them
    hard = {it["id"]: it["question"] for it in
            json.loads((REPO / "experiments" / "benchmarks"
                        / "hard_eval_set.json").read_text(encoding="utf-8"))}
    neg = {it["id"]: it["question"] for it in
           json.loads((REPO / "experiments" / "benchmarks"
                       / "negation_eval.json").read_text(encoding="utf-8"))["retrieval_items"]}
    hard.update(neg)
    xs, ys = [], []
    for r in ans:
        q = hard.get(r["id"])
        if q:
            xs.append(len(q.split()))
            ys.append(r["dense_top1"])
    print(f"n = {len(xs)} answerable queries")
    print(f"Pearson r(word count, dense_top1) = {pearson(xs, ys):+.3f}")
    print("\nmean distance by length bucket:")
    print(f"{'words':>12s} {'n':>4s} {'mean dense':>11s}")
    buckets = [(0, 4), (5, 8), (9, 14), (15, 24), (25, 999)]
    for lo, hi in buckets:
        v = [y for x, y in zip(xs, ys) if lo <= x <= hi]
        if v:
            label = f"{lo}-{hi}" if hi < 999 else f"{lo}+"
            print(f"{label:>12s} {len(v):>4d} {statistics.mean(v):>11.4f}")

    # ── 2. controlled ────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("2. CONTROLLED - same question, only the amount of padding varies")
    print("=" * 78)
    eval_set = json.loads(EVAL.read_text(encoding="utf-8"))[:20]
    embedder, chroma = Embedder(), ChromaStore()
    session = SessionFactory()

    results = {"pad": {}, "truncate": {}}
    try:
        # Padding: append irrelevant, domain-neutral sentences.
        print("\npadding with IRRELEVANT domain-neutral English:")
        print(f"{'padding':>18s} {'words':>7s} {'mean dense':>11s} {'R@1':>6s} {'R@5':>6s}")
        for n_pad in (0, 1, 2, 3, 4, 6):
            dists, hits1, hits5, wc = [], 0, 0, []
            for qa in eval_set:
                q = qa["question"] + ("" if not n_pad else " " + " ".join(PAD[:n_pad]))
                stats = {}
                res = run_hybrid_search(q, qa["subject"], session, embedder,
                                        chroma, top_k=5, stats=stats)
                ids = [r["slide_id"] for r in res]
                dists.append(stats["dense_top1"])
                hits1 += ids[:1] == [qa["gold_slide_id"]]
                hits5 += qa["gold_slide_id"] in ids
                wc.append(len(q.split()))
            m = statistics.mean(dists)
            results["pad"][n_pad] = {"mean_dense": m, "r1": hits1 / len(eval_set),
                                     "r5": hits5 / len(eval_set),
                                     "mean_words": statistics.mean(wc)}
            print(f"{f'+{n_pad*10} words':>18s} {statistics.mean(wc):>7.0f} "
                  f"{m:>11.4f} {hits1/len(eval_set):>6.3f} {hits5/len(eval_set):>6.3f}")

        # Truncation: keep only the first k words of the real question.
        print("\ntruncating the SAME questions to their first k words:")
        print(f"{'k':>18s} {'words':>7s} {'mean dense':>11s} {'R@1':>6s} {'R@5':>6s}")
        for k in (2, 3, 5, 8, 12, 999):
            dists, hits1, hits5, wc = [], 0, 0, []
            for qa in eval_set:
                q = " ".join(qa["question"].split()[:k])
                stats = {}
                res = run_hybrid_search(q, qa["subject"], session, embedder,
                                        chroma, top_k=5, stats=stats)
                ids = [r["slide_id"] for r in res]
                dists.append(stats["dense_top1"])
                hits1 += ids[:1] == [qa["gold_slide_id"]]
                hits5 += qa["gold_slide_id"] in ids
                wc.append(len(q.split()))
            m = statistics.mean(dists)
            label = "full" if k == 999 else str(k)
            results["truncate"][label] = {
                "mean_dense": m, "r1": hits1 / len(eval_set),
                "r5": hits5 / len(eval_set), "mean_words": statistics.mean(wc)}
            print(f"{label:>18s} {statistics.mean(wc):>7.0f} {m:>11.4f} "
                  f"{hits1/len(eval_set):>6.3f} {hits5/len(eval_set):>6.3f}")

        # The decisive control: pad an UNANSWERABLE query the same way.
        # If padding lowers its distance too, distance is not tracking
        # answerability at all.
        print("\nthe decisive control - padding queries whose answer is ABSENT:")
        print(f"{'padding':>18s} {'mean dense':>11s}")
        absent = [("kaju katli", "ML"), ("kaju katli", "CA"),
                  ("linear regression", "CA"), ("Linear Algebra", "CN"),
                  ("ARQ", "CA")]
        results["absent_pad"] = {}
        for n_pad in (0, 2, 4, 6):
            dists = []
            for q0, subj in absent:
                q = q0 + ("" if not n_pad else " " + " ".join(PAD[:n_pad]))
                stats = {}
                run_hybrid_search(q, subj, session, embedder, chroma,
                                  top_k=5, stats=stats)
                dists.append(stats["dense_top1"])
            m = statistics.mean(dists)
            results["absent_pad"][n_pad] = m
            print(f"{f'+{n_pad*10} words':>18s} {m:>11.4f}")
    finally:
        session.close()

    # ── verdict ──────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    p0 = results["pad"][0]["mean_dense"]
    p6 = results["pad"][6]["mean_dense"]
    a0 = results["absent_pad"][0]
    a6 = results["absent_pad"][6]
    print(f"answerable queries  + 60 words of irrelevant padding: "
          f"{p0:.4f} -> {p6:.4f} ({p6-p0:+.4f})")
    print(f"  their R@1 over the same change: "
          f"{results['pad'][0]['r1']:.3f} -> {results['pad'][6]['r1']:.3f}")
    print(f"UNANSWERABLE queries + 60 words of irrelevant padding: "
          f"{a0:.4f} -> {a6:.4f} ({a6-a0:+.4f})")
    print()
    if p6 < p0 and a6 < a0:
        print("CONFOUNDED. Adding words that carry no information moves BOTH")
        print("classes toward the corpus. The distance is partly a function of")
        print("query length, so a fixed threshold penalises short queries -")
        print("which is most of real traffic.")
    elif p6 < p0:
        print("Partially confounded: padding helps answerable queries only.")
    else:
        print("Not confounded in the direction suspected.")

    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
