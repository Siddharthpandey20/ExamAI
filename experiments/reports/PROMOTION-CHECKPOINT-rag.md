# Promotion checkpoint — RAG retrieval confidence & query handling

> **SUPERSEDED IN PART — see `PROMOTION-CHECKPOINT-rag-v2.md`.**
> Steps 0–2 of §4 have since been carried out. Two conclusions below did not
> survive them: the rewriting proposal (Step 4) is now recommended **against**,
> and the abstention performance figures were measured before negation items
> existed. The v2 checkpoint supersedes §1, §4 and §6. Kept unedited as the
> record of what was believed at the time.

**This is a decision document, not a change.** Nothing in `engine/`, `indexing/`,
`jobs/`, or `routes/` was modified. No threshold was changed, no feature was
enabled, no model was swapped. 245/245 tests pass and `examai.db` is byte-identical.

**Awaiting your approval before any of this touches production.**

---

## 1. PROVEN

Each of these is held-out or interval-estimated, never in-sample.

| # | finding | evidence | strength |
|---|---|---|---|
| P1 | **Dense top-1 distance supports reliable abstention.** | 0.941 balanced accuracy, stratified 5-fold CV × 5 seeds, vs 0.500 always-answer baseline | strong |
| P2 | **The fitted threshold is stable**, 0.1768 ± 0.0019 across 25 fits | it is a property of the data, not of one split | strong |
| P3 | **RRF score cannot serve as a confidence signal.** 0.711 bal.acc; `rrf_gap`/`rrf_mean`/`top1_in_both` ≈ 0.50 | structural: RRF scores a *rank*, `1/(60+rank)`, so top-1 ≈ 0.0328 whether the match is perfect or hopeless | strong, and mechanistic |
| P4 | **`content_only` rewriting improves class separation.** | paired bootstrap over items, Δbal.acc **+0.0274, 95% CI [+0.0091, +0.0510]**, P(better) 99.9% | strong |
| P5 | **That separation buys back refused queries at matched risk.** At zero false-acceptance, keyword refusals 37.5% → 25.0%; at a 2% budget, 27.5% → 12.5% | iso-risk comparison | moderate (n=40 keyword items) |
| P6 | **Conditional retry is worse than always-rewriting**, at every budget × trigger | monotone in rewrite fraction | strong |
| P7 | **`min()` over two retrieval passes erodes the abstention margin** — negatives move down 3–6× further than positives | predicted before running, confirmed | strong |

## 2. REJECTED

