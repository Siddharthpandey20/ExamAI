"""
Q3 — where do genuine student queries land, relative to the evaluation sets?

This is the question every previous phase deferred. The answer changes how much
weight the abstention evidence deserves, because a threshold calibrated on
generated questions is only useful if real ones are distributed similarly.

Source: the 31 distinct free-text queries in query_cache, typed by the user
between 2026-03-09 and 2026-04-06 - before any of this work started, so they
cannot have been influenced by it. Nothing is fabricated.

LABELS ARE ASSIGNED LEXICALLY, never by distance. Each query's rarest content
term must occur in the target subject's slides for it to count as answerable -
the same anchor rule used to build the negative sets in P1 and P10. Using
dense distance to label the data would guarantee the conclusion.

Queries the rule cannot decide are reported as UNKNOWN rather than guessed.

READ-ONLY.
"""

import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from indexing.database import SessionFactory   # noqa: E402
from indexing.models import Slide              # noqa: E402

AUDIT = REPO / "experiments" / "benchmarks" / "q1_coverage_audit.json"
EXPANDED = REPO / "experiments" / "benchmarks" / "expanded_features.json"
INDEP = REPO / "experiments" / "benchmarks" / "p11_negation_safe.json"
OUT = REPO / "experiments" / "benchmarks" / "q3_real_queries.json"

STOP = set("""what how why is are the a an of in on for to and or not does do can
which when where who explain describe define tell me about between with from
that this it its their there they be been being has have had will would should
covered cover slide slides class detail present my document documents wrt
comprehensive generate create organise organize include specific reference
references priority exam hours before optimised optimized schedule revision
key concepts meaning need we b/w or""".split())


def terms(t):
    return [w for w in re.findall(r"[a-z0-9]+", (t or "").lower())
            if len(w) > 2 and w not in STOP]


