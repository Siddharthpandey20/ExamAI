# R3 — retrieval confidence without a second LLM

**Status:** complete · **Conclusion: PARTIALLY SUPPORTED, but NOT actionable yet**

**No production code was modified.**

---

## Hypothesis under test

> Cheap deterministic signals available at retrieval time can predict whether
> the evidence is sufficient, so a low-confidence branch could retry or abstain
> instead of answering from weak evidence.

**Success criterion:** a signal that predicts retrieval success on **held-out**
data better than the majority-class baseline by a margin larger than noise.

---

## Method

Nine signals computed from what `run_hybrid_search` already returns, so a
positive result would cost nothing at query time: `top1_rrf`, `mean_rrf`,
`gap_1_2`, `gap_ratio`, `top1_in_both_lists`, `n_in_both_lists`,
`score_spread`, `lexical_overlap`, `n_candidates`.

Two outcomes: `hit_at_1` (gold ranked first) and **`hit_at_5`** (gold anywhere in
the context the LLM will see — the one that actually matters, since the LLM
receives 6 slides, not 1).

Evaluated twice: once in-sample, then with **leave-one-out cross-validation**,
fitting the threshold on 39 questions and testing the held-out one.

---

## Why the in-sample numbers had to be discarded

Picking the best threshold on the same 40 questions it is then scored against
is fitting, not measuring. With 9 signals and n=40, beating the baseline by a
few questions is expected by chance. The two columns diverge exactly as that
predicts:

| outcome | signal | in-sample | **LOOCV** | vs baseline |
|---|---|---|---|---|
| hit_at_1 | `top1_rrf` | 0.900 | **0.875** | **+0.150** (6 questions) |
| hit_at_1 | `mean_rrf` | 0.850 | 0.700 | −0.025 |
| hit_at_1 | `lexical_overlap` | 0.800 | 0.700 | −0.025 |
| hit_at_1 | `gap_1_2` | 0.775 | 0.525 | −0.200 |
| **hit_at_5** | `top1_rrf` | 0.900 | **0.800** | **−0.050** |
| **hit_at_5** | `top1_in_both_lists` | 0.875 | 0.875 | +0.025 (1 question) |

`top1_rrf` looked like the best predictor of `hit_at_5` in-sample at 0.900 and
lands **below** the 0.850 baseline under cross-validation. That is the overfit
the LOOCV pass existed to catch.

---

## Results

**`hit_at_1` — supported.** `top1_rrf` holds up: LOOCV **0.875** against a 0.725
baseline, +6 questions out of 40. A genuine, cross-validated signal.

**`hit_at_5` — not supported.** The best honest signal gains **1 question out of
40** over simply always answering. No signal separates "the gold slide is in the
context" from "it is not".

---

## Conclusion

**The actionable version of this hypothesis is NOT supported.**

The signal that would drive a confidence gate is `hit_at_5` — *is the evidence
the LLM is about to read sufficient?* — and that is the one that is not
predictable above baseline. The signal that does work, `hit_at_1`, matters much
less: the LLM already receives six slides, so gold at rank 3 is not a failure.

There is also a sample-size problem that no amount of analysis fixes: `hit_at_5`
has only **6 negative cases** in 40 questions. Fitting a threshold on 6 examples
is not a basis for a production gate, and the +0.025 "best" result is one
question.

---

## Proposed production change

**None.** Specifically, this evidence does **not** justify:

- a confidence threshold gating answers (R3),
- an iterative retry-on-low-confidence controller (R4),
- an abstention branch driven by retrieval score (R5).

Building any of those now would mean hardcoding a threshold that
cross-validation shows does not generalise — precisely what the checklist warns
against.

---

## What would make this decidable

The blocker is the evaluation set, not the method. `hit_at_5` is 34/40 positive,
so the interesting class is tiny. R1 should add questions whose answer is
genuinely **absent** from the corpus — out-of-scope and cross-subject probes —
where the gold label is deterministic by construction and needs no fabrication
or human adjudication. That would:

- give the negative class enough members to fit and validate a threshold,
- make not-found precision/recall measurable at all, which is the actual goal of
  R5,
- let this experiment be re-run unchanged against better data.

**R1 is therefore a prerequisite for R3, R4 and R5**, not a parallel task.

---

## Risk / rollback

No production change proposed. The experiment reads the evaluation set and calls
`run_hybrid_search` read-only; it writes only to `experiments/benchmarks/`.
