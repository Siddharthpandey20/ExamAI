"""
Q2 — prove the observability wiring changed nothing, on real data.

The unit tests establish this against stubs. This establishes it against the
actual corpus, which is where a subtle difference would actually show up:

1. replay all 290 expanded evaluation items with observation ENABLED and diff
   the retrieved slide ids against the rows recorded before the module existed
2. measure the latency cost of the append, on vs off, on the same queries
3. confirm the log contains no query text, slide text or filename

The latency question matters more than it looks. Retrieval p50 is ~90 ms and
~70 ms of that is the query embedding, so there is little headroom; an append
that cost even a few milliseconds per search would be a real tax for data the
project can also obtain by other means.

READ-ONLY with respect to the corpus. Writes only to a temporary log path.
"""

import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

HARD = REPO / "experiments" / "benchmarks" / "hard_eval_set.json"
NEG = REPO / "experiments" / "benchmarks" / "negation_eval.json"
PRIOR = REPO / "experiments" / "benchmarks" / "expanded_features.json"
TOP_K = 5


def main():
    tmpdir = tempfile.mkdtemp(prefix="examai_obs_")
    logpath = Path(tmpdir) / "obs.jsonl"
    os.environ["EXAMAI_OBSERVE_PATH"] = str(logpath)
    os.environ["EXAMAI_OBSERVE_RETRIEVAL"] = "1"
    os.environ.pop("EXAMAI_OBSERVE_QUERY_TEXT", None)

    from indexing.database import SessionFactory      # noqa: E402
    from indexing.db_chroma import ChromaStore        # noqa: E402
    from indexing.embedder import Embedder            # noqa: E402
    from engine.tools import run_hybrid_search        # noqa: E402
    from engine.observability import observe          # noqa: E402

    items = (json.loads(HARD.read_text(encoding="utf-8"))
             + json.loads(NEG.read_text(encoding="utf-8"))["retrieval_items"])
    embedder, chroma = Embedder(), ChromaStore()
    session = SessionFactory()

    print(f"replaying {len(items)} items with observation ENABLED\n")
    now = {}
    try:
        for it in items:
            with observe("replay", it["subject"], it["question"]) as obs:
                res = run_hybrid_search(it["question"], it["subject"], session,
                                        embedder, chroma, top_k=TOP_K,
                                        stats=obs.stats)
                obs.done(res, answered=bool(res))
            now[it["id"]] = [r["slide_id"] for r in res]

        # ── 1. retrieval identity ────────────────────────────────────────
        prior = {r["id"]: r for r in json.loads(PRIOR.read_text(encoding="utf-8"))}
        shared = [i for i in prior if i in now]
        diff = [i for i in shared if prior[i]["retrieved"] != now[i]]
        print("=" * 70)
        print("1. RETRIEVAL IDENTITY")
        print("=" * 70)
        print(f"items compared           : {len(shared)}")
        print(f"retrieved-id differences : {len(diff)}")
        print("PASS - identical" if not diff else f"FAIL - {diff[:5]}")

        # ── 2. latency cost ──────────────────────────────────────────────
        print("\n" + "=" * 70)
        print("2. LATENCY COST OF THE APPEND")
        print("=" * 70)
        sample = [it for it in items if it["category"] == "positive"][:30]
        for it in sample[:5]:               # warm
            run_hybrid_search(it["question"], it["subject"], session, embedder,
                              chroma, top_k=TOP_K)

        off, on = [], []
        for it in sample:
            os.environ["EXAMAI_OBSERVE_RETRIEVAL"] = "0"
            t0 = time.perf_counter()
            run_hybrid_search(it["question"], it["subject"], session, embedder,
                              chroma, top_k=TOP_K)
            off.append((time.perf_counter() - t0) * 1000)

            os.environ["EXAMAI_OBSERVE_RETRIEVAL"] = "1"
            t0 = time.perf_counter()
            with observe("bench", it["subject"], it["question"]) as obs:
                r = run_hybrid_search(it["question"], it["subject"], session,
                                      embedder, chroma, top_k=TOP_K,
                                      stats=obs.stats)
                obs.done(r, answered=True)
            on.append((time.perf_counter() - t0) * 1000)

        # Isolate the append alone, away from retrieval noise.
        from engine.observability import record_retrieval
        appends = []
        for _ in range(200):
            t0 = time.perf_counter()
            record_retrieval(endpoint="bench", subject="CN", query="x" * 40,
                             stats={"dense_top1": 0.1}, results=[])
            appends.append((time.perf_counter() - t0) * 1000)

        for name, v in (("retrieval, observation off", off),
                        ("retrieval, observation on", on)):
            v = sorted(v)
            print(f"  {name:30s} p50 {statistics.median(v):7.2f} ms   "
                  f"p95 {v[int(len(v)*0.95)]:7.2f} ms")
        a = sorted(appends)
        print(f"  {'the append alone':30s} p50 {statistics.median(a):7.3f} ms   "
              f"p95 {a[int(len(a)*0.95)]:7.3f} ms")
        share = statistics.median(a) / statistics.median(on) * 100
        print(f"\n  append is {share:.2f}% of a retrieval "
              f"({statistics.median(a):.3f} ms of "
              f"{statistics.median(on):.1f} ms)")

        # ── 3. privacy ───────────────────────────────────────────────────
        print("\n" + "=" * 70)
        print("3. WHAT ACTUALLY LANDED IN THE LOG")
        print("=" * 70)
        blob = logpath.read_text(encoding="utf-8")
        rows = [json.loads(l) for l in blob.splitlines() if l]
        print(f"observations written : {len(rows)}")
        leaks = []
        for it in items[:60]:
            q = it["question"]
            if len(q) > 12 and q in blob:
                leaks.append(q)
        print(f"raw query text found : {len(leaks)}")
        for probe, label in ((".pdf", "filenames"), (".md", "filenames"),
                             ("substantive", "slide text")):
            print(f"  {label:12s} ({probe:12s}) present: {probe in blob}")
        print(f"\nfields recorded: {sorted(rows[0])}")
        print(f"\nexample row:\n{json.dumps(rows[0], indent=2)}")
    finally:
        session.close()
        os.environ["EXAMAI_OBSERVE_RETRIEVAL"] = "0"


if __name__ == "__main__":
    main()
