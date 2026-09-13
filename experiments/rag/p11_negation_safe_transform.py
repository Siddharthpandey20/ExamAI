"""
Can content_only be made negation-safe, and does its benefit survive on an
independently constructed evaluation set?

Two separate questions, deliberately not conflated:

1. SAFETY is a property, not a score. content_only maps "Is X used here?" and
   "Is X not used here?" to the same string, which is a correctness defect no
   retrieval metric can see. The test is the minimal-pair set from p7: a
   transform that collapses any pair has destroyed a distinction, and no
   balanced-accuracy number rehabilitates that. This gate is pass/fail.

2. BENEFIT has to survive leaving home. Every number in P3/P5 traces back to
   eval/eval_set.json - one generator, then degradations written by the same
   hand that later measured them. p10's PYQ set shares none of that lineage:
   real exam questions, written by an instructor, with gold labels assigned
   lexically rather than by the embedding under test. If the benefit is real it
   shows up there too. If it was an artifact of the generator's house style, it
   will not.

Variants:
  baseline            untouched query
  content_only        P5's winner, unsafe
  content_safe        same, but negation and contrast terms are preserved

Read-only. Writes experiments/benchmarks/p11_negation_safe.json.
"""

import json
import random
import re
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from indexing.database import SessionFactory    # noqa: E402
from indexing.db_chroma import ChromaStore      # noqa: E402
from indexing.embedder import Embedder          # noqa: E402
from engine.tools import run_hybrid_search      # noqa: E402

HARD = REPO / "experiments" / "benchmarks" / "hard_eval_set.json"
NEGEVAL = REPO / "experiments" / "benchmarks" / "negation_eval.json"
INDEP = REPO / "experiments" / "benchmarks" / "independent_eval.json"
OUT = REPO / "experiments" / "benchmarks" / "p11_negation_safe.json"
TOP_K = 5
N_BOOT = 2000

# Terms whose removal changes truth conditions. Preserving these is the whole
# fix; everything else about the transform is unchanged from P5.
PRESERVE = {"not", "no", "never", "none", "neither", "nor", "cannot", "cant",
            "isnt", "arent", "doesnt", "dont", "wont", "without", "except",
            "unless", "versus", "vs", "unlike", "instead", "rather", "opposed",
            "avoid", "avoided", "fails", "fail", "incorrect", "invalid"}

FILLER = set("""
hi hello hey please thanks thank ok okay um uh so well actually basically just
really very quite kind sort bit little lot maybe perhaps sorry
i im ive id my me mine myself we our us you your
was were am are is be been being do does did doing have has had
going get got getting need want wondering wonder confused confusing stuck
help understand understanding explain tell show give know knowing figure
could would should can will shall may might must
about regarding concerning through over around
question doubt query asking ask answer
exam exams test tests quiz midterm final semester class lecture lectures
slide slides notes note chapter book textbook syllabus topic
today tomorrow yesterday now currently
""".split())

STOP = set("""what how why is are the a an of in on for to and or not does do can
which when where who explain describe define tell me about between with from
that this it its their there they be been being has have had will would should
""".split())


def rw_baseline(q):
    return q


def rw_content_only(q):
    """P5's transform, reproduced exactly - including the negation defect."""
    out = " ".join(w for w in re.findall(r"[A-Za-z0-9/+._-]+", q)
                   if w.lower() not in FILLER and w.lower() not in STOP
                   and len(w) > 1)
    return out if len(out) >= 3 else q


def rw_content_safe(q):
    """content_only, except that meaning-bearing negation survives."""
    out = " ".join(w for w in re.findall(r"[A-Za-z0-9/+._-]+", q)
                   if w.lower() in PRESERVE
                   or (w.lower() not in FILLER and w.lower() not in STOP
                       and len(w) > 1))
    return out if len(out) >= 3 else q


VARIANTS = {"baseline": rw_baseline, "content_only": rw_content_only,
            "content_safe": rw_content_safe}


# ── 1. the safety gate ───────────────────────────────────────────────────

def safety_gate():
    pairs = json.loads(NEGEVAL.read_text(encoding="utf-8"))["minimal_pairs"]
    print("=" * 74)
    print("GATE 1 - minimal-pair safety. A transform that maps an affirmative")
    print("         and its negation to the same string has destroyed meaning.")
    print("=" * 74)
    print(f"{'variant':16s} {'pairs':>7s} {'collapsed':>10s} {'rate':>8s}  verdict")
    results = {}
    for name, fn in VARIANTS.items():
        collapsed = [p for p in pairs
                     if fn(p["affirmative"]).lower() == fn(p["negated"]).lower()]
        rate = len(collapsed) / len(pairs)
        verdict = "PASS" if not collapsed else "FAIL"
        results[name] = {"collapsed": len(collapsed), "n": len(pairs),
                         "verdict": verdict}
        print(f"{name:16s} {len(pairs):>7d} {len(collapsed):>10d} {rate:>8.1%}  {verdict}")
        if collapsed and name != "baseline":
            ex = collapsed[0]
            print(f"    e.g. {ex['affirmative']!r}")
            print(f"     and {ex['negated']!r}")
            print(f"    both -> {fn(ex['affirmative'])!r}")
    return results


# ── 2. retrieval and separation ──────────────────────────────────────────

