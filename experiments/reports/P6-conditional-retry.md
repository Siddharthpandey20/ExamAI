# P6 — Conditional retry

**Status:** complete · **Conclusion: REJECTED.** Retrying only the queries that
look weak is worse than rewriting every query, at every risk level tested, while
also costing a second retrieval pass on 40–78% of traffic.

**No production code was modified.** Both retrieval passes were already recorded
per item in Phase 5, so every policy below is an exact replay, not a model.

---

## Hypothesis under test

> `content_only` costs −0.025 R@1 on plain, well-formed questions — rewriting a
> query that was already fine can only lose information. Applying it *only* when
> the first retrieval looks weak should keep the separation gain and skip that
> cost.

This is the standard cascade intuition, and it is wrong here.

**Success criterion:** a conditional policy beating `always_rewrite` on
end-to-end usefulness at matched false-acceptance risk.

## Method

Four policies, five trigger points, three risk budgets. The headline metric is
deliberately strict:

> **useful** = fraction of *all* answerable questions that got the correct top-1
> slide **and** were not refused.

Abstaining counts as a miss. That is the student's experience, and it prevents a
policy from scoring well by refusing everything it would have got wrong.

---

## Results

| budget | policy | T | **useful** | answered | kw refused | R@1 given answered | retry rate |
|---|---|---|---|---|---|---|---|
| 0% | always_baseline | 0.1653 | 0.569 | 86.2% | 37.5% | 0.659 | 0% |
| 0% | **always_rewrite** | 0.1762 | **0.631** | 87.5% | 25.0% | 0.721 | 100% |
| 0% | retry_if_far@0.13 | 0.1762 | 0.594 | 87.5% | 25.0% | 0.679 | 78% |
| 0% | retry_take_min@0.13 | 0.1653 | 0.562 | 87.5% | 37.5% | 0.643 | 78% |
| 2% | always_baseline | 0.1718 | 0.581 | 90.0% | 27.5% | 0.646 | 0% |
| 2% | **always_rewrite** | 0.1911 | **0.650** | 96.2% | 12.5% | 0.675 | 100% |
| 2% | retry_if_far@0.13 | 0.1911 | 0.613 | 96.2% | 12.5% | 0.636 | 78% |
| 2% | retry_if_far@0.17 | 0.1762 | 0.600 | 91.2% | 25.0% | 0.658 | 43% |
| 5% | always_baseline | 0.1819 | 0.600 | 92.5% | 25.0% | 0.649 | 0% |
| 5% | **always_rewrite** | 0.1993 | **0.650** | 98.1% | 7.5% | 0.662 | 100% |
| 5% | retry_if_far@0.13 | 0.1993 | 0.613 | 98.1% | 7.5% | 0.624 | 78% |

`always_rewrite` wins at all three budgets. No trigger value closes the gap, and
the conditional policies land monotonically between the two extremes — the more
queries a policy rewrites, the better it does. There is no operating point where
selectivity pays.

---

## Why the cascade intuition fails here

P5 established that `content_only` works by moving the **negatives** away, not by
pulling positives closer. Its value is therefore a property of the *distance
distribution as a whole*, not of any individual query.

A conditional policy produces distances from two different transforms and then
compares them against **one** threshold. Raw-query distances and rewritten-query
distances are not on the same scale, so the mixture is not thresholdable — the
threshold ends up calibrated for neither population. Selectivity does not
preserve a calibration gain; it destroys it.

Put briefly: **rewriting here is a calibration change, and you cannot calibrate
half a distribution.**

This also explains the otherwise odd `retry_if_far` behaviour — the lower the
trigger (the more queries rewritten), the better the score, converging on
`always_rewrite` from below.

## `retry_take_min` — a free lunch that is not free

Keeping whichever pass scored closer looks strictly better and is strictly worse.
Giving every query two chances to look close helps the negatives most, because a
negative has two independent opportunities to find something spuriously similar:

| class | baseline | take_min | shift |
|---|---|---|---|
| positive | 0.1392 | 0.1367 | −0.0025 |
| positive_verbose | 0.1313 | 0.1313 | −0.0001 |
| in_subject_absent | 0.2022 | 0.2021 | −0.0000 |
| **cross_subject_overlap** | 0.2254 | 0.2187 | **−0.0067** |
| **out_of_domain** | 0.2564 | 0.2425 | **−0.0139** |

The negatives move down 3–6× further than the positives. `min()` over two
retrievals is a maximum-selection over noise, and it erodes exactly the margin
abstention depends on. This was predicted in the script header before running,
and the prediction held.

---

## Conclusion

| claim | verdict |
|---|---|
| Conditional retry beats always-rewrite | **REJECTED** — worse at every budget |
| A better trigger exists | **REJECTED** — monotone in rewrite fraction |
| `min()` over two passes is free | **REJECTED** — erodes the negative margin |
| Rewriting's benefit is per-query | **REJECTED** — it is distributional |

## Proposed production change

**None.** This phase removes an option rather than adding one, which is worth as
much: the simpler design (`always_rewrite`, one retrieval pass) is also the
better one, so no retry machinery, no trigger threshold to tune, and no second
embedding call per query.

## Threats to validity

- Only `content_only` was used as the retry transform. A retry that changed the
  *retrieval mode* rather than the query — sparse-only, or a widened `top_k` —
  is a different hypothesis and is untested here.
- 250 items; differences of 0.01–0.02 in `useful` are within noise. The
  conclusion rests on the consistent ordering across 3 budgets × 5 triggers, not
  on any single cell.
- Both passes were cached from one run, so retrieval non-determinism is excluded
  by construction (correct for policy comparison, but it means the measured
  retry cost excludes real-world variance).
