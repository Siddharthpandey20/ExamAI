"""
H1b — did raw text or source-id citations improve grounding?

Mechanical metrics first and judged metrics second, never blended. The judge is
the same model family that wrote the answers, so it is reported as indicative;
the citation and specifics checks are facts about the text.

Computes only.
"""

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

DATA = REPO / "experiments" / "benchmarks" / "h1_grounding_variants.json"
ORDER = ["A_current", "B_raw_text", "C_source_ids"]


def jv(r, k, d=0):
    j = r.get("judge") or {}
    v = j.get(k, d)
    return v if isinstance(v, (int, float)) else d


def main():
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    by = defaultdict(list)
    for r in rows:
        by[r["variant"]].append(r)
    n = len(by[ORDER[0]])
    ans = {v: [r for r in by[v] if r["kind"] == "answerable"] for v in ORDER}
    absent = {v: [r for r in by[v] if r["kind"] == "absent"] for v in ORDER}
    print(f"{n} items per variant "
          f"({len(ans[ORDER[0]])} answerable, {len(absent[ORDER[0]])} absent)")
    print("retrieval held fixed across variants\n")

    # ── 1. citations, mechanical ─────────────────────────────────────────
    print("=" * 84)
    print("1. CITATIONS - mechanical. 'fabricated' = names a source never supplied")
    print("=" * 84)
    print(f"{'variant':16s} {'cites/ans':>10s} {'valid':>8s} {'fabricated':>11s} "
          f"{'fab rate':>9s} {'no-such-file':>13s} {'no citation':>12s}")
    for v in ORDER:
        g = by[v]
        tot = sum(r["n_citations"] for r in g)
        val = sum(r["n_valid"] for r in g)
        fab = sum(r["n_fabricated"] for r in g)
        nsf = sum(r["nonexistent_file"] for r in g)
        none = sum(1 for r in g if r["n_citations"] == 0)
        print(f"{v:16s} {tot/len(g):>10.1f} {val:>8d} {fab:>11d} "
              f"{(fab/tot if tot else 0):>8.1%} {nsf:>13d} {none:>7d}/{len(g):<4}")

    print("\nfabricated citations by variant:")
    for v in ORDER:
        ex = [(r["kind"], r["fabricated"]) for r in by[v] if r["n_fabricated"]]
        print(f"  {v:16s} {len(ex)} answers affected")
        for kind, f in ex[:3]:
            print(f"      [{kind}] {f}")

    # ── 2. did it cite the gold slide? ───────────────────────────────────
    print("\n" + "=" * 84)
    print("2. CITATION COMPLETENESS - gold slide in context, was it cited?")
    print("=" * 84)
    print(f"{'variant':16s} {'gold in ctx':>12s} {'cited gold':>12s} {'rate':>8s}")
    for v in ORDER:
        g = [r for r in ans[v] if r["gold_in_context"]]
        cited = sum(1 for r in g if r["cited_gold"])
        print(f"{v:16s} {len(g):>12d} {cited:>12d} "
              f"{(cited/len(g) if g else 0):>8.1%}")

    # ── 3. unsupported specifics, mechanical ─────────────────────────────
    print("\n" + "=" * 84)
    print("3. UNSUPPORTED SPECIFICS - numbers/acronyms absent from the context")
    print("=" * 84)
    print(f"{'variant':16s} {'per answer':>11s} {'answers with >=1':>17s} "
          f"{'context chars':>14s}")
    for v in ORDER:
        g = by[v]
        u = [r["n_unsupported_specifics"] for r in g]
        print(f"{v:16s} {statistics.mean(u):>11.2f} "
              f"{sum(1 for x in u if x)}/{len(g):<15} "
              f"{statistics.mean([r['context_chars'] for r in g]):>14.0f}")

    # ── 4. absent-topic behaviour ────────────────────────────────────────
    print("\n" + "=" * 84)
    print("4. TOPICS THE MATERIAL DOES NOT COVER")
    print("=" * 84)
    print(f"{'variant':16s} {'n':>3s} {'declined':>10s} {'citations emitted':>18s} "
          f"{'fabricated':>11s}")
    for v in ORDER:
        g = absent[v]
        dec = sum(1 for r in g if (r.get("judge") or {}).get("declines"))
        print(f"{v:16s} {len(g):>3d} {dec}/{len(g)} = {dec/len(g):>4.0%}   "
              f"{sum(r['n_citations'] for r in g):>15d} "
              f"{sum(r['n_fabricated'] for r in g):>11d}")

    # ── 5. judged ────────────────────────────────────────────────────────
    print("\n" + "=" * 84)
    print("5. JUDGED (indicative - same model family graded its own output)")
    print("=" * 84)
    print(f"{'variant':16s} {'correct':>8s} {'grounded':>9s} {'unsupported':>12s} "
          f"{'ans chars':>10s} {'ms':>7s}")
    for v in ORDER:
        g = by[v]
        print(f"{v:16s} {statistics.mean([jv(r,'correct') for r in g]):>8.2f} "
              f"{statistics.mean([jv(r,'grounded') for r in g]):>9.2f} "
              f"{statistics.mean([jv(r,'unsupported_claims') for r in g]):>12.2f} "
              f"{statistics.mean([r['answer_chars'] for r in g]):>10.0f} "
              f"{statistics.median([r['wall_ms'] for r in g]):>7.0f}")

    print(f"\n{'variant':16s} {'correct (answerable only)':>26s} {'grounded':>10s}")
    for v in ORDER:
        g = ans[v]
        print(f"{v:16s} {statistics.mean([jv(r,'correct') for r in g]):>26.2f} "
              f"{statistics.mean([jv(r,'grounded') for r in g]):>10.2f}")

    # ── 6. paired ────────────────────────────────────────────────────────
    print("\n" + "=" * 84)
    print("6. PAIRED vs A_current")
    print("=" * 84)
    base = {r["id"]: r for r in by["A_current"]}
    for v in ORDER[1:]:
        b = w = t = 0
        for r in by[v]:
            d = jv(r, "correct") - jv(base[r["id"]], "correct")
            b += d > 0; w += d < 0; t += d == 0
        gb = gw = gt = 0
        for r in by[v]:
            d = jv(r, "grounded") - jv(base[r["id"]], "grounded")
            gb += d > 0; gw += d < 0; gt += d == 0
        print(f"  {v:14s} correct : {b} better, {w} worse, {t} tied")
        print(f"  {'':14s} grounded: {gb} better, {gw} worse, {gt} tied")

    # ── verdict ──────────────────────────────────────────────────────────
    print("\n" + "=" * 84)
    print("VERDICT")
    print("=" * 84)
    a = by["A_current"]
    fab_a = sum(r["n_fabricated"] for r in a)
    tot_a = sum(r["n_citations"] for r in a)
    for v in ORDER[1:]:
        g = by[v]
        fab = sum(r["n_fabricated"] for r in g)
        tot = sum(r["n_citations"] for r in g)
        ctx = (statistics.mean([r["context_chars"] for r in g])
               / statistics.mean([r["context_chars"] for r in a]))
        print(f"  {v:14s} fabricated {fab_a}->{fab} "
              f"({(fab_a/tot_a if tot_a else 0):.1%} -> {(fab/tot if tot else 0):.1%}), "
              f"context {ctx:.2f}x, "
              f"grounded {statistics.mean([jv(r,'grounded') for r in a]):.2f}"
              f"->{statistics.mean([jv(r,'grounded') for r in g]):.2f}")


if __name__ == "__main__":
    main()
