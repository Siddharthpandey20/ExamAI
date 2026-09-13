# Promotion checkpoint v4 — broad RAG research

Supersedes `PROMOTION-CHECKPOINT-rag-v3.md`. v3's open questions were answer
grounding and agentic RAG. Both are now answered.

**No production code was changed this session.** 267/267 tests pass,
`examai.db` is byte-identical (`c416c600087fb060`), nothing pushed.

---

## ⚠ FIRST: a live production outage, found incidentally

**67% of production LLM calls fail right now.** Two of the three models in
`GROQ_MODELS` — `llama-3.3-70b-versatile` and
`meta-llama/llama-4-scout-17b-16e-instruct` — have been decommissioned by Groq
and return 404. `engine/llm.py::complete()` catches only 429, so a 404
**re-raises instead of falling back**. Measured: 4 of 6 consecutive
`pool.complete()` calls failed.

**Reasoning mode fails 100% of the time** — `get_best_model_name()` returns the
dead `llama-3.3-70b-versatile`, and there is no round-robin to rescue it.

This outranks every RAG finding below in user impact. It is not applied because
the model list is explicitly frozen, but the fix is three lines and is specified
in `G0-production-llm-outage.md`. **Recommend applying it.**

---

## BIGGEST QUALITY BOTTLENECK

**Retrieval bounds correctness; generation bounds trustworthiness.**

When the right slide reaches the LLM, the answer is correct **96% of the time**
(1.96/2, failing 1 of 24). When it does not, correctness drops to 1.50/2. So
correctness is a retrieval problem — and retrieval tops out at **0.842
gold-in-context at top-6**, with no context-packing option recovering the rest.

But groundedness is a *generation* problem and it is worse:

| | |
|---|---|
| answers fully grounded | **8/30** |
| answers with ≥1 unsupported claim | **25/30 (83%)** |
| unsupported claims total | **97** across 30 answers (~3.2 each) |
| questions answered despite verifiably absent evidence | **5/15 (33%)** |
| citations to documents that **do not exist** | **3** (`sdn_chapter.pdf`, `cap_theory.pdf`, `chapter3.pdf`) |

The system is right and over-elaborating. For an exam tool that is the dangerous
failure: the student believes what they read reflects *their syllabus*.

Two structural causes, both previously undocumented:
- `_build_context` passes only `summary` + `concepts`, **never `raw_text`** —
  answers are grounded in an LLM's summary of a slide, not the slide.
- The prompt says *"Speak with authority as if you studied the material
  yourself"* and *"Never say 'Based on the data provided'"*, with no permission
  to decline.

## AGENTIC RAG — did it help?

**No, except at one thing, and that one thing is real.**

| system | correct | grounded | citations | tokens | won/lost vs baseline |
|---|---|---|---|---|---|
| baseline | **1.53** | **2.00** | **3.0** | 1.00× | — |
| iterative | 1.47 | 1.94 | 3.6 | 1.19× | 0 better, 1 worse, 16 tied |
| **agentic** | **0.94** | **0.94** | **0.1** | **2.36×** | **1 better, 9 worse, 7 tied** |

It is worse on exactly the queries it was supposed to rescue — multi-slide 1.17
vs 2.00 — and it nearly stops citing slides at all.

**The exception:** on questions the material does not cover, agentic declines
**3/4 (75%)** where baseline and iterative decline **0/4 (0%)** and emit 7 and 11
slide citations respectively.

I suspected that was just the agent's prompt, which grants permission to
decline. **Ablation says no**: adding that sentence to the production prompt
leaves the decline rate at 0/4. The advantage is architectural — but n = 4, and
0/4 vs 3/4 is not significant (p ≈ 0.14). **The single most important thing to
re-measure on a larger set.**

**Iterative retrieval (WS4) and a cheap deterministic verifier (WS10) both
failed outright** — within noise of baseline everywhere.

## RETRIEVAL — what improved, what was rejected

All rejected. Five tuning avenues are now closed with measurements:

| hypothesis | result |
|---|---|
| Weighted fusion beats RRF (keeps the magnitude RRF discards) | **REJECTED** — ties at best |
| RRF K=60 is mistuned for 15-candidate lists | **REJECTED** — flat K=5…120 |
| Larger candidate pool helps | **REJECTED** — flat fetch_n 5…120 |
| Hybrid beats either retriever alone | **CONFIRMED** — keep it |
| Query-length routing | **real but worthless** — interaction CI [+0.020, +0.297], worth **+3 questions of 114** |

## CONTEXT — what improved, what was rejected

| option | gold in context | tokens |
|---|---|---|
| top 5 | 0.816 | 624 |
| **top 6 (production)** | **0.842** | 743 |
| top 10 | 0.860 | 1213 |
| top 6 + adjacent pages | 0.860 | 1693 |

**Adjacent-slide expansion is dominated** — same recall as plain top-10 for 40%
more tokens. Production's top-6 is a sensible operating point; top-10 buys
+0.018 for +63% tokens.

**Not tested: hierarchical / parent-child retrieval (WS7).** Out of session budget.

## GROUNDING — failure modes found

