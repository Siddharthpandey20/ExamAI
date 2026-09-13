"""
Q7 — can a shallower embedding model buy back the latency without costing
retrieval quality?

Q6 established that query embedding is LAUNCH-BOUND, not compute-bound:
sequence length does not matter (4 tokens 50.9 ms, 128 tokens 51.4 ms), batch
16 is faster in total than batch 1, and fp16 gives nothing. The cost is 24
sequential transformer layers dispatched one at a time on a laptop GPU.

If that diagnosis is right, latency should scale with LAYER COUNT rather than
parameter count or precision, and a 6- or 12-layer model should be roughly
4x or 2x faster. This measures whether the retrieval quality survives.

Method: embed the whole corpus and the whole evaluation set with each model in
memory and rank by cosine similarity. PRODUCTION CHROMA IS NEVER TOUCHED - no
collection is created, written or deleted. e5-large is re-measured through the
same in-memory path so the comparison is like-for-like; this is DENSE-ONLY
retrieval, so the absolute numbers are not comparable to the hybrid R@1
reported elsewhere.

The production model is not replaced. This is evidence for a future decision.
"""

import json
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import torch                                       # noqa: E402
from sentence_transformers import SentenceTransformer   # noqa: E402
from indexing.database import SessionFactory       # noqa: E402
from indexing.models import Slide                  # noqa: E402

EVAL = REPO / "eval" / "eval_set.json"
OUT = REPO / "experiments" / "benchmarks" / "q7_embedding_models.json"

# (name, query prefix, passage prefix). e5 requires its prefixes; MiniLM has none.
CANDIDATES = [
    ("intfloat/e5-large-v2", "query: ", "passage: "),
    ("intfloat/e5-base-v2", "query: ", "passage: "),
    ("sentence-transformers/all-MiniLM-L6-v2", "", ""),
]


def build_embed_text(summary, concepts, raw_text):
    parts = [p.strip() for p in (summary, concepts, raw_text) if p and p.strip()]
    return " | ".join(parts)[:2000]


