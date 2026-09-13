"""
Phase 5 — does cheap deterministic query rewriting recover the recall lost to
phrasing?

Phase 2 measured a large phrasing penalty on R@1:
    positive 0.725 | noisy 0.650 | keyword 0.575 | verbose 0.525
and Phase 3 showed the cost lands on keyword queries: 25% of them get falsely
refused by a distance threshold that is otherwise well behaved.

CIRCULARITY WARNING — read before trusting the verbose numbers.
The verbose queries in the eval set were built by prepending a fixed template
("hi, i was going through the slides ... thanks a lot"). A rewriter that deleted
exactly that template would score brilliantly and mean nothing. So:
  - the filler list here is generic conversational vocabulary, written without
    consulting the template, and contains no multi-word phrase from it;
  - every variant is scored on ALL FOUR phrasings, including plain positives,
    where a good rewriter must be close to a no-op;
  - the honest reading is that *keyword* gains are real evidence and *verbose*
    gains are partly construction. Both are reported, separately.

A rewrite must also be checked against the NEGATIVES. Pulling every query closer
to the corpus would "improve" recall while destroying the abstention signal, so
class separation is reported alongside recall.

Read-only. Writes experiments/benchmarks/p5_rewriting.json.
"""

import json
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

IN = REPO / "experiments" / "benchmarks" / "hard_eval_set.json"
OUT = REPO / "experiments" / "benchmarks" / "p5_rewriting.json"
RAW = REPO / "experiments" / "benchmarks" / "p5_rewriting_rows.json"
TOP_K = 5

POSITIVE_CATS = ("positive", "positive_noisy", "positive_keyword", "positive_verbose")
NEGATIVE_CATS = ("in_subject_absent", "cross_subject_overlap", "out_of_domain")

# Generic conversational filler. Single words only, chosen as the vocabulary of
# politeness and self-narration rather than of subject matter.
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

# Interrogatives are kept: they are not filler, they signal question shape.
WH = {"what", "why", "how", "when", "where", "which", "who", "whose", "whom"}

STOP = set("""what how why is are the a an of in on for to and or not does do can
which when where who explain describe define tell me about between with from
that this it its their there they be been being has have had will would should
""".split())


def content_words(q):
    """Words that carry subject meaning: not filler, not a pure stopword."""
    return [w for w in re.findall(r"[A-Za-z0-9/+._-]+", q)
            if w.lower() not in FILLER and w.lower() not in STOP and len(w) > 1]


# ── rewrite variants ─────────────────────────────────────────────────────

def rw_baseline(q):
    return q


def rw_strip_filler(q):
    """Drop conversational filler, keep interrogatives and structure."""
    kept = [w for w in re.findall(r"[A-Za-z0-9/+._-]+", q)
            if w.lower() in WH or w.lower() not in FILLER]
    out = " ".join(kept).strip()
    return out if len(out) >= 3 else q


def rw_content_only(q):
    """Reduce to bare content terms - the most aggressive normalisation."""
    out = " ".join(content_words(q))
    return out if len(out) >= 3 else q


def rw_template(q):
    """Give a terse keyword query the shape of a question.

    e5 was trained on natural-language query/passage pairs; a bare noun pile is
    off-distribution for it. This only fires on short queries that do not
    already look like a question, so it is a no-op on normal input.
    """
    words = re.findall(r"[A-Za-z0-9/+._-]+", q)
    lowered = {w.lower() for w in words}
    if len(words) <= 7 and not (lowered & WH) and "?" not in q:
        return f"What is {q.strip().rstrip('?')}, and how does it work?"
    return q


def rw_strip_then_template(q):
    return rw_template(rw_strip_filler(q))


VARIANTS = {
    "baseline": rw_baseline,
    "strip_filler": rw_strip_filler,
    "content_only": rw_content_only,
    "template": rw_template,
    "strip+template": rw_strip_then_template,
}


def evaluate(items, variant_name, fn, embedder, chroma, session, cache):
    rows = []
    for it in items:
        q = fn(it["question"])
        key = (q, it["subject"])
        if key in cache:
            ids, dist = cache[key]
        else:
            vec = embedder.embed_query(q)
            try:
                dres = chroma.query(query_embedding=vec, n_results=TOP_K,
                                    where={"subject": it["subject"]})
            except Exception:
                dres = chroma.query(query_embedding=vec, n_results=TOP_K)
            dl = (dres.get("distances") or [[]])[0]
            dist = dl[0] if dl else None
            res = run_hybrid_search(q, it["subject"], session, embedder, chroma,
                                    top_k=TOP_K)
            ids = [r["slide_id"] for r in res]
            cache[key] = (ids, dist)

        gold = it.get("gold_slide_id")
        rows.append({
            "id": it["id"], "category": it["category"],
            "answerable": it["answerable"], "rewritten": q,
            "changed": q != it["question"],
            "hit_at_1": bool(gold) and ids[:1] == [gold],
            "hit_at_3": bool(gold) and gold in ids[:3],
            "hit_at_5": bool(gold) and gold in ids,
            "rank_of_gold": (ids.index(gold) + 1) if gold and gold in ids else None,
            "dense_top1": dist,
        })
    return rows


