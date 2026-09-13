"""
Q5 — why do short queries retrieve badly, and which retriever is failing?

Q4 rejected the hypothesis that dense distance is a length artifact. Truncating
a question to two words raises its distance to 0.1946 AND drops R@1 to 0.100:
distance and recall degrade together, so the distance is honestly reporting a
real retrieval failure rather than manufacturing one.

That relocates the bottleneck. Real traffic has a median of 5 words and 35% of
it is three words or fewer, which is the regime where R@1 is 0.10-0.20. Short-
query retrieval, not confidence estimation, is where this system loses.

Two questions:

1. WHICH RETRIEVER FAILS? A one-word acronym query like "TCP" or "irq" is the
   best possible case for BM25 - an exact, high-IDF token match - and close to
   the worst for a dense encoder, since e5 embeds "query: TCP" where the
   prefix is most of the input. If sparse does well and fused does badly, RRF
   is diluting a good sparse result with a bad dense one, and the fusion is the
   problem rather than either retriever.

2. WHY DID THE EVAL SET SHOW THE OPPOSITE? positive_verbose (padded) had a
   LOWER mean distance than plain positives, but Q4's neutral padding raised
   distance. The difference is probably that make_verbose's filler ("going
   through the slides for my exam...") contains corpus vocabulary - slide, exam,
   understand - so it was not neutral at all. Testable directly.

READ-ONLY.
"""

import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from indexing.database import SessionFactory        # noqa: E402
from indexing.db_chroma import ChromaStore          # noqa: E402
from indexing.embedder import Embedder              # noqa: E402
from engine.tools import (run_hybrid_search, _get_bm25_index,  # noqa: E402
                          _tokenize, _parse_chroma_id)

EVAL = REPO / "eval" / "eval_set.json"
OUT = REPO / "experiments" / "benchmarks" / "q5_short_query.json"

VERBOSE_FILLER_PRE = ("hi, i was going through the slides for my exam and i got "
                      "a bit confused, could you please help me understand this: ")
VERBOSE_FILLER_POST = " thanks a lot"
NEUTRAL = (" I was sitting by the window earlier today thinking about this. "
           "The weather has been quite pleasant and calm all of this week.")


def dense_only(q, subject, embedder, chroma, session, top_k=5):
    """Rank by dense distance alone, mirroring run_hybrid_search's fetch."""
    vec = embedder.embed_query(q)
    try:
        raw = chroma.query(query_embedding=vec, n_results=top_k * 3,
                           where={"subject": subject})
    except Exception:
        raw = chroma.query(query_embedding=vec, n_results=top_k * 3)
    from indexing.models import Slide
    out = []
    if raw and raw.get("ids") and raw["ids"][0]:
        for cid in raw["ids"][0]:
            doc_id, page = _parse_chroma_id(cid)
            sl = (session.query(Slide)
                  .filter(Slide.doc_id == doc_id, Slide.page_number == page)
                  .first())
            if sl:
                out.append(sl.id)
    return out[:top_k]


def sparse_only(q, subject, session, top_k=5):
    bm25, corpus = _get_bm25_index(session, subject)
    if bm25 is None:
        return []
    toks = _tokenize(q)
    if not toks:
        return []
    scores = bm25.get_scores(toks)
    ranked = sorted(((i, scores[i]) for i in range(len(scores)) if scores[i] > 0),
                    key=lambda x: -x[1])
    return [corpus[i].id for i, _ in ranked[:top_k]]