def evaluate(items, fn, embedder, chroma, session, cache):
    rows = []
    for it in items:
        q = fn(it["question"])
        key = (q, it["subject"])
        if key not in cache:
            stats = {}
            res = run_hybrid_search(q, it["subject"], session, embedder, chroma,
                                    top_k=TOP_K, stats=stats)
            cache[key] = ([r["slide_id"] for r in res], stats["dense_top1"])
        ids, dist = cache[key]
        gold = set(it.get("gold_slide_ids") or
                   ([it["gold_slide_id"]] if it.get("gold_slide_id") else []))
        rows.append({
            "id": it["id"], "category": it["category"],
            "subject": it["subject"], "answerable": it["answerable"],
            "hit_at_1": bool(gold) and bool(set(ids[:1]) & gold),
            "hit_at_5": bool(gold) and bool(set(ids) & gold),
            "dense_top1": dist,
        })
    return rows


def best_bal(rows):
    pos = [r["dense_top1"] for r in rows if r["answerable"]]
    neg = [r["dense_top1"] for r in rows if not r["answerable"]]
    if not pos or not neg:
        return None, None
    best = (-1.0, None)
    for t in sorted({r["dense_top1"] for r in rows}):
        b = (sum(1 for d in pos if d <= t) / len(pos)
             + sum(1 for d in neg if d > t) / len(neg)) / 2
        if b > best[0]:
            best = (b, t)
    return best


def bootstrap(base_rows, var_rows, seed=11):
    b = {r["id"]: r for r in base_rows}
    v = {r["id"]: r for r in var_rows}
    ids = [i for i in b if i in v]
    rng = random.Random(seed)
    diffs = []
    for _ in range(N_BOOT):
        draw = [ids[rng.randrange(len(ids))] for _ in range(len(ids))]
        bb, _ = best_bal([b[i] for i in draw])
        vv, _ = best_bal([v[i] for i in draw])
        if bb is not None and vv is not None:
            diffs.append(vv - bb)
    diffs.sort()
    if not diffs:
        return None
    return (diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))],
            sum(1 for d in diffs if d > 0) / len(diffs))


def run_set(label, items, embedder, chroma, session):
    print("\n" + "=" * 74)
    print(f"{label}  (n={len(items)}, "
          f"{sum(1 for i in items if i['answerable'])} answerable)")
    print("=" * 74)
    cache, results = {}, {}
    for name, fn in VARIANTS.items():
        results[name] = evaluate(items, fn, embedder, chroma, session, cache)

    cats = sorted({i["category"] for i in items})
    print(f"{'variant':14s} {'R@1':>6s} {'R@5':>6s} {'bal.acc':>8s} {'T':>7s}  "
          + " ".join(f"{c[:11]:>12s}" for c in cats if "negative" not in c
                     and "absent" not in c and "domain" not in c
                     and "overlap" not in c))
    for name in VARIANTS:
        rows = results[name]
        pos = [r for r in rows if r["answerable"]]
        bal, t = best_bal(rows)
        line = (f"{name:14s} {sum(r['hit_at_1'] for r in pos)/len(pos):>6.3f} "
                f"{sum(r['hit_at_5'] for r in pos)/len(pos):>6.3f} ")
        line += f"{bal:>8.3f} {t:>7.4f}  " if bal else f"{'-':>8s} {'-':>7s}  "
        for c in cats:
            if ("negative" in c or "absent" in c or "domain" in c
                    or "overlap" in c):
                continue
            grp = [r for r in rows if r["category"] == c]
            line += f"{sum(r['hit_at_1'] for r in grp)/len(grp):>12.3f}" if grp else f"{'-':>12s}"
        print(line)

    print(f"\npaired bootstrap vs baseline ({N_BOOT} resamples):")
    for name in VARIANTS:
        if name == "baseline":
            continue
        bs = bootstrap(results["baseline"], results[name])
        if not bs:
            continue
        lo, hi, p = bs
        verdict = "established" if lo > 0 else ("likely" if p >= 0.95
                                               else "not established")
        print(f"  {name:14s} d_bal.acc 95% CI [{lo:+.4f}, {hi:+.4f}]  "
              f"P(better) {p:>5.1%}  {verdict}")
    return results


def main():
    gate = safety_gate()

    hard = json.loads(HARD.read_text(encoding="utf-8"))
    negitems = json.loads(NEGEVAL.read_text(encoding="utf-8"))["retrieval_items"]
    indep = json.loads(INDEP.read_text(encoding="utf-8"))

    embedder, chroma = Embedder(), ChromaStore()
    session = SessionFactory()
    try:
        r_exp = run_set("SET A - expanded original set (250 + 40 negation)",
                        hard + negitems, embedder, chroma, session)
        r_ind = run_set("SET B - INDEPENDENT set: real PYQ exam questions, "
                        "lexical gold", indep, embedder, chroma, session)

        # Negation items deserve their own line: they are the reason the safe
        # variant exists.
        print("\n" + "=" * 74)
        print("Negation items specifically (n=40)")
        print("=" * 74)
        print(f"{'variant':14s} {'R@1':>6s} {'R@5':>6s} {'mean dense':>11s}")
        for name in VARIANTS:
            grp = [r for r in r_exp[name] if r["category"] == "positive_negation"]
            print(f"{name:14s} {sum(r['hit_at_1'] for r in grp)/len(grp):>6.3f} "
                  f"{sum(r['hit_at_5'] for r in grp)/len(grp):>6.3f} "
                  f"{statistics.mean([r['dense_top1'] for r in grp]):>11.4f}")
    finally:
        session.close()

    OUT.write_text(json.dumps(
        {"safety_gate": gate, "expanded": r_exp, "independent": r_ind},
        indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
