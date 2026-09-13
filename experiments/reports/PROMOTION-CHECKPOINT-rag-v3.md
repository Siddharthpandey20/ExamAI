# Promotion checkpoint v3 — real-query evidence

> **SUPERSEDED by `PROMOTION-CHECKPOINT-rag-v4.md`.** Its two open questions -
> answer grounding and agentic RAG - are now answered, and a live production
> LLM outage was found that outranks everything here. Kept unedited as the
> record of what was believed at the time.

Supersedes `PROMOTION-CHECKPOINT-rag-v2.md`. v2's central open question was
"what do real queries look like?" That question is now answered, and the answer
changes the priority order.

**No user-visible behaviour changed.** Two production files gained
instrumentation that is proven inert. 267/267 tests pass, `examai.db` is
byte-identical, nothing pushed.

`0.194` is used nowhere. `0.1768` is not treated as a production threshold.
Rewriting, retry and abstention remain unimplemented.

---

## The headline

**A production feature is already broken, and it is a more defensible target
than anything previously proposed.** `fast_coverage` tells students their
material covers topics it does not — `covered=true` for **31/31** real queries,
including "kaju katli" against Machine Learning.

Meanwhile the abstention proposal got worse, not better, once real queries were
measured: at the fitted threshold it would refuse **52%** of genuinely
answerable real questions.

## 1. PROVEN

| # | finding | evidence |
|---|---|---|
| A | **`fast_coverage`'s confidence gate is equivalent to `always true`.** It thresholds RRF score, which scores a rank: `1/61 = 0.01639` for a rank-1 hit, so `"low"` (≤ 0.015) is unreachable and `covered` is false only when the result list is empty | `covered=true` 31/31 real queries; labels 27 high / 4 medium / **0 low** |
| B | **Real queries are nothing like the evaluation sets.** Median 5 words vs 13; 35% are ≤3 words vs 2% | 31 distinct queries from `query_cache`, typed before this work began |
| C | **Real answerable queries sit +0.038 further out** than generated positives, with their median (0.1793) landing exactly on the fitted threshold | mean 0.1775 vs 0.1392 |
| D | **A threshold at 0.1768 would refuse 52% of answerable real queries** | 11/21 |
| E | **Short queries genuinely fail — it is not a measurement artifact.** Truncating the same question to 2 words raises distance to 0.1946 *and* drops R@1 to 0.100; distance and recall degrade together | controlled truncation sweep |
| F | **Short queries fail because they are underspecified, not badly retrieved.** For `TCP` the three retrievers return three different slides and the fused answer is one neither ranked first; `tcp` occurs 477× in CN | per-retriever comparison |
| G | **`dense_top1` can be fooled by padding a query with corpus vocabulary.** `make_verbose`'s filler lowers mean distance 0.1419 → 0.1336 while lowering R@1 0.560 → 0.400 | controlled filler comparison |
| H | **Query embedding is launch- and power-state-bound, not compute-bound.** Idle GPU clock 600 MHz vs 2100 MHz max; 19.7 ms back-to-back vs 74.98 ms interleaved; length irrelevant; 0.84–1.05 ms per layer across three models | four independent measurements |
| I | **Ingestion is LLM-bound.** AI cleanup at 0.56 req/s is **25×** embedding + Chroma + BM25 + SQLite combined | 690-slide profile |
| J | **The observability change is inert.** | 0/290 retrieval differences, 267/267 tests, 2.2 ms append, no query text logged |

## 2. REJECTED

| claim | why |
|---|---|
| **Abstention at the fitted threshold** | Refuses 52% of answerable real queries. Unshippable. |
| Generated evaluation sets predict real behaviour | Real queries sit +0.038 out; every realistic question type added has lowered measured performance (keyword 25%, negation 37.5%) |
| Dense distance is a length artifact | **My own hypothesis, rejected.** Padding *raises* distance, for both classes |
| Sparse retrieval rescues short queries | No better than dense at ≤2 words |
| fp16 / quantization for the embedder | No gain — not compute-bound |
| CPU query embedding | 7× worse (383 ms) |
| A GPU keep-warm thread | **0.91×** — contends for the device rather than holding the clock |
| An embedding cache | Redundant; `smart_cache_check` returns before retrieval runs |
| SQLite / Chroma / BM25 as ingestion bottlenecks | 0.5% / 3.8% / 0.2% of measured cost |
| Query rewriting, conditional retry, LLM rewriting | Rejected in v2, unchanged |

## 3. UNCERTAIN

