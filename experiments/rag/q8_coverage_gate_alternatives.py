"""
Q8 — what would a CORRECT coverage gate look like?

Q1 established that fast_coverage's gate is broken: it thresholds RRF score,
which scores a rank, so `covered` is True whenever any slide survives filtering.
covered=True for 31/31 real queries including "kaju katli".

The coverage question is not the same as the abstention question, and the
difference matters. Abstention SUPPRESSES an answer - a false abstention means
the student gets nothing. A coverage verdict is a LABEL on an answer that is
shown either way: the student still receives the slides and the explanation,
and a wrong "not covered" costs them a moment of doubt rather than the content.

So the operating point should be different. For abstention the evidence said
protect recall at almost any cost. For coverage, saying "this doesn't look like
it's in your material" about something that is, is a much cheaper error than
confidently telling a student their syllabus covers kaju katli.

This evaluates candidate gates on all three labelled populations at once,
including the real queries, and reports the confusion matrix rather than a
single score.

Nothing is promoted. READ-ONLY.
"""

import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

EXPANDED = REPO / "experiments" / "benchmarks" / "expanded_features.json"
INDEP = REPO / "experiments" / "benchmarks" / "p11_negation_safe.json"
REAL = REPO / "experiments" / "benchmarks" / "q3_real_queries.json"
OUT = REPO / "experiments" / "benchmarks" / "q8_coverage_gates.json"


def load():
    exp = [{"d": r["dense_top1"], "a": r["answerable"], "src": "constructed"}
           for r in json.loads(EXPANDED.read_text(encoding="utf-8"))
           if r["dense_top1"] is not None]
    ind = [{"d": r["dense_top1"], "a": r["answerable"], "src": "independent PYQ"}
           for r in json.loads(INDEP.read_text(encoding="utf-8"))["independent"]["baseline"]]
    real = [{"d": r["dense_top1"], "a": r["label"] == "answerable",
             "src": "real queries", "q": r["query"]}
            for r in json.loads(REAL.read_text(encoding="utf-8"))
            if r["label"] in ("answerable", "unanswerable")]
    return {"constructed": exp, "independent PYQ": ind, "real queries": real}


def confusion(rows, predicate):
    tp = sum(1 for r in rows if r["a"] and predicate(r))
    fn = sum(1 for r in rows if r["a"] and not predicate(r))
    fp = sum(1 for r in rows if not r["a"] and predicate(r))
    tn = sum(1 for r in rows if not r["a"] and not predicate(r))
    npos, nneg = tp + fn, fp + tn
    return {
        "said_covered_correctly": tp, "said_not_covered_wrongly": fn,
        "said_covered_wrongly": fp, "said_not_covered_correctly": tn,
        "recall": tp / npos if npos else 0.0,
        "specificity": tn / nneg if nneg else 0.0,
        "n_pos": npos, "n_neg": nneg,
    }


def main():
    pops = load()
    print("Populations (all labelled lexically, never by distance):")
    for name, rows in pops.items():
        print(f"  {name:18s} {len(rows):>4d} items "
              f"({sum(1 for r in rows if r['a'])} covered / "
              f"{sum(1 for r in rows if not r['a'])} not)")

    gates = {
        "production (RRF)": lambda r: True,     # proven equivalent to always-true
    }
    for t in (0.19, 0.20, 0.21, 0.22, 0.23):
        gates[f"dense <= {t:.2f}"] = (lambda t: lambda r: r["d"] <= t)(t)

    print("\n" + "=" * 96)
    print("Each gate on each population. 'wrongly covered' is the kaju katli error.")
    print("=" * 96)
    results = {}
    for gname, pred in gates.items():
        results[gname] = {}
        print(f"\n{gname}")
        print(f"  {'population':20s} {'recall':>8s} {'specificity':>12s} "
              f"{'wrongly covered':>16s} {'wrongly not covered':>20s}")
        for pname, rows in pops.items():
            c = confusion(rows, pred)
            results[gname][pname] = c
            print(f"  {pname:20s} {c['recall']:>8.3f} {c['specificity']:>12.3f} "
                  f"{c['said_covered_wrongly']:>7d}/{c['n_neg']:<8d} "
                  f"{c['said_not_covered_wrongly']:>10d}/{c['n_pos']:<9d}")

    # The specific queries that motivated this.
    print("\n" + "=" * 96)
    print("The real queries that should NOT be reported as covered")
    print("=" * 96)
    real = [r for r in json.loads(REAL.read_text(encoding="utf-8"))
            if r["label"] == "unanswerable"]
    print(f"{'query':26s} {'subject':8s} {'dense':>7s}  verdict under each gate")
    for r in sorted(real, key=lambda x: -x["dense_top1"]):
        verdicts = []
        for t in (0.19, 0.21, 0.23):
            verdicts.append(f"T{t}:{'COVERED' if r['dense_top1'] <= t else 'not'}")
        print(f"{r['query'][:26]:26s} {r['subject'][:8]:8s} "
              f"{r['dense_top1']:>7.4f}  RRF:COVERED  " + "  ".join(verdicts))

    # And the answerable real queries a gate would wrongly reject.
    print("\nAnswerable real queries each gate would wrongly call NOT covered:")
    ans = [r for r in json.loads(REAL.read_text(encoding="utf-8"))
           if r["label"] == "answerable"]
    for t in (0.19, 0.21, 0.23):
        bad = [r["query"] for r in ans if r["dense_top1"] > t]
        print(f"  T={t}: {len(bad)}/{len(ans)}  {bad[:4]}")

    print("\n" + "=" * 96)
    print("READ THIS BEFORE ACTING ON THE TABLE ABOVE")
    print("=" * 96)
    print("The real-query population has only 4 unanswerable items. A gate")
    print("fitted to separate 4 points is fitted to noise. What the three")
    print("populations agree on is the ORDERING - nonsense queries land further")
    print("away than real ones - not the value of any particular threshold.")
    print()
    print("The defensible claim is narrow: the current gate is equivalent to")
    print("'always true' and any distance-based gate is strictly better than")
    print("that, because a gate with zero specificity carries no information.")

    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