def main():
    rows = json.loads(AUDIT.read_text(encoding="utf-8"))

    session = SessionFactory()
    try:
        counts = {}
        for sl in session.query(Slide).filter(Slide.is_embedded == True).all():  # noqa: E712
            c = counts.setdefault(sl.subject, Counter())
            c.update(terms(f"{sl.summary or ''} {sl.concepts or ''} "
                           f"{sl.raw_text or ''}"))
    finally:
        session.close()

    # A first version labelled on the RAREST term alone and got two of these
    # wrong, which is worth recording because the same brittleness would have
    # corrupted the headline number:
    #
    #   "reliably send emails application" -> CN was called unanswerable
    #   because 'emails' occurs 0x. 'email' occurs 24x and 'e-mail' 49x. A
    #   plural, not an absence.
    #
    #   "...difference b/w imap and ftp? why we need pop3?" was called
    #   unanswerable because 'pop3' occurs 0x, even though 'imap' occurs 40x
    #   and 'ftp' is covered. One uncovered clause in a multi-part question
    #   does not make the question unanswerable.
    #
    # So: coverage over ALL content terms, with light morphology. Still purely
    # lexical and still independent of any embedding.
    def occurs(word, subj_counts):
        if subj_counts.get(word, 0):
            return subj_counts[word]
        for variant in (word.rstrip("s"), word + "s", word.rstrip("es"),
                        word.replace("-", "")):
            if variant != word and subj_counts.get(variant, 0):
                return subj_counts[variant]
        return 0

    SYSTEM_PROMPT_MARKERS = ("comprehensive study plan", "revision schedule",
                             "hours before my")

    for r in rows:
        ql = r["query"].lower()
        if any(m in ql for m in SYSTEM_PROMPT_MARKERS):
            r["label"] = "system_prompt"
            r["why"] = "app-generated prompt, not a student question"
            continue
        qt = set(terms(r["query"]))
        subj_counts = counts.get(r["subject"], Counter())
        if not qt:
            r["label"], r["why"] = "unknown", "no content terms after stopwords"
            continue
        present = {w: occurs(w, subj_counts) for w in qt}
        covered = sum(1 for v in present.values() if v > 0)
        frac = covered / len(qt)
        r["term_coverage"] = round(frac, 2)
        r["missing_terms"] = sorted(w for w, v in present.items() if v == 0)
        if frac >= 0.6:
            r["label"] = "answerable"
            r["why"] = f"{covered}/{len(qt)} terms present"
        elif frac <= 0.2:
            r["label"] = "unanswerable"
            r["why"] = f"only {covered}/{len(qt)} terms present"
        else:
            r["label"] = "unknown"
            r["why"] = f"{covered}/{len(qt)} terms present - borderline"

    print("=" * 96)
    print("REAL USER QUERIES - lexically labelled, sorted by dense_top1")
    print("=" * 96)
    print(f"{'query':40s} {'subj':5s} {'wd':>3s} {'dense':>7s} {'label':>12s}  why")
    for r in sorted(rows, key=lambda x: x["dense_top1"]):
        print(f"{r['query'][:40]:40s} {r['subject'][:5]:5s} {r['n_words']:>3d} "
              f"{r['dense_top1']:>7.4f} {r['label']:>12s}  {r['why'][:34]}")

    lab = Counter(r["label"] for r in rows)
    print(f"\nlabels: {dict(lab)}")

    ans = [r["dense_top1"] for r in rows if r["label"] == "answerable"]
    una = [r["dense_top1"] for r in rows if r["label"] == "unanswerable"]

    # ── the comparison that matters ──────────────────────────────────────
    exp = [r for r in json.loads(EXPANDED.read_text(encoding="utf-8"))
           if r["dense_top1"] is not None]
    ind = json.loads(INDEP.read_text(encoding="utf-8"))["independent"]["baseline"]

    def q(v, p):
        v = sorted(v)
        return v[min(int(p * len(v)), len(v) - 1)]

    print("\n" + "=" * 96)
    print("DISTANCE DISTRIBUTIONS - generated vs real")
    print("=" * 96)
    print(f"{'population':44s} {'n':>4s} {'mean':>8s} {'p10':>8s} {'p50':>8s} {'p90':>8s}")
    pops = [
        ("eval: answerable (generated)",
         [r["dense_top1"] for r in exp if r["answerable"]]),
        ("eval: plain positives only",
         [r["dense_top1"] for r in exp if r["category"] == "positive"]),
        ("eval: keyword-style positives",
         [r["dense_top1"] for r in exp if r["category"] == "positive_keyword"]),
        ("independent PYQ: answerable",
         [r["dense_top1"] for r in ind if r["answerable"]]),
        ("REAL QUERIES: answerable", ans),
        ("", []),
        ("eval: unanswerable (constructed)",
         [r["dense_top1"] for r in exp if not r["answerable"]]),
        ("independent PYQ: unanswerable",
         [r["dense_top1"] for r in ind if not r["answerable"]]),
        ("REAL QUERIES: unanswerable", una),
    ]
    for name, v in pops:
        if not name:
            print()
            continue
        if not v:
            continue
        print(f"{name:44s} {len(v):>4d} {statistics.mean(v):>8.4f} "
              f"{q(v,0.1):>8.4f} {q(v,0.5):>8.4f} {q(v,0.9):>8.4f}")

    # ── query shape ──────────────────────────────────────────────────────
    print("\n" + "=" * 96)
    print("QUERY SHAPE - what students type vs what the eval set contains")
    print("=" * 96)
    real_w = [r["n_words"] for r in rows]
    gen_w = []
    for f in (REPO / "experiments" / "benchmarks" / "hard_eval_set.json",):
        for it in json.loads(f.read_text(encoding="utf-8")):
            if it["category"] == "positive":
                gen_w.append(len(it["question"].split()))
    print(f"{'population':30s} {'n':>4s} {'median words':>13s} {'<=3 words':>11s} "
          f"{'<=6 words':>11s}")
    for name, w in (("REAL user queries", real_w),
                    ("eval plain positives", gen_w)):
        print(f"{name:30s} {len(w):>4d} {statistics.median(w):>13.0f} "
              f"{sum(1 for x in w if x <= 3)/len(w):>11.0%} "
              f"{sum(1 for x in w if x <= 6)/len(w):>11.0%}")

    # ── what a threshold would have done to these real queries ───────────
    print("\n" + "=" * 96)
    print("What a distance threshold would have done to these 31 real queries")
    print("(illustrative only - no threshold is being promoted)")
    print("=" * 96)
    print(f"{'T':>8s} {'answerable refused':>20s} {'unanswerable caught':>21s} "
          f"{'unknown refused':>17s}")
    unk = [r["dense_top1"] for r in rows if r["label"] == "unknown"] or [0.0]
    for t in (0.165, 0.1768, 0.1793, 0.19, 0.21):
        ar = sum(1 for d in ans if d > t)
        uc = sum(1 for d in una if d > t)
        ur = sum(1 for d in unk if d > t)
        print(f"{t:>8.4f} {ar}/{len(ans)} = {ar/len(ans):>11.0%} "
              f"{uc}/{len(una)} = {uc/len(una):>12.0%} "
              f"{ur}/{len(unk)} = {ur/len(unk):>8.0%}")

    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