| question | status |
|---|---|
| Where a coverage threshold belongs | Three populations disagree (specificity 0.556 / 0.706 / 0.750 at T=0.21) and only **4 real unanswerable queries** exist. A gate fitted to 4 points is fitted to noise. |
| What real students ask at scale | 31 queries, one user, four weeks. The observability log now accumulates this. |
| Seven ingestion stages | Unmeasured — no source PDF/PPTX in the repo. Reported as unmeasured, not estimated. |
| Whether fusion helps at full length | Dense-only beat RRF 0.600 vs 0.560 on n=25. One question. A lead, not a finding. |
| Answer grounding / citation correctness | **Not investigated this session.** |

## 4. OBSERVABILITY — what was collected

`engine/observability.py` records, per retrieval: timestamp, endpoint, subject,
a truncated SHA-256 of the normalised query, structural shape (length, question
mark, acronym count, keyword shape), `dense_top1`, `dense_mean`,
`top_result_distance`, dense/sparse/fused counts, `rrf_top1`, retriever
agreement, latency, and whether an answer was produced.

**Not** recorded: raw query text (opt-in only), slide content, filenames,
document content, credentials. The log directory is gitignored.

Evidence gathered: 31 distinct real queries replayed with full feature capture;
the resulting distribution is §1 B–D.

## 5. PERFORMANCE — what actually consumes resources

| | |
|---|---|
| **Retrieval** | ~95 ms p50, of which **78% is query embedding** (paired, n=80) |
| Embedding, cause | GPU at 600 MHz idle vs 2100 MHz loaded; 19.7 ms warm vs 74.98 ms interleaved |
| Everything else in retrieval | ~21 ms |
| **Ingestion** | LLM-bound: AI cleanup **25×** all other measured stages |
| Indexing half | embedding 95.4%, Chroma 3.8%, SQLite 0.5%, BM25 0.2% |
| Observability overhead | 2.2 ms per search (2.5% of retrieval, ~0.1% of an answer) |

**Absolute latency on this machine is not reproducible** — retrieval p50
measured 88.6, 95.7, 97.6, 101.0 and 116.9 ms across this session, and an
earlier session's 31 ms could not be reproduced at all. Only paired
same-process comparisons are trustworthy.

## 6. PROPOSED PRODUCTION CHANGES

**Only observability is justified by the evidence, and it is already in.**

One change is *close* to justified and is offered for a decision rather than
taken: **repair the `fast_coverage` gate.** The argument does not depend on
choosing a good threshold — the current gate has **zero specificity**, so it
carries no information at all. Any distance-based gate is better than one whose
output is constant.

What is still missing is the threshold. I recommend **not** picking one until
the observation log holds more unanswerable real queries; today there are four.

Two things are explicitly **not** proposed: abstention (refuses 52% of real
answerable queries) and any embedder optimisation (measurable in a benchmark,
invisible against a multi-second answer).

## 7. RISKS

| risk | note |
|---|---|
| Observation log growth | Capped at 32 MB, then stops; one line per search |
| Log contains user query metadata | Hashed, gitignored, disableable via `EXAMAI_OBSERVE_RETRIEVAL=0` |
| Fixing the coverage gate with a bad threshold | Would turn a useless-but-harmless label into a wrong one. Hence: gather data first |
| Evidence base is one user, one corpus | Every threshold in every report is corpus- and model-specific |
| `dense_top1` gameable by corpus-vocabulary padding (§1 G) | Any future gate inherits this weakness |

## 8. TESTS — how promotion would be validated

1. **Flag-off identity** — retrieval byte-identical with observation disabled.
   *(built: 15 tests + 290-item replay)*
2. **Logging cannot break retrieval** — unwritable path, size cap,
   unserialisable field. *(built)*
3. **Privacy** — no raw query, filename or slide text in the log. *(built)*
4. **Negation minimal pairs** — gates any query transform. *(built, p7)*
5. Regression — full suite. *(267/267)*
6. **If the coverage gate is ever changed**: a fixture set of known-absent
   topics (`kaju katli` and friends) must return `covered: false`, and a
   fixture set of known-present topics must return `covered: true`. Neither
   exists today and both should precede the change.

---

## Recommendation

**Keep collecting.** The observability change is the only thing this evidence
justifies shipping, and it is in.

The most valuable single output of this session is that a shipped feature was
found to be silently wrong, by a method — replaying real queries through the
production code path — that had never been applied before. The second most
valuable is a set of confident rejections: five plausible latency optimisations
and three plausible ingestion bottlenecks are now ruled out with measurements,
so nobody needs to spend time on them.

**No production behaviour has changed. Awaiting your decision.**