1. **Over-elaboration** — 83% of answers contain ≥1 claim not traceable to context.
2. **Confabulation on absent topics** — 33% answer anyway; agentic cuts this to 25%.
3. **Invented sources** — 3 citations to documents that do not exist.
4. **Unverifiable citations by construction** — the filename is free text in
   prose, though the retrieval layer knows exactly which slides it supplied.
5. **Two-stage grounding** — answers are grounded in an ingestion-time summary,
   so an error there is invisible to every retrieval metric.

## COVERAGE — what should happen to `fast_coverage`

**Do not replace the threshold. Delete the reliance on a threshold.**

`covered` is derived from `rrf_score`, which scores a rank, so it is effectively
always `true`. Meanwhile the LLM's own prose, in the **same response object**,
is nearly twice as accurate:

| | boolean | prose |
|---|---|---|
| known_present (6) | 6/6 | 6/6 |
| **known_absent (10)** | **0/10** | **5/10** |
| **related_insufficient (5)** | **0/5** | **3/5** |
| short_ambiguous (3) | 3/3 | 2/3 |
| **overall** | **9/24 (38%)** | **16/24 (67%)** |

**38% of responses are self-contradictory** — `covered: true` alongside prose
saying it is not covered. The prose verdict costs nothing extra, needs no
threshold and no per-corpus tuning. 67% is better, not good.

## PERFORMANCE — what dominates end-to-end latency

Retrieval is **not** the problem and further work on it is wasted:

| stage | p50 |
|---|---|
| retrieval (embed + Chroma + BM25 + DB) | ~95 ms |
| **LLM generation** | **1.3–12 s** depending on model |

The LLM is **10–100× everything else combined**. The observability append is
2.2 ms. Prior sessions already rejected SQLite, Chroma, BM25, fp16, CPU
inference, keep-warm and embedding caches.

---

## BEST NEXT 3 CHANGES

| # | change | impact | complexity | risk | evidence |
|---|---|---|---|---|---|
| **1** | **Fix the dead model list + treat 404 as fallback-worthy** | **Restores 67% of failed requests and all of reasoning mode** | 3 lines | Low — one stub-client test | **Measured outage, 4/6 calls fail** |
| **2** | **Derive `covered` from the model's own verdict, not `rrf_score`** | 38% → 67% correct; removes a user-visible contradiction in 38% of responses | Medium — needs a structured output field, not a regex | Medium — changes a user-visible boolean | 24 probes, 4 independent classes |
| **3** | **Re-measure not-found behaviour on a larger set**, then decide between an agent used *only* as a not-found detector and doing nothing | 33% of absent-topic questions currently get confabulated answers with citations | Low (measurement only) | None | 75% vs 0% on n=4 — promising, not proven |

Deliberately **not** in the list: query rewriting, conditional retry, fusion
changes, RRF-K tuning, pool size, adjacent-slide context, query routing,
embedder optimisation, agentic RAG as the answer path. All measured, all
rejected.

## PRODUCTION CHANGES

**None made.** Everything in this session is experimental and isolated under
`experiments/`. Change #1 is an outage fix and I recommend it be applied
promptly; #2 and #3 need the work described above first.

## RISKS

| risk | note |
|---|---|
| The outage persists | 67% failure now; recurs whenever a provider retires a model unless 404 handling changes |
| Acting on small samples | The not-found result is n=4; the coverage result n=24; grounding n=45 |
| Judge leniency | The judge is the same model that wrote the answers; mechanical metrics do not depend on it, judged ones do |
| Model substitution | G6/G7 ran on `llama3:8b` because Groq's free tier 429s at 2 concurrent calls. Comparisons are controlled; absolute quality is not production's |
| My own measurement bugs | Two were found and corrected mid-session (see below) |

## TESTS — how promotion would be validated

1. **404 fallback** — stub client returns 404 for model A; assert the pool
   falls through to model B rather than raising. *(none exists)*
2. **Model-liveness readiness probe** — assert every configured model id appears
   in the provider's list, surfaced via `routes/health.py`.
3. **Coverage fixtures** — known-absent topics (`kaju katli` and friends) must
   return `covered: false`; known-present must return `true`. *(none exists)*
4. **Grounding regression** — citations naming a document not in the supplied
   context should be detectable mechanically; no such check exists.
5. Full suite — 267/267 green.

---

## Two measurement bugs I made, and caught

Recorded because both produced plausible, alarming, wrong numbers:

- **G3** ran 4 concurrent Groq calls; the free tier 429'd every one and the
  helper swallowed the error and returned `""`. The output looked like a
  finished experiment showing agentic RAG scoring 0.00. The tell was
  `llm_calls: 0.26` when every system makes ≥1 by construction. G6 re-runs it
  sequentially and asserts the call count.
- **G1b** reported "only 12.2% of citations match the context" and "100% of
  answers are poorly grounded". Both were mine: the model writes
  `Page 62 of *CH2.pdf*` (narrow no-break space, markdown asterisks) so the
  filename never matched, and the grounding metric counted every word over three
  characters, flagging `able`, `after` and `across` as ungrounded.

Any future LLM experiment here should assert that calls actually happened.

**No production behaviour has changed. Awaiting your decision.**