def main():
    session = SessionFactory()
    try:
        slides = (session.query(Slide)
                  .filter(Slide.is_embedded == True).all())  # noqa: E712
        corpus = [(s.id, s.subject,
                   build_embed_text(s.summary, s.concepts, s.raw_text))
                  for s in slides]
    finally:
        session.close()

    eval_set = json.loads(EVAL.read_text(encoding="utf-8"))
    print(f"corpus {len(corpus)} slides, eval {len(eval_set)} questions")
    print("in-memory cosine ranking; production Chroma is not touched\n")

    results = {}
    for name, qpref, ppref in CANDIDATES:
        print(f"--- {name}")
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                free0, _ = torch.cuda.mem_get_info()
            t0 = time.perf_counter()
            m = SentenceTransformer(name)
            load_s = time.perf_counter() - t0
        except Exception as e:                      # noqa: BLE001
            print(f"    unavailable ({type(e).__name__}: {str(e)[:90]}); skipped\n")
            continue

        dev = next(m.parameters()).device
        layers = m[0].auto_model.config.num_hidden_layers
        dim = m.get_sentence_embedding_dimension()
        params = sum(p.numel() for p in m[0].auto_model.parameters()) / 1e6

        # corpus embedding (one-off ingestion cost)
        t0 = time.perf_counter()
        cvecs = m.encode([ppref + t for _, _, t in corpus], batch_size=32,
                         normalize_embeddings=True, show_progress_bar=False,
                         convert_to_tensor=True)
        corpus_s = time.perf_counter() - t0

        # single-query latency, the number that matters at request time
        qs = [qa["question"] for qa in eval_set]
        for q in qs[:8]:
            m.encode([qpref + q], normalize_embeddings=True,
                     show_progress_bar=False)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        lat = []
        for q in qs:
            t0 = time.perf_counter()
            m.encode([qpref + q], normalize_embeddings=True,
                     show_progress_bar=False)
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            lat.append((time.perf_counter() - t0) * 1000)
        lat.sort()

        if torch.cuda.is_available():
            free1, _ = torch.cuda.mem_get_info()
            vram = (free0 - free1) / 2 ** 20
        else:
            vram = float("nan")

        # retrieval quality, subject-filtered like production
        qvecs = m.encode([qpref + q for q in qs], batch_size=32,
                         normalize_embeddings=True, show_progress_bar=False,
                         convert_to_tensor=True)
        h1 = h3 = h5 = 0
        rr = []
        for i, qa in enumerate(eval_set):
            mask = [j for j, (_, subj, _) in enumerate(corpus)
                    if subj == qa["subject"]]
            if not mask:
                rr.append(0.0)
                continue
            sub = cvecs[mask]
            sims = (sub @ qvecs[i]).tolist()
            order = sorted(range(len(mask)), key=lambda k: -sims[k])[:5]
            ids = [corpus[mask[k]][0] for k in order]
            g = qa["gold_slide_id"]
            h1 += ids[:1] == [g]
            h3 += g in ids[:3]
            h5 += g in ids
            rr.append(1 / (ids.index(g) + 1) if g in ids else 0.0)

        n = len(eval_set)
        results[name] = {
            "layers": layers, "dim": dim, "params_m": round(params),
            "device": str(dev), "load_s": round(load_s, 1),
            "corpus_embed_s": round(corpus_s, 1), "vram_mib": round(vram),
            "q_p50_ms": round(statistics.median(lat), 2),
            "q_p95_ms": round(lat[int(len(lat) * 0.95)], 2),
            "r1": h1 / n, "r3": h3 / n, "r5": h5 / n,
            "mrr": statistics.mean(rr),
        }
        print(f"    {layers} layers, {dim}d, {params:.0f}M params, "
              f"q_p50 {results[name]['q_p50_ms']:.1f} ms, R@1 {h1/n:.3f}\n")

        del m, cvecs, qvecs
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    # ── report ───────────────────────────────────────────────────────────
    base_name = "intfloat/e5-large-v2"
    print("=" * 108)
    print(f"{'model':34s} {'lyr':>4s} {'dim':>5s} {'par':>5s} {'q_p50':>7s} "
          f"{'q_p95':>7s} {'R@1':>6s} {'R@3':>6s} {'R@5':>6s} {'MRR':>6s} "
          f"{'VRAM':>6s} {'load':>6s}")
    print("=" * 108)
    for name, r in results.items():
        print(f"{name[:34]:34s} {r['layers']:>4d} {r['dim']:>5d} "
              f"{r['params_m']:>5d} {r['q_p50_ms']:>7.1f} {r['q_p95_ms']:>7.1f} "
              f"{r['r1']:>6.3f} {r['r3']:>6.3f} {r['r5']:>6.3f} {r['mrr']:>6.3f} "
              f"{r['vram_mib']:>6d} {r['load_s']:>6.1f}")

    if base_name in results:
        b = results[base_name]
        print(f"\n{'model':34s} {'speedup':>9s} {'d R@1':>8s} {'d MRR':>8s} "
              f"{'ms saved/query':>15s}")
        for name, r in results.items():
            if name == base_name:
                continue
            print(f"{name[:34]:34s} {b['q_p50_ms']/r['q_p50_ms']:>8.2f}x "
                  f"{r['r1']-b['r1']:>+8.3f} {r['mrr']-b['mrr']:>+8.3f} "
                  f"{b['q_p50_ms']-r['q_p50_ms']:>15.1f}")

        print("\nlatency vs layer count - testing the launch-bound diagnosis:")
        print(f"{'model':34s} {'layers':>7s} {'q_p50':>8s} {'ms/layer':>10s}")
        for name, r in results.items():
            print(f"{name[:34]:34s} {r['layers']:>7d} {r['q_p50_ms']:>8.1f} "
                  f"{r['q_p50_ms']/r['layers']:>10.2f}")

    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
