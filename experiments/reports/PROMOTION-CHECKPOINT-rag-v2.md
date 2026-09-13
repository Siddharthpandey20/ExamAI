# Promotion checkpoint v2 — RAG retrieval confidence

> **SUPERSEDED by `PROMOTION-CHECKPOINT-rag-v3.md`.** Its central open
> question - what real queries look like - has since been answered, and the
> answer removes abstention from the proposal list: at the fitted threshold
> it would refuse 52% of genuinely answerable real queries. Kept unedited as
> the record of what was believed at the time.

Supersedes §1, §4 and §6 of `PROMOTION-CHECKPOINT-rag.md`, which was written
before Steps 0–2 were carried out. Two of its conclusions did not survive.

**Production behaviour is unchanged.** One production file was modified —
`engine/tools.py` gained an opt-in `stats` out-parameter that is inert when
omitted. No abstention, no rewriting, no threshold, no flag. 252/252 tests pass;
`examai.db` untouched; nothing pushed.

`0.194` is used nowhere. `0.1768` is not treated as a production threshold.

---

## What changed since v1

| v1 said | now |
|---|---|
| `content_only` rewriting improves separation — **PROVEN** | **NOT REPLICATED.** Zero effect on an independent evaluation set; R@1 leans worse |
| Abstention reaches 0.941 balanced accuracy | **0.914** once negation items exist; 0.838 on real exam questions |
| Rewriting is Step 4 of the rollout | **Recommended against** |
| Retrieval p50 ≈ 31 ms | **≈ 90–98 ms**; 71% of it is query embedding |

## 1. PROVEN

| # | finding | evidence |
|---|---|---|
| A | **Dense top-1 distance separates answerable from unanswerable questions.** Holds on two independently built evaluation sets | bal.acc 0.919 (n=290) and 0.912 (n=68, real exam questions) |
| B | **The threshold value transfers.** Fitted separately on two sets sharing no lineage, it lands 0.0095 apart (0.1793 vs 0.1888) | cross-set fit |
| C | **It also transfers across subjects.** LOSO fit 0.1791 ± 0.0014, mean cost +0.024 | leave-one-subject-out |
| D | **RRF score cannot be a confidence signal** — structurally, it scores a rank | 0.711 bal.acc; gap/mean/agreement ≈ 0.50 |
| E | **Multi-signal fusion is not worth it** | +0.010 for a trained model; 8 features worse than 3 |
| F | **Conditional retry is worse than always-rewriting**, and `min()` over two passes erodes the margin | monotone across 3 budgets × 5 triggers |
| G | **`content_only` inverts negated questions**, and the negation-safe fix works at a cost of 0.002 bal.acc | minimal pairs: 7/40 collapse → 0/40 |
| H | **The `stats` plumbing is inert** | 0 differences in retrieved ids, hit@1 and distances across 250 real replays; 7 new tests |

## 2. REJECTED

| claim | why |
|---|---|
| Threshold **≤ 0.194** | Past the cliff — ~12% false acceptance. Withdrawn in P3 and not revived. |
| **Rewriting (`content_only` or `content_safe`) should ship** | **New.** No benefit on independent data (CI [−0.031, +0.057] and [−0.053, +0.034]); R@1 0.706 → 0.676 → 0.647. The Set A benefit came from stripping filler I had written into the test queries. |
| Multi-signal fusion | +0.010 for sklearn in the request path |
| Conditional / triggered retry | Worse at every budget; a second pass now also costs ~70 ms of embedding |
| LLM query rewriting | Deterministic rewriting has no demonstrated benefit to improve on |

## 3. UNCERTAIN — and one of these is now the main obstacle

| question | status |
|---|---|
| **Which question types the eval set still fails to cover** | **The central risk.** Every realistic type added has lowered performance: keyword 25% refused, negation 37.5%. There is no reason to believe the set is finished. |
| How real students actually phrase questions | Still unknown. All degradations are synthetic; the only real questions available are 40 instructor-written PYQs. |
| Where in ~0.165–0.19 a threshold should sit | A product policy call, not a measurement |
| Absolute performance on real questions | At the Set-A threshold, real exam questions see **29% false abstention** (10/34) against 1/34 false acceptance |
| Generalisation beyond this corpus / model | Untested. Band is specific to e5-large-v2 here. |

## 4. PROPOSED

**Step 1 (done, inert).** `stats` out-parameter on `run_hybrid_search`. Gates
nothing, read by no production path. Reviewable on its own.

**Step 2 — observe only.** Log `dense_top1` per real query. This is now the
*only* proposed next step, and it is the one that resolves the central
uncertainty: what real students actually ask, and where their queries land in
the distance distribution. No behaviour change, no gating.

**Step 3 — reconsider abstention after Step 2 produces data.** Not before. The
measured performance fell each time the evaluation got more realistic (0.948 →
0.914 → 0.838), and the direction of that trend matters more than any single
value. If real queries resemble the PYQ set, 29% false abstention is far too
high to ship.

**Rewriting: dropped.** Not deferred — dropped. It has no independent evidence
of benefit and carries a correctness risk requiring a curated word list.
`content_safe` remains in `experiments/` as the correct implementation should
the question be revisited.

## 5. EXPECTED IMPACT

Only Step 2 is proposed, so: **no user-visible change, no latency change, no
new dependency.** One log line per search.

Any later abstention would have to be judged against this, which is the honest
current estimate on the most realistic data available:

| at the Set-A threshold, on real exam questions | |
|---|---|
| unanswerable questions correctly refused | 33/34 (97%) |
| **answerable questions wrongly refused** | **10/34 (29%)** |

## 6. RISK / ROLLBACK

| risk | mitigation |
|---|---|
| `stats` plumbing regresses retrieval | Proven inert on 250 real replays; revert is one parameter |
| Logging volume in Step 2 | One float per search; sample if needed |
| Threshold tuned on unrepresentative questions | Precisely what Step 2 exists to prevent |
| Eval set still blind to some question type | Unresolved — treat every accuracy figure as an upper bound |

## 7. TEST PLAN

1. **Negation minimal pairs** — any query transform must keep affirmative and
   negated forms distinct. Pass/fail, gates everything. *(built, p7)*
2. **Flag-off identity** — retrieval byte-identical when `stats` is omitted.
   *(built, 7 tests + 250-item replay)*
3. **Regression** — full suite. *(252/252 green)*
4. Threshold boundary, empty-retrieval, and determinism suites — **only if** a
   threshold is ever proposed again.
5. Re-run the independent PYQ evaluation after any embedding-model change.

---

## Recommendation

**Do Step 2 (observe only). Do not promote abstention. Drop rewriting.**

The most useful thing this round produced is a negative result: a finding that
two bootstrap intervals called "established" with P(better) ≥ 99.9% vanished
completely on data built independently. The arithmetic was right; the question
was too narrow. That is worth more than the rewriting feature would have been,
and it is the reason to gather real query data before gating anything on a
distance.

**No production behaviour has changed. Awaiting your decision.**
