# Q6–Q7 — Query embedding latency

**Status:** complete · **Conclusion: the embedding is not slow; the GPU is
asleep.** Query embedding is neither compute-bound nor model-bound. It is
launch-bound and power-state-bound: the idle clock on this laptop GPU is
**600 MHz against a 2100 MHz maximum**, and a single short inference does not
ramp it. The same call takes **~20 ms under sustained load and ~75 ms
interleaved with ordinary CPU work.**

Six of seven optimisation candidates were rejected. **The production embedding
model was not replaced and no production code was changed.**

---

## First, a correction: absolute latency here is not reproducible

Across this session I measured retrieval p50 at **88.6, 95.7, 97.6, 101.0 and
116.9 ms** on the same machine and the same corpus, and a previous session
reported 31 ms which I could not reproduce at all. The spread is not noise
around a true value — it tracks GPU power state, which depends on what ran
immediately before.

So every absolute figure below is conditional, and the trustworthy results are
the **paired, interleaved comparisons** made inside a single process.

The one stable ratio, measured by alternating the two calls query-by-query
(n=80 paired samples):

| | p50 | p95 |
|---|---|---|
| `embed_query` | 74.98 ms | 98.69 ms |
| full `run_hybrid_search` | 95.69 ms | 125.33 ms |
| search minus embedding | 20.70 ms | |

**Embedding is 78% of retrieval latency.** That part of the earlier claim holds.

## The cost is not computation

| test | result | implication |
|---|---|---|
| Sequence length 4 → 128 tokens | 50.9 → 51.4 ms | **length is irrelevant** |
| Batch 1 vs batch 16 | 54.4 ms vs 47.6 ms *total* | a 16× larger batch is **cheaper in absolute terms** |
| fp16 vs fp32 | 52.7 vs 51.9 ms | **half precision buys nothing** |
| Per-layer cost across 3 models | 0.84 / 0.86 / 1.05 ms per layer | cost scales with **layer count**, not parameters |

Four independent results all say the GPU is idle between kernel launches. A
24-layer encoder dispatching one short sequence spends its time waiting, not
multiplying.

### And the GPU is clocked down while it waits

| condition | embed p50 | embed p95 |
|---|---|---|
| back-to-back single queries | **19.71 ms** | 29.17 ms |
| 1.0 s idle gap between queries | **39.24 ms** | **215.88 ms** |
| immediately after a sustained burst | 19.30 ms | 26.96 ms |
| after 8 s idle | 22.74 ms | 218.47 ms |
| interleaved with Chroma/BM25/DB work | 74.98 ms | 98.69 ms |

`nvidia-smi` under load: **1965 MHz / 2100 MHz, 67.8 W**. At rest: **600 MHz,
14.2 W**. The 3.5× clock ratio matches the 3.8× latency ratio (19.7 → 74.98 ms)
almost exactly.

This also retrospectively explains the unreproducible 31 ms from an earlier
session: Ollama was resident on the same GPU at the time, holding it clocked up.

**Production pays the worst case.** A real request embeds, then does CPU-bound
Chroma/BM25/SQLite work, then calls the LLM. Every query arrives at a
downclocked GPU.

---

## Candidates evaluated

| candidate | speed | quality | verdict |
|---|---|---|---|
| **raw forward + `inference_mode`** | **1.26×** (65.5 → 51.9 ms) | cosine **1.000000**, **40/40 identical top-1**, R@1/R@3/R@5/MRR unchanged | **the only safe win found** |
| fp16 on GPU | 1.24× (no better than fp32) | cosine 0.999999 | **REJECTED** — not compute-bound |
| CPU inference | **0.17×** (383 ms) | identical | **REJECTED** — 7× worse |
| GPU keep-warm thread | **0.91×** (76.6 → 84.3 ms) | n/a | **REJECTED** — contends for the GPU instead of just holding the clock |
| CUDA graph capture | — | — | **FAILED** — `cudaErrorStreamCaptureInvalidated` under both `no_grad` and `inference_mode` |
| Exact query-embedding cache | 2690× on a hit | identical | **REJECTED as redundant** — `smart_cache_check` already returns before retrieval runs, so a repeat never reaches the embedder |
| Smaller model | see below | see below | **not proposed** |

