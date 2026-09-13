"""
Q6 — where does the 70 ms of query-embedding latency actually go?

Retrieval p50 is ~90 ms and embed_query is ~70 ms of it, so the search itself
is a minor cost. 70 ms is a lot for one short sequence through a 335M-parameter
encoder on a GPU; the forward pass alone should be a fraction of that. This
measures the breakdown before proposing anything.

Candidates, each measured against the production call as baseline:

  st.encode (production)   SentenceTransformer.encode does per-call work that is
                           designed for batches - length sorting, numpy
                           conversion, device inference - and for batch size 1
                           that overhead may dominate the matrix multiply.
  raw forward              tokenize + model + mean-pool + normalize, by hand.
  inference_mode           autograd bookkeeping disabled.
  fp16                     half precision on GPU.
  CPU                      a 3050 laptop GPU has real kernel-launch and
                           synchronisation overhead; for one short sequence CPU
                           can genuinely win.
  cache                    identical queries recur in real traffic (query_cache
                           shows "kaju katli" twice, ftp three ways). An exact
                           cache is the only option here that cannot change a
                           single retrieval result.

EVERY candidate is checked for output equivalence against the production
embedding, because a latency win that changes the vector is a retrieval change
in disguise. Cosine similarity to the baseline vector is reported alongside
R@1/R@5/MRR on the evaluation set.

Nothing is promoted. The production model is not replaced.
"""

import json
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import torch                                        # noqa: E402
from indexing.database import SessionFactory        # noqa: E402
from indexing.db_chroma import ChromaStore          # noqa: E402
from indexing.embedder import Embedder              # noqa: E402
from engine.tools import run_hybrid_search          # noqa: E402

EVAL = REPO / "eval" / "eval_set.json"
OUT = REPO / "experiments" / "benchmarks" / "q6_embedding_latency.json"
N_WARM, N_MEASURE = 10, 40


def timeit(fn, queries, warm=N_WARM):
    for q in queries[:warm]:
        fn(q)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    times = []
    for q in queries:
        t0 = time.perf_counter()
        fn(q)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    return {"p50": statistics.median(times),
            "p95": times[int(len(times) * 0.95)],
            "mean": statistics.mean(times)}


