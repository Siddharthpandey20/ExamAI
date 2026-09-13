"""
G3b — did agentic or iterative retrieval earn its cost?

The decision rule is set before looking at the numbers: agentic RAG is
justified only if it improves answer quality by more than the extra latency and
token cost can be defended. A retrieval gain that does not reach the answer is
not a gain, and an answer gain bought with 3x the calls has to be large.

Reports quality and cost side by side, and breaks quality down by query kind,
because the interesting question is not "is the agent better on average" but
"is there a class of query where it is decisively better" - which would justify
routing rather than replacing.

Computes only.
"""

import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

DATA = REPO / "experiments" / "benchmarks" / "g6_agentic.json"
SYSTEMS = ["baseline", "iterative", "agentic"]


def jval(r, key, default=0):
    j = r.get("judge") or {}
    v = j.get(key, default)
    return v if isinstance(v, (int, float)) else default


def main():
    rows = json.loads(DATA.read_text(encoding="utf-8"))
    by_sys = defaultdict(list)
    for r in rows:
        by_sys[r["system"]].append(r)
    kinds = sorted({r["kind"] for r in rows})
    n = len(by_sys["baseline"])
    print(f"{n} hard queries x {len(SYSTEMS)} systems = {len(rows)} runs")
    print(f"kinds: {dict(Counter(r['kind'] for r in by_sys['baseline']))}\n")

    # ── quality ──────────────────────────────────────────────────────────
    print("=" * 86)
    print("QUALITY  (correct and grounded are judged 0-2; rest is mechanical)")
    print("=" * 86)
    print(f"{'system':12s} {'correct':>8s} {'grounded':>9s} {'unsupported':>12s} "
          f"{'citations':>10s} {'lex_ground':>11s} {'R@any':>7s}")
    for s in SYSTEMS:
        g = by_sys[s]
        hits = [r for r in g if r["hit"] is not None]
        print(f"{s:12s} "
              f"{statistics.mean([jval(r,'correct') for r in g]):>8.2f} "
              f"{statistics.mean([jval(r,'grounded') for r in g]):>9.2f} "
              f"{statistics.mean([jval(r,'unsupported_claims') for r in g]):>12.2f} "
              f"{statistics.mean([r['n_citations'] for r in g]):>10.1f} "
              f"{statistics.mean([r['lex_grounding'] for r in g]):>11.3f} "
              f"{(sum(1 for r in hits if r['hit'])/len(hits) if hits else 0):>7.3f}")

    # ── cost ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 86)
    print("COST  (measured, not estimated)")
    print("=" * 86)
    print(f"{'system':12s} {'LLM calls':>10s} {'retrievals':>11s} "
          f"{'prompt tok':>11s} {'compl tok':>10s} {'total tok':>10s} "
          f"{'p50 ms':>8s} {'p95 ms':>8s}")
    base_tok = base_ms = None
    for s in SYSTEMS:
        g = by_sys[s]
        pt = statistics.mean([r["prompt_tokens"] for r in g])
        ct = statistics.mean([r["completion_tokens"] for r in g])
        w = sorted(r["wall_ms"] for r in g)
        if s == "baseline":
            base_tok, base_ms = pt + ct, statistics.median(w)
        print(f"{s:12s} {statistics.mean([r['llm_calls'] for r in g]):>10.2f} "
              f"{statistics.mean([r['retrievals'] for r in g]):>11.2f} "
              f"{pt:>11.0f} {ct:>10.0f} {pt+ct:>10.0f} "
              f"{statistics.median(w):>8.0f} {w[int(len(w)*0.95)]:>8.0f}")

    print(f"\n{'system':12s} {'tokens vs baseline':>20s} {'latency vs baseline':>21s}")
    for s in SYSTEMS:
        g = by_sys[s]
        tok = statistics.mean([r["prompt_tokens"] + r["completion_tokens"] for r in g])
        ms = statistics.median([r["wall_ms"] for r in g])
        print(f"{s:12s} {tok/base_tok:>19.2f}x {ms/base_ms:>20.2f}x")

    # ── quality by query kind ────────────────────────────────────────────
    print("\n" + "=" * 86)
    print("CORRECTNESS BY QUERY KIND - is there a class the agent rescues?")
    print("=" * 86)
    print(f"{'kind':16s} {'n':>3s} " + " ".join(f"{s:>13s}" for s in SYSTEMS))
    for k in kinds:
        cells = []
        for s in SYSTEMS:
            g = [r for r in by_sys[s] if r["kind"] == k]
            cells.append(f"{statistics.mean([jval(r,'correct') for r in g]):.2f}"
                         if g else "-")
        nk = len([r for r in by_sys['baseline'] if r['kind'] == k])
        print(f"{k:16s} {nk:>3d} " + " ".join(f"{c:>13s}" for c in cells))

    print("\nGROUNDEDNESS BY QUERY KIND")
    print(f"{'kind':16s} {'n':>3s} " + " ".join(f"{s:>13s}" for s in SYSTEMS))
    for k in kinds:
        cells = []
        for s in SYSTEMS:
            g = [r for r in by_sys[s] if r["kind"] == k]
            cells.append(f"{statistics.mean([jval(r,'grounded') for r in g]):.2f}"
                         if g else "-")
        nk = len([r for r in by_sys['baseline'] if r['kind'] == k])
        print(f"{k:16s} {nk:>3d} " + " ".join(f"{c:>13s}" for c in cells))

    # ── the insufficient-evidence case, which matters most ───────────────
    print("\n" + "=" * 86)
    print("INSUFFICIENT EVIDENCE - does the system say so?")
    print("=" * 86)
    print(f"{'system':12s} {'n':>4s} {'declined':>10s} {'answered anyway':>17s} "
          f"{'citations emitted':>18s}")
    for s in SYSTEMS:
        g = [r for r in by_sys[s] if r["kind"] == "insufficient"]
        if not g:
            continue
        dec = sum(1 for r in g if (r.get("judge") or {}).get("declines"))
        cit = sum(r["n_citations"] for r in g)
        print(f"{s:12s} {len(g):>4d} {dec}/{len(g)} = {dec/len(g):>4.0%}   "
              f"{len(g)-dec}/{len(g)} = {1-dec/len(g):>5.0%}   {cit:>15d}")

    # ── paired comparison vs baseline ────────────────────────────────────
    print("\n" + "=" * 86)
    print("PAIRED, PER QUERY - where each system beats or loses to baseline")
    print("=" * 86)
    base = {r["id"]: r for r in by_sys["baseline"]}
    for s in ("iterative", "agentic"):
        better = worse = same = 0
        for r in by_sys[s]:
            b = base.get(r["id"])
            if not b:
                continue
            d = jval(r, "correct") - jval(b, "correct")
            if d > 0:
                better += 1
            elif d < 0:
                worse += 1
            else:
                same += 1
        print(f"  {s:11s} vs baseline on correctness: "
              f"{better} better, {worse} worse, {same} tied")

    # ── verdict ──────────────────────────────────────────────────────────
    print("\n" + "=" * 86)
    print("VERDICT")
    print("=" * 86)
    bc = statistics.mean([jval(r, 'correct') for r in by_sys["baseline"]])
    for s in ("iterative", "agentic"):
        g = by_sys[s]
        sc = statistics.mean([jval(r, 'correct') for r in g])
        tok = statistics.mean([r["prompt_tokens"] + r["completion_tokens"] for r in g])
        ms = statistics.median([r["wall_ms"] for r in g])
        print(f"  {s:11s}: correctness {sc-bc:+.2f}/2  for {tok/base_tok:.2f}x tokens "
              f"and {ms/base_ms:.2f}x latency")
    print("\n  Agentic RAG is justified only if the quality gain is worth the")
    print("  extra cost. Read the two lines above together, not separately.")


if __name__ == "__main__":
    main()