The `raw forward` win is real but modest: ~13.6 ms of `SentenceTransformer.encode`
per-call overhead (length sorting, numpy conversion, device inference) that is
designed for batches and wasted on batch size 1. It is bit-identical.

## Q7 — the model-size trade-off

Corpus and evaluation set re-embedded in memory; **production Chroma was never
touched**. Dense-only ranking, so these R@1 values are not comparable to the
hybrid numbers elsewhere — but they are comparable to each other.

| model | layers | dim | params | q p50 | R@1 | R@3 | R@5 | MRR | VRAM |
|---|---|---|---|---|---|---|---|---|---|
| **intfloat/e5-large-v2** (production) | 24 | 1024 | 335M | 20.1 ms | **0.750** | 0.775 | 0.825 | **0.774** | 2470 MiB |
| intfloat/e5-base-v2 | 12 | 768 | 109M | **10.3 ms** | 0.625 | **0.825** | **0.875** | 0.727 | 1258 MiB |
| all-MiniLM-L6-v2 | 6 | 384 | 23M | **6.3 ms** | 0.575 | 0.675 | 0.750 | 0.629 | 296 MiB |

Latency tracks layer count almost perfectly (0.84, 0.86, 1.05 ms per layer),
confirming the launch-bound diagnosis on a third axis.

**e5-base is not the easy win it looks like.** It is 1.95× faster and loses
0.125 R@1 — but *gains* on R@3 (+0.050) and R@5 (+0.050). It finds the right
slide nearly as often; it ranks it first less often. Whether that matters
depends on whether the product shows one slide or five. With n=40, the R@1 gap
is 5 questions and not significant on its own.

**Not proposed**, for three reasons beyond the quality question: swapping the
query model requires re-embedding all 690 slides (the vector spaces are
incompatible, and the dimensions differ), it would invalidate every distance
measurement in this project, and the instruction was explicit that the
production embedding model is not to be replaced.

---

## Conclusion

| claim | verdict |
|---|---|
| Embedding dominates retrieval latency | **CONFIRMED** — 78%, paired n=80 |
| Embedding is slow because the model is large | **REJECTED** — 20 ms under load; length and precision irrelevant |
| It is launch-bound and power-state-bound | **CONFIRMED** — 600 MHz idle vs 2100 MHz; 0.84–1.05 ms per layer |
| Quantization / fp16 helps | **REJECTED** |
| CPU inference helps | **REJECTED** — 7× worse |
| A keep-warm thread helps | **REJECTED** — 0.91×, contention |
| An embedding cache helps | **REJECTED** — upstream cache already short-circuits |
| Bypassing `st.encode` helps | **CONFIRMED** — 1.26×, bit-identical |
| A smaller model helps | **TRUE but not free** — 1.95× for −0.125 R@1 |

## Proposed production change

**None from this phase**, though one is now justified enough to offer:
replacing `SentenceTransformer.encode` with a direct forward pass in
`embed_query` is **bit-identical** (cosine 1.000000, 40/40 identical retrieved
top-1) for a 1.26× speed-up. It is a contained change to one method.

It is not proposed today because it saves ~14 ms against a variance of ±30 ms
between runs, and against an LLM call of ~1800 ms. It would be measurable in a
benchmark and invisible to a student. **The honest priority is that latency is
not this system's problem** — retrieval is ~100 ms out of a multi-second answer.

The genuinely useful output of this phase is diagnostic: nobody should spend
further effort quantizing, batching or shrinking the embedder, because three
independent measurements show the cost is not where those levers apply.

## Threats to validity

- One GPU (RTX 3050 6 GB laptop), one driver, Windows. Power-state behaviour is
  hardware-specific; a desktop or datacentre GPU would likely not show this.
- Absolute latency on this machine varies 3–4× between runs. Only paired,
  same-process comparisons are trustworthy, and those are what the verdicts rest on.
- Q7 uses dense-only in-memory ranking on 40 questions; R@1 differences of
  ~0.10 are 4 questions.
- CUDA graph capture failed rather than being shown not to help; on a setup
  where capture succeeds it remains the textbook fix for launch-bound inference.