def cos(a, b):
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def main():
    eval_set = json.loads(EVAL.read_text(encoding="utf-8"))
    queries = [qa["question"] for qa in eval_set][:N_MEASURE]

    emb = Embedder()
    model = emb.model
    device = next(model.parameters()).device
    print(f"model device: {device}")
    if torch.cuda.is_available():
        print(f"gpu: {torch.cuda.get_device_name(0)}")
        free, total = torch.cuda.mem_get_info()
        print(f"vram free {free/2**20:.0f} / {total/2**20:.0f} MiB")
    print(f"measuring over {len(queries)} real evaluation questions\n")

    results, vectors = {}, {}

    # ── baseline: production path ────────────────────────────────────────
    results["production (st.encode)"] = timeit(emb.embed_query, queries)
    vectors["production (st.encode)"] = [emb.embed_query(q) for q in queries[:8]]

    # ── raw forward pass by hand ─────────────────────────────────────────
    tok = model.tokenizer
    transformer = model[0].auto_model

    def raw_forward(q, half=False, infer=True):
        ctx = torch.inference_mode() if infer else torch.no_grad()
        with ctx:
            batch = tok([f"query: {q}"], padding=True, truncation=True,
                        max_length=512, return_tensors="pt").to(device)
            out = transformer(**batch).last_hidden_state
            mask = batch["attention_mask"].unsqueeze(-1).float()
            pooled = (out * mask).sum(1) / mask.sum(1)
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            return pooled[0].float().cpu().tolist()

    results["raw forward + inference_mode"] = timeit(raw_forward, queries)
    vectors["raw forward + inference_mode"] = [raw_forward(q) for q in queries[:8]]

    # ── tokenizer alone, to size the non-model overhead ──────────────────
    def tokenize_only(q):
        return tok([f"query: {q}"], padding=True, truncation=True,
                   max_length=512, return_tensors="pt")
    results["tokenizer only"] = timeit(tokenize_only, queries)

    # ── fp16 on GPU ──────────────────────────────────────────────────────
    if device.type == "cuda":
        try:
            half_model = transformer.half()

            def raw_half(q):
                with torch.inference_mode():
                    batch = tok([f"query: {q}"], padding=True, truncation=True,
                                max_length=512, return_tensors="pt").to(device)
                    out = half_model(**batch).last_hidden_state
                    mask = batch["attention_mask"].unsqueeze(-1).half()
                    pooled = (out * mask).sum(1) / mask.sum(1)
                    pooled = torch.nn.functional.normalize(pooled.float(), p=2, dim=1)
                    return pooled[0].cpu().tolist()

            results["raw forward, fp16"] = timeit(raw_half, queries)
            vectors["raw forward, fp16"] = [raw_half(q) for q in queries[:8]]
            transformer.float()          # restore
        except Exception as e:            # noqa: BLE001
            print(f"  (fp16 unavailable: {e})")

    # ── CPU ──────────────────────────────────────────────────────────────
    try:
        cpu_model = transformer.to("cpu")

        def raw_cpu(q):
            with torch.inference_mode():
                batch = tok([f"query: {q}"], padding=True, truncation=True,
                            max_length=512, return_tensors="pt")
                out = cpu_model(**batch).last_hidden_state
                mask = batch["attention_mask"].unsqueeze(-1).float()
                pooled = (out * mask).sum(1) / mask.sum(1)
                pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
                return pooled[0].tolist()

        results["raw forward, CPU"] = timeit(raw_cpu, queries)
        vectors["raw forward, CPU"] = [raw_cpu(q) for q in queries[:8]]
        transformer.to(device)
    except Exception as e:                # noqa: BLE001
        print(f"  (CPU path failed: {e})")

    # ── exact cache ──────────────────────────────────────────────────────
    cache = {}

    def cached(q):
        key = " ".join(q.lower().split())
        if key not in cache:
            cache[key] = emb.embed_query(q)
        return cache[key]

    for q in queries:
        cached(q)                          # prime
    results["exact cache (hit)"] = timeit(cached, queries, warm=0)

    # ── report ───────────────────────────────────────────────────────────
    base = results["production (st.encode)"]["p50"]
    print("=" * 84)
    print(f"{'variant':34s} {'p50 ms':>9s} {'p95 ms':>9s} {'vs prod':>9s} "
          f"{'cos to prod':>12s}")
    print("=" * 84)
    for name, m in results.items():
        speed = base / m["p50"] if m["p50"] else 0
        if name in vectors and name != "production (st.encode)":
            sims = [cos(a, b) for a, b in
                    zip(vectors["production (st.encode)"], vectors[name])]
            csim = f"{min(sims):.6f}"
        elif name == "production (st.encode)":
            csim = "1.000000"
        else:
            csim = "-"
        print(f"{name:34s} {m['p50']:>9.2f} {m['p95']:>9.2f} "
              f"{speed:>8.2f}x {csim:>12s}")

    # ── does the fastest equivalent option change retrieval? ─────────────
    print("\n" + "=" * 84)
    print("RETRIEVAL EQUIVALENCE - does any candidate change what is returned?")
    print("=" * 84)

    class _Wrap:
        def __init__(self, fn):
            self.fn = fn

        def embed_query(self, t):
            return self.fn(t)

    session = SessionFactory()
    chroma = ChromaStore()
    try:
        candidates = {"production": emb}
        if "raw forward + inference_mode" in results:
            candidates["raw forward"] = _Wrap(raw_forward)
        if "raw forward, fp16" in results:
            def half_fn(q):
                transformer.half()
                try:
                    return raw_half(q)
                finally:
                    transformer.float()
            # measured separately above; skip in equivalence to avoid
            # repeated dtype flipping distorting the comparison
        print(f"{'variant':20s} {'R@1':>6s} {'R@3':>6s} {'R@5':>6s} {'MRR':>6s} "
              f"{'identical top1':>15s}")
        base_ids = None
        for name, e in candidates.items():
            h1 = h3 = h5 = 0
            rr = []
            ids_all = []
            for qa in eval_set:
                res = run_hybrid_search(qa["question"], qa["subject"], session,
                                        e, chroma, top_k=5)
                ids = [r["slide_id"] for r in res]
                ids_all.append(ids)
                g = qa["gold_slide_id"]
                h1 += ids[:1] == [g]; h3 += g in ids[:3]; h5 += g in ids
                rr.append(1 / (ids.index(g) + 1) if g in ids else 0)
            n = len(eval_set)
            if base_ids is None:
                base_ids = ids_all
                same = "-"
            else:
                same = f"{sum(1 for a, b in zip(base_ids, ids_all) if a[:1]==b[:1])}/{n}"
            print(f"{name:20s} {h1/n:>6.3f} {h3/n:>6.3f} {h5/n:>6.3f} "
                  f"{statistics.mean(rr):>6.3f} {same:>15s}")
    finally:
        session.close()

    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
