# Q8–Q9 — A correct coverage gate, and where ingestion time goes

**Status:** complete · **No production code was modified.**

---

# Q8 — what a correct coverage gate would look like

Q1 proved `fast_coverage`'s gate is equivalent to `always true`. This asks what
should replace it — and deliberately treats it as a *different* problem from
abstention.

## Why coverage is not abstention

Abstention **suppresses** an answer: a false abstention means the student gets
nothing. A coverage verdict is a **label on an answer shown either way** — the
slides and the explanation are returned regardless, and a wrong "not covered"
costs a moment of doubt rather than the content.

So the operating point should differ. For abstention the evidence said protect
recall at nearly any cost. For coverage, wrongly saying "this doesn't look like
it's in your material" is far cheaper than confidently telling a student their
syllabus covers **kaju katli**.

## Candidate gates on all three labelled populations

| gate | population | recall | specificity | wrongly covered | wrongly not covered |
|---|---|---|---|---|---|
| **production (RRF)** | all three | **1.000** | **0.000** | **everything** | 0 |
| dense ≤ 0.19 | constructed | 0.905 | 0.900 | 9/90 | 19/200 |
| dense ≤ 0.19 | independent PYQ | 0.882 | 0.941 | 2/34 | 4/34 |
| dense ≤ 0.19 | real queries | 0.667 | **1.000** | **0/4** | 7/21 |
| dense ≤ 0.21 | constructed | 0.985 | 0.556 | 40/90 | 3/200 |
| dense ≤ 0.21 | independent PYQ | 0.941 | 0.706 | 10/34 | 2/34 |
| **dense ≤ 0.21** | **real queries** | **0.905** | **0.750** | **1/4** | **2/21** |
| dense ≤ 0.23 | real queries | 0.952 | 0.750 | 1/4 | 1/21 |

The specific queries that motivated this:

| query | subject | dense | production | T=0.19 | T=0.21 |
|---|---|---|---|---|---|
| kaju katli | ML | 0.2986 | **COVERED** | not | not |
| kaju katli | CA | 0.2775 | **COVERED** | not | not |
| ARQ | CA | 0.2429 | **COVERED** | not | not |
| What is POP3? | CN | 0.2060 | **COVERED** | not | COVERED |

At T=0.21 the cost on real answerable queries is 2/21 — `is DFDs covered`
(0.2337) and `is Cognitive limitation of human is covered?` (0.2138).

## What may and may not be concluded

**Not** a threshold. The three populations disagree about where it belongs
(specificity at 0.21 is 0.556 / 0.706 / 0.750), and the real-query population
has **only 4 unanswerable items** — a gate fitted to separate four points is
fitted to noise.

What they agree on is the **ordering**: nonsense queries land further away than
real ones, in all three populations.

**The defensible claim is narrow and sufficient:** the current gate has **zero
specificity**. It carries no information, so it cannot be *worse* to replace it
with something that does — and the signal to do it with is already computed.

---

# Q9 — where ingestion time actually goes

## Scope, stated honestly

The brief asked for upload → parsing → extraction → OCR → chunking → embedding →
Chroma → BM25 → DB → total. **The repository contains no source PDF or PPTX and
`knowledge/` is empty.** Fabricating a synthetic document would produce a number
about the synthetic document, so those stages are reported as **NOT MEASURED**
rather than estimated:

> upload · PDF/PPTX parsing · image extraction · OCR · table extraction ·
> page segmentation · markdown writing

What *is* measured exactly, from the 690 real slides already in the database —
everything between "text has been extracted" and "the document is searchable",
which is the half a re-index must repeat. Writes went to a temporary SQLite file
and a temporary Chroma collection; `examai.db` and production Chroma were
read-only.

## Result

690 slides, 1.1 M characters, 15 documents:

| stage | seconds | % of measured | ms/slide | slides/s |
|---|---|---|---|---|
| **embedding** | **46.62** | **95.4%** | 67.56 | 15 |
| Chroma writes | 1.88 | 3.8% | 2.72 | 368 |
| DB writes | 0.25 | 0.5% | 0.36 | 2763 |
| BM25 tokenise | 0.06 | 0.1% | 0.08 | 11998 |
| BM25 build | 0.06 | 0.1% | 0.08 | 12263 |
| **total measured** | **48.86** | 100% | 70.81 | 14 |

## And against the stage that was not re-measured

P2 measured Ollama at **0.56 req/s**. AI cleanup makes one LLM call per slide:

| | |
|---|---|
| AI cleanup, 690 slides at 0.56 req/s | **1232 s (20.5 min)** |
| Everything measured above | **48.9 s** |
| Ratio | **25×** |

**Deleting embedding, Chroma, BM25 and SQLite entirely would make a 21-minute
ingest 3.8% faster.** Ingestion is LLM-bound and nothing else is close. P2
separately established that Ollama concurrency cannot be raised on this host
because llama3 needs 4.3 GiB of system RAM and only ~2 GiB is free at load.

## A detail worth recording: passages and queries are bound by different things

Q6 found query embedding is *launch*-bound — sequence length irrelevant, batch 16
cheaper in total than batch 1. Here, batched passage embedding costs **67.6
ms/slide**, essentially the same as a single 20-token query.

That is not a contradiction. Passages run to 2000 characters (~500 tokens) while
queries are ~20. At 500 tokens the GPU has real work, so passages are
**compute-bound** where queries are **launch-bound**. Batching helps queries and
cannot help passages.

The practical consequence: the Q6 conclusion ("don't bother optimising the
embedder") holds for retrieval, and holds for ingestion too — but for the
opposite reason. In ingestion the embedder is genuinely busy, and it is still
only 3.8% of the job.

---

## Conclusion

| claim | verdict |
|---|---|
| The production coverage gate carries information | **REJECTED** — zero specificity on all three populations |
| A distance-based coverage gate would be better | **SUPPORTED** — but no threshold is defensible on n=4 |
| SQLite limits ingestion | **REJECTED again** — 0.5% of measured cost, 2763 slides/s |
| Chroma or BM25 limit ingestion | **REJECTED** — 3.8% and 0.2% |
| Embedding limits ingestion | **REJECTED in context** — 95% of the measured half, 3.8% of the whole |
| Ingestion is LLM-bound | **CONFIRMED** — AI cleanup is 25× everything else combined |

## Proposed production change

**None.** The only change this session's evidence would justify is repairing the
coverage gate, and that needs a threshold the data does not yet support.

For ingestion the evidence says clearly what **not** to do: do not optimise
SQLite, Chroma, BM25 or the embedder. If ingestion time matters, the only lever
that moves it is the per-slide LLM call — fewer calls, batched calls, a smaller
model, or skipping cleanup for slides that do not need it. None of those were
tested here.

## Threats to validity

- Seven pipeline stages are unmeasured; the "3.8%" figure is a share of
  (measured + projected AI cleanup) and would shrink further if parsing and OCR
  are significant.
- AI cleanup is projected from P2's 0.56 req/s, not re-measured, and assumes one
  call per slide.
- One corpus of 690 slides across 15 documents on one machine.
- The coverage populations are small, especially the 4 real unanswerable queries.