| claim | why |
|---|---|
| The previously suggested threshold **≤ 0.194** | Fitted against easy out-of-domain negatives. Against hard negatives it sits past a cliff: ~12% of unanswerable questions answered, 27% of in-subject-absent ones. **Do not ship this number.** |
| Multi-signal fusion (logistic regression) | +0.010 bal.acc for fitted coefficients, scaler state, a training pipeline and sklearn in the request path. All-8-features is *worse* than 3 — fitting noise. |
| Deterministic rewriting fixes keyword *retrieval* | +1 question, p = 1.00. The original hypothesis was wrong; the benefit is calibration, not recall. |
| Conditional / triggered retry | See P6. Removes an option — the simpler design is also the better one. |
| LLM-based query rewriting (not attempted, and shouldn't be) | The mechanism is filler removal, which an LLM cannot do more cheaply. P2 measured Ollama at 0.56 req/s against a 31 ms p50 retrieval path — one LLM call would cost ~50× the entire retrieval budget. |

## 3. UNCERTAIN

| question | status |
|---|---|
| Where in **0.165–0.199** the threshold should sit | This is a **product policy call, not a measurement.** The curve is mapped; the choice of how much false-acceptance to budget is yours. |
| Whether the verbose-query gain is real | Significant (p=0.016) but **circular** — those queries were built with a fixed filler template. Untrustworthy by construction; excluded from every conclusion above. |
| Real student phrasing | All degradations are synthetic. `make_keyword`/`make_verbose` are plausible, not observed. |
| Generalisation | One corpus, one embedding model. The distance band is specific to e5-large-v2 on this content and must be re-measured if either changes. |
| Effective sample size | 40 source questions × 4 phrasings. The four phrasings of one question are not independent, so effective n is nearer 40 than 160. |

## 4. PROPOSED (not implemented)

Ordered. **Nothing here should ship without the blocker in §5 fixed first.**

**Step 0 — prerequisite, no behaviour change.** Extend the eval set with negated
questions (`not`, `never`, `except`, `without`, `versus`). The current set has
none, so it is structurally blind to the defect in §5.

**Step 1 — plumbing only, no behaviour change.** `run_hybrid_search` currently
discards Chroma's `distances`. Return them alongside `rrf_score`. Nothing reads
the field yet. Independently reviewable, trivially revertible.

**Step 2 — observe only.** Log `dense_top1` per query for a period of real use.
This answers the "real student phrasing" uncertainty with production data instead
of synthetic degradations, and confirms the distance distribution matches the
eval set before any threshold gates anything.

**Step 3 — abstention, behind a default-off flag.** A single comparison:

```
if dense_top1 > ABSTAIN_THRESHOLD:  ->  "not covered in your material"
```

One float, one config value, no model. Default off; the threshold read from
config, never hardcoded.

**Step 4 — rewriting, only if Steps 0–3 hold up.** `content_only` with negation
terms excluded. Abstention and rewriting ship **together or not at all** —
rewriting alone changes retrieval for every user with no measured end-user
benefit, since its entire value is enabling a safer threshold.

## 5. BLOCKER — verified, must be fixed before Step 4

`content_only` **inverts the meaning of negated questions**, confirmed against
the implementation:

| raw | rewritten |
|---|---|
| `Why is symmetric encryption not used for key exchange?` | `symmetric encryption used key exchange` |
| `Explain why deadlock does not occur here` | `deadlock occur here` |

This is a correctness defect, not a ranking regression, and **every metric in
this report is blind to it** because no eval item contains a negation. The
retrieval numbers stand; they are simply not evidence that the transform is safe.

Fixing the word list without also extending the eval set would only move the
blind spot — hence Step 0.

## 6. EXPECTED IMPACT

| metric | today | Steps 3+4 at a 2% false-acceptance budget |
|---|---|---|
| Unanswerable questions answered anyway | 100% | ~2% |
| Answerable questions served | 100% | ~96% |
| Keyword queries refused | 0% | ~12.5% |
| Correct top-1 among answered | 0.646 | 0.675 |
| Added p50 latency | — | ~0 (one float compare + a string function) |
| Added dependencies | — | none |

The honest trade: the system stops confidently answering from evidence it does
not have, and pays for that by refusing roughly one in eight keyword-style
queries. Note also that at matched risk `content_only` answers *more* keyword
queries but gets a slightly smaller fraction of them right (0.600 vs 0.655) — it
buys coverage and pays a little precision. That is a trade, not a free win.

## 7. RISK / ROLLBACK

| risk | mitigation |
|---|---|
| Negation inversion | §5 blocker; Step 0 gates it |
| Threshold wrong for real traffic | Step 2 observes before Step 3 gates |
| Over-refusal feels broken | Default off; single config value; instant revert |
| Corpus or embedding model changes | Threshold is corpus-specific — re-run P2/P3 on any embedding change |
| Filler list wrong for other corpora | `exam`, `slide`, `notes` are filler *here*; wrong for a corpus about assessment |

Rollback for Steps 1–3 is a config flip. Step 4 is a single function call.

## 8. TEST PLAN

1. **Negation suite (new, gates everything).** Negated questions must retrieve
   the same gold slide rewritten as raw.
2. **Regression.** All 245 existing tests green.
3. **Flag-off identity.** With the flag off, retrieval output must be
   byte-identical to today's — assert on fused ordering, not just top-1.
4. **Threshold boundary.** Distances either side of the configured value, plus
   exact equality.
5. **Empty / degenerate retrieval.** No slides for a subject → abstain, not crash.
6. **Determinism.** Same query twice → identical ordering (guards the
   `_corpus_digest` BM25 cache already in `engine/tools.py`).
7. **Re-run P2/P3 end-to-end** after Step 4 and confirm the operating curve still
   matches this report.

---

## Recommendation

Steps 0–2 are safe, useful on their own, and carry no behavioural risk — they fix
an eval blind spot, stop discarding a signal the system already computes, and
gather the real-traffic data that would settle the remaining uncertainty.

Steps 3–4 should wait for Step 2's data. The measurements support them, but they
rest on 40 source questions with synthetic degradations, and Step 2 replaces that
weakness with real evidence at no risk.

**No production change is being made. Awaiting your decision.**