def main():
    eval_set = json.loads(EVAL.read_text(encoding="utf-8"))[:25]
    embedder, chroma = Embedder(), ChromaStore()
    session = SessionFactory()
    results = {}

    try:
        # ── 1. which retriever fails as queries shorten ──────────────────
        print("=" * 82)
        print("1. R@1 / R@5 BY RETRIEVER, as the same questions are truncated")
        print("=" * 82)
        print(f"{'query length':>14s} | {'dense only':>17s} | {'sparse only':>17s} "
              f"| {'RRF fused':>17s}")
        print(f"{'':>14s} | {'R@1':>8s}{'R@5':>9s} | {'R@1':>8s}{'R@5':>9s} "
              f"| {'R@1':>8s}{'R@5':>9s}")
        print("-" * 82)
        for k in (1, 2, 3, 5, 8, 999):
            d1 = d5 = s1 = s5 = f1 = f5 = 0
            n = 0
            for qa in eval_set:
                q = " ".join(qa["question"].split()[:k])
                if not q.strip():
                    continue
                gold = qa["gold_slide_id"]
                n += 1
                di = dense_only(q, qa["subject"], embedder, chroma, session)
                si = sparse_only(q, qa["subject"], session)
                fi = [r["slide_id"] for r in run_hybrid_search(
                    q, qa["subject"], session, embedder, chroma, top_k=5)]
                d1 += di[:1] == [gold]; d5 += gold in di
                s1 += si[:1] == [gold]; s5 += gold in si
                f1 += fi[:1] == [gold]; f5 += gold in fi
            label = "full" if k == 999 else f"{k} words"
            results[label] = {"dense_r1": d1/n, "dense_r5": d5/n,
                              "sparse_r1": s1/n, "sparse_r5": s5/n,
                              "fused_r1": f1/n, "fused_r5": f5/n, "n": n}
            print(f"{label:>14s} | {d1/n:>8.3f}{d5/n:>9.3f} | "
                  f"{s1/n:>8.3f}{s5/n:>9.3f} | {f1/n:>8.3f}{f5/n:>9.3f}")

        # ── 2. acronym-only queries, the real-traffic worst case ─────────
        print("\n" + "=" * 82)
        print("2. REAL acronym queries from query_cache - per retriever")
        print("=" * 82)
        probes = [("TCP", "CN"), ("SMTP", "CN"), ("irq", "CA"), ("FIQ", "CA"),
                  ("Waterfall model", "SE"), ("is DFDs covered", "SE"),
                  ("linear regression", "CA"), ("kaju katli", "ML")]
        print(f"{'query':22s} {'subj':5s} {'dense top1 id':>14s} {'sparse top1 id':>15s} "
              f"{'fused top1 id':>14s} {'agree':>6s}")
        for q, subj in probes:
            di = dense_only(q, subj, embedder, chroma, session)
            si = sparse_only(q, subj, session)
            fi = [r["slide_id"] for r in run_hybrid_search(
                q, subj, session, embedder, chroma, top_k=5)]
            agree = "yes" if (di[:1] and si[:1] and di[0] == si[0]) else "no"
            print(f"{q[:22]:22s} {subj[:5]:5s} {str(di[:1]):>14s} "
                  f"{str(si[:1]):>15s} {str(fi[:1]):>14s} {agree:>6s}")

        # ── 3. was make_verbose's filler actually neutral? ───────────────
        print("\n" + "=" * 82)
        print("3. WHY THE EVAL SET DISAGREED - is the verbose filler neutral?")
        print("=" * 82)
        variants = {
            "plain question": lambda q: q,
            "+ make_verbose filler": lambda q: VERBOSE_FILLER_PRE + q + VERBOSE_FILLER_POST,
            "+ neutral filler (same length)": lambda q: q + NEUTRAL,
        }
        print(f"{'variant':34s} {'words':>6s} {'mean dense':>11s} {'R@1':>6s}")
        for name, fn in variants.items():
            dists, hits, wc = [], 0, []
            for qa in eval_set:
                q = fn(qa["question"])
                stats = {}
                res = run_hybrid_search(q, qa["subject"], session, embedder,
                                        chroma, top_k=5, stats=stats)
                dists.append(stats["dense_top1"])
                hits += [r["slide_id"] for r in res][:1] == [qa["gold_slide_id"]]
                wc.append(len(q.split()))
            print(f"{name:34s} {statistics.mean(wc):>6.0f} "
                  f"{statistics.mean(dists):>11.4f} {hits/len(eval_set):>6.3f}")

        # How much corpus vocabulary does each filler contain?
        from indexing.models import Slide
        corpus_terms = set()
        for sl in session.query(Slide).filter(Slide.is_embedded == True).all():  # noqa: E712
            corpus_terms |= set(_tokenize(f"{sl.summary or ''} {sl.raw_text or ''}"))
        for name, text in (("make_verbose filler",
                            VERBOSE_FILLER_PRE + VERBOSE_FILLER_POST),
                           ("neutral filler", NEUTRAL)):
            toks = [t for t in _tokenize(text) if len(t) > 2]
            hit = [t for t in toks if t in corpus_terms]
            print(f"\n  {name:22s}: {len(hit)}/{len(toks)} tokens "
                  f"({len(hit)/len(toks):.0%}) also occur in the corpus")
            print(f"    overlapping: {sorted(set(hit))[:12]}")
    finally:
        session.close()

    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
