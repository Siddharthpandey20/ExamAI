"""
G1b — analysis of the grounding run.

Reports deterministic metrics and judged metrics SEPARATELY and never blends
them. The mechanical checks (citation validity, lexical grounding) are facts
about the text; the judged ones are one model's opinion about another model's
output, and the judge here is the same model that produced the answers, which
is a known source of leniency. Where they disagree, the mechanical number is
the one to trust.

Computes only.
"""

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

DATA = REPO / "experiments" / "benchmarks" / "g1_grounding.json"


def main():
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    ans = [r for r in rows if r["kind"] == "answerable"]
    ins = [r for r in rows if r["kind"] == "insufficient"]
    print(f"{len(rows)} answers graded: {len(ans)} answerable, "
          f"{len(ins)} insufficient-evidence\n")

    # ── 1. citations, entirely mechanical ────────────────────────────────
    print("=" * 78)
    print("1. CITATIONS - mechanical, no judgement involved")
    print("=" * 78)
    for label, grp in (("answerable", ans), ("insufficient", ins)):
        if not grp:
            continue
        tot_c = sum(r["n_citations"] for r in grp)
        tot_v = sum(r["n_valid_citations"] for r in grp)
        tot_p = sum(r["n_page_only_valid"] for r in grp)
        tot_f = sum(r["n_fabricated_citations"] for r in grp)
        none = sum(1 for r in grp if r["n_citations"] == 0)
        print(f"\n{label} (n={len(grp)}):")
        print(f"  citations emitted                : {tot_c}")
        print(f"  exact (page+file) match in context: {tot_v} "
              f"({tot_v/tot_c:.1%})" if tot_c else "  none emitted")
        if tot_c:
            print(f"  page number present in context   : {tot_p} ({tot_p/tot_c:.1%})")
            print(f"  page NOT in context (fabricated) : {tot_f} ({tot_f/tot_c:.1%})")
        print(f"  answers with no citation at all  : {none}/{len(grp)} "
              f"({none/len(grp):.1%})")
        if label == "answerable":
            gold_ctx = [r for r in grp if r["gold_in_context"]]
            cited = sum(1 for r in gold_ctx if r["cited_gold"])
            if gold_ctx:
                print(f"  gold slide was in context        : {len(gold_ctx)}/{len(grp)}")
                print(f"  ...and was cited                 : {cited}/{len(gold_ctx)} "
                      f"({cited/len(gold_ctx):.1%})")

    fab = [r for r in rows if r["n_fabricated_citations"] > 0]
    if fab:
        print(f"\nexamples of fabricated citations (page not in the context given):")
        for r in fab[:5]:
            print(f"  [{r['kind']:12s}] {r['question'][:52]!r}")
            print(f"      claimed {r['fabricated']}")

    # ── 2. lexical grounding, mechanical ─────────────────────────────────
    print("\n" + "=" * 78)
    print("2. LEXICAL GROUNDING - share of the answer's content terms that")
    print("   appear in the context. Lenient: paraphrase counts as grounded.")
    print("=" * 78)
    print(f"{'group':16s} {'n':>4s} {'mean':>7s} {'p10':>7s} {'median':>7s} "
          f"{'<0.8':>7s} {'<0.6':>7s}")
    for label, grp in (("answerable", ans), ("insufficient", ins)):
        if not grp:
            continue
        v = sorted(r["lex_grounding"] for r in grp)
        lo80 = sum(1 for x in v if x < 0.8) / len(v)
        lo60 = sum(1 for x in v if x < 0.6) / len(v)
        print(f"{label:16s} {len(v):>4d} {statistics.mean(v):>7.3f} "
              f"{v[len(v)//10]:>7.3f} {statistics.median(v):>7.3f} "
              f"{lo80:>7.1%} {lo60:>7.1%}")

    worst = sorted(rows, key=lambda r: r["lex_grounding"])[:5]
    print("\nleast-grounded answers, and the terms not present in their context:")
    for r in worst:
        print(f"  [{r['lex_grounding']:.2f}] {r['question'][:50]!r}")
        print(f"      {r['ungrounded_sample']}")

    # ── 3. THE headline: behaviour when evidence is absent ───────────────
    print("\n" + "=" * 78)
    print("3. WHAT HAPPENS WHEN THE ANSWER IS NOT IN THE MATERIAL")
    print("=" * 78)
    if ins:
        declined = [r for r in ins
                    if r.get("judge") and r["judge"].get("declines")]
        print(f"  questions whose answer is verifiably absent : {len(ins)}")
        print(f"  answers that said so                        : {len(declined)} "
              f"({len(declined)/len(ins):.1%})")
        print(f"  answers that answered anyway                : "
              f"{len(ins)-len(declined)} ({1-len(declined)/len(ins):.1%})")
        cited = sum(r["n_citations"] for r in ins)
        print(f"  slide citations emitted for absent topics   : {cited}")
        print("\n  sample answers to questions the material does not cover:")
        for r in ins[:4]:
            d = r["judge"].get("declines") if r.get("judge") else "?"
            print(f"    {r['question'][:60]!r}")
            print(f"      declines={d} citations={r['n_citations']} "
                  f"grounding={r['lex_grounding']:.2f}")
            print(f"      {r['answer'][:150]!r}")

    # ── 4. judged metrics, reported separately ───────────────────────────
    print("\n" + "=" * 78)
    print("4. JUDGED METRICS - one model grading another, including its own")
    print("   output. Treat as indicative, not as ground truth.")
    print("=" * 78)
    for label, grp in (("answerable", ans), ("insufficient", ins)):
        j = [r["judge"] for r in grp if r.get("judge")]
        if not j:
            print(f"{label}: no judge output")
            continue
        c = Counter(x.get("correct") for x in j)
        g = Counter(x.get("grounded") for x in j)
        uns = [x.get("unsupported_claims", 0) or 0 for x in j]
        print(f"\n{label} (judged {len(j)}/{len(grp)}):")
        print(f"  correct   2={c.get(2,0)} 1={c.get(1,0)} 0={c.get(0,0)}   "
              f"mean {statistics.mean([x.get('correct',0) or 0 for x in j]):.2f}/2")
        print(f"  grounded  2={g.get(2,0)} 1={g.get(1,0)} 0={g.get(0,0)}   "
              f"mean {statistics.mean([x.get('grounded',0) or 0 for x in j]):.2f}/2")
        print(f"  unsupported claims: total {sum(uns)}, "
              f"mean {statistics.mean(uns):.2f}/answer, "
              f"answers with >=1: {sum(1 for u in uns if u)}/{len(j)}")

    # ── 5. is the failure retrieval or generation? ───────────────────────
    print("\n" + "=" * 78)
    print("5. RETRIEVAL OR GENERATION? - the question this phase exists to answer")
    print("=" * 78)
    have = [r for r in ans if r.get("judge") and r["gold_in_context"] is not None]
    if have:
        gold_in = [r for r in have if r["gold_in_context"]]
        gold_out = [r for r in have if not r["gold_in_context"]]
        print(f"{'case':44s} {'n':>4s} {'correct(0-2)':>13s} {'grounded':>9s}")
        for label, grp in ((f"gold slide WAS in context", gold_in),
                           (f"gold slide was NOT in context", gold_out)):
            if not grp:
                continue
            cm = statistics.mean([r["judge"].get("correct", 0) or 0 for r in grp])
            gm = statistics.mean([r["judge"].get("grounded", 0) or 0 for r in grp])
            print(f"{label:44s} {len(grp):>4d} {cm:>13.2f} {gm:>9.2f}")
        if gold_in:
            failed = [r for r in gold_in if (r["judge"].get("correct", 0) or 0) < 2]
            print(f"\n  Retrieval succeeded but the answer still was not fully "
                  f"correct: {len(failed)}/{len(gold_in)} ({len(failed)/len(gold_in):.1%})")
            print("  That fraction is the share of the problem that generation "
                  "owns.")

    print(f"\nmean generation latency: "
          f"{statistics.median([r['gen_ms'] for r in rows]):.0f} ms p50")


if __name__ == "__main__":
    main()