def recall_table(rows, cats):
    out = {}
    for cat in cats:
        grp = [r for r in rows if r["category"] == cat]
        if not grp:
            continue
        n = len(grp)
        out[cat] = {
            "n": n,
            "r1": sum(r["hit_at_1"] for r in grp) / n,
            "r3": sum(r["hit_at_3"] for r in grp) / n,
            "r5": sum(r["hit_at_5"] for r in grp) / n,
            "mrr": sum(1 / r["rank_of_gold"] if r["rank_of_gold"] else 0
                       for r in grp) / n,
            "changed": sum(r["changed"] for r in grp) / n,
            "dense": statistics.mean([r["dense_top1"] for r in grp
                                      if r["dense_top1"] is not None]),
        }
    return out


def best_balanced(rows):
    """Best achievable abstention on this variant, in-sample upper bound.

    In-sample deliberately: the question is whether a rewrite preserves the
    SEPARATION at all, and an optimistic bound answers that. It is not a
    performance claim and is not comparable to the cross-validated P3 number.
    """
    vals = [(r["dense_top1"], r["answerable"]) for r in rows
            if r["dense_top1"] is not None]
    pos = [v for v, a in vals if a]
    neg = [v for v, a in vals if not a]
    if not pos or not neg:
        return None, None
    best = (-1, None)
    for t in sorted({v for v, _ in vals}):
        rec = sum(1 for v in pos if v <= t) / len(pos)
        spec = sum(1 for v in neg if v > t) / len(neg)
        if (rec + spec) / 2 > best[0]:
            best = ((rec + spec) / 2, t)
    return best


def main():
    items = json.loads(IN.read_text(encoding="utf-8"))
    embedder, chroma = Embedder(), ChromaStore()
    session = SessionFactory()
    cache, results = {}, {}

    try:
        for name, fn in VARIANTS.items():
            print(f"  running {name} ...", flush=True)
            results[name] = evaluate(items, name, fn, embedder, chroma,
                                     session, cache)
    finally:
        session.close()

    # ── recall on the answerable half ────────────────────────────────────
    print("\nR@1 by phrasing (the number Phase 3 cares about)\n")
    hdr = f"{'variant':16s}" + "".join(f"{c.replace('positive','pos'):>16s}"
                                       for c in POSITIVE_CATS) + f"{'ALL':>8s}"
    print(hdr)
    print("-" * len(hdr))
    base_tab = recall_table(results["baseline"], POSITIVE_CATS)
    for name in VARIANTS:
        tab = recall_table(results[name], POSITIVE_CATS)
        line = f"{name:16s}"
        for c in POSITIVE_CATS:
            d = tab[c]["r1"] - base_tab[c]["r1"]
            line += f"{tab[c]['r1']:>10.3f}{d:+6.3f}" if name != "baseline" \
                else f"{tab[c]['r1']:>16.3f}"
        allr = [r for r in results[name] if r["category"] in POSITIVE_CATS]
        line += f"{sum(r['hit_at_1'] for r in allr)/len(allr):>8.3f}"
        print(line)

    print("\nMRR by phrasing\n")
    print(hdr)
    print("-" * len(hdr))
    for name in VARIANTS:
        tab = recall_table(results[name], POSITIVE_CATS)
        line = f"{name:16s}"
        for c in POSITIVE_CATS:
            d = tab[c]["mrr"] - base_tab[c]["mrr"]
            line += f"{tab[c]['mrr']:>10.3f}{d:+6.3f}" if name != "baseline" \
                else f"{tab[c]['mrr']:>16.3f}"
        allr = [r for r in results[name] if r["category"] in POSITIVE_CATS]
        mrr = sum(1 / r["rank_of_gold"] if r["rank_of_gold"] else 0
                  for r in allr) / len(allr)
        line += f"{mrr:>8.3f}"
        print(line)

    # ── how often each variant actually fires ────────────────────────────
    print("\nfraction of queries the rewrite actually changed\n")
    print(f"{'variant':16s}" + "".join(f"{c.replace('positive','pos'):>18s}"
                                       for c in POSITIVE_CATS))
    for name in VARIANTS:
        tab = recall_table(results[name], POSITIVE_CATS)
        print(f"{name:16s}" + "".join(f"{tab[c]['changed']:>17.0%} "
                                      for c in POSITIVE_CATS))

    # ── the check that matters: does it wreck abstention? ────────────────
    print("\nseparation check - mean dense_top1 per class, and the best")
    print("balanced accuracy still achievable (in-sample upper bound)\n")
    cats = POSITIVE_CATS + NEGATIVE_CATS
    print(f"{'variant':16s}" + "".join(f"{c[:13]:>14s}" for c in cats)
          + f"{'bal.acc':>9s}{'T':>8s}")
    for name in VARIANTS:
        tab = recall_table(results[name], cats)
        line = f"{name:16s}"
        for c in cats:
            line += f"{tab[c]['dense']:>14.4f}" if c in tab else f"{'-':>14s}"
        bal, t = best_balanced(results[name])
        line += f"{bal:>9.3f}{t:>8.4f}" if bal else f"{'-':>9s}{'-':>8s}"
        print(line)

    OUT.write_text(json.dumps(
        {n: recall_table(r, cats) for n, r in results.items()}, indent=2),
        encoding="utf-8")
    RAW.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}\nsaved -> {RAW}")


if __name__ == "__main__":
    main()
