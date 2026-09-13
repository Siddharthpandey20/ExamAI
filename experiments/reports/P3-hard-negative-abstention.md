# P3/P4 — Abstention against hard negatives

**Status:** complete · **Conclusion: PARTIALLY CONFIRMED, with a real cost.**
Dense distance still separates answerable from unanswerable questions well
(balanced accuracy **0.941**, held-out), but the earlier near-perfect result was
an artifact of easy negatives, and the honest threshold is **not** the 0.194
suggested previously.

**No production code was modified.** Retrieval was exercised read-only.

---

## Why this experiment was re-run

R1 (previous session) reported near-perfect not-found detection. Its negatives
were out-of-domain questions ("how long to roast a chicken"), which sit far from
any slide **by construction**. Separating those proves the embedding works, not
that abstention works.

This phase rebuilt the evaluation set so the negatives are genuinely hard, and
re-measured under cross-validation.

---

## The evaluation set (Phase 1)

250 items. Every negative is labelled by **lexical** verification — checking that
the term occurs zero times in the slide text of that subject — never by dense
similarity. That independence is the whole point: using distance to label the
data would guarantee separation and prove nothing.

| class | n | what it is |
|---|---|---|
| positive | 40 | the original question |
| positive_noisy | 40 | typos, informal phrasing |
| positive_keyword | 40 | reduced to bare keywords |
| positive_verbose | 40 | padded with student filler |
| in_subject_absent | 44 | **hardest** — plausibly belongs to the subject, verified absent |
| cross_subject_overlap | 34 | real question, wrong subject, vocabulary overlaps |
| out_of_domain | 12 | another field entirely (control) |

The anchor-term rule matters: `MPLS label switching` is kept as absent because
`mpls` occurs 0 times, even though `switching` is common; `QUIC protocol` is
**rejected** because `quic` occurs 65 times. An earlier any-overlap rule threw
away good negatives and would have biased the set easy.

## The negatives are now genuinely hard

Mean top-1 dense distance by class — the hard negatives **overlap the positives**,
which the old set did not:

| class | mean distance | range |
|---|---|---|
| positive_verbose | 0.1313 | |
| positive | 0.1392 | 0.0866–0.1939 |
| positive_keyword | 0.1544 | 0.0847–0.2088 |
| **in_subject_absent** | **0.2022** | **0.1655–0.2346** |
| cross_subject_overlap | 0.2254 | |
| out_of_domain | 0.2564 | |

`in_subject_absent` starts at 0.1655 while positives reach 0.2088. There is no
threshold that separates them cleanly — that overlap is the finding.

---

## Results (Phase 3) — stratified 5-fold CV × 5 seeds, all held out

Baseline: always answer = accuracy 0.640, balanced accuracy 0.500.

| signal | bal.acc | acc | prec | rec | spec | F1 | threshold | ± |
|---|---|---|---|---|---|---|---|---|
| **dense_top1** | **0.941** | 0.934 | 0.981 | 0.914 | 0.969 | 0.946 | **0.1768** | 0.0019 |
| dense_min | 0.941 | 0.934 | 0.981 | 0.914 | 0.969 | 0.946 | 0.1768 | 0.0019 |
| lex_topk | 0.907 | 0.900 | 0.959 | 0.881 | 0.933 | 0.919 | 0.4000 | 0.0000 |
| dense_mean | 0.906 | 0.890 | 0.976 | 0.850 | 0.962 | 0.908 | 0.1887 | 0.0049 |
| lex_top1 | 0.873 | 0.850 | 0.969 | 0.790 | 0.956 | 0.871 | 0.2669 | 0.0012 |
| rrf_top1 | 0.711 | 0.685 | 0.849 | 0.618 | 0.804 | 0.715 | 0.0326 | 0.0001 |
| rrf_gap | 0.579 | | | | | | | |
| n_in_both | 0.547 | | | | | | | |
| rrf_mean | 0.546 | | | | | | | |
| top1_in_both | 0.490 | | | | | | | |

The threshold is stable across folds and seeds (± 0.0019), so it is a property
of the data rather than of one split.

### RRF score is nearly useless as a confidence signal — as predicted

`rrf_top1` reaches only 0.711, and `rrf_gap`, `rrf_mean` and `top1_in_both` sit
at or near 0.500. This is structural, not a tuning failure: RRF scores a **rank**
(`1/(60+rank)`), so the top result always scores about 0.0328 whether it is a
perfect match or the least-bad member of a bad set. Rank carries no information
about whether anything relevant was found. Any confidence signal must come from
the dense distance that `run_hybrid_search` currently discards.

### Multi-signal combination (Phase 4)

| combination | bal.acc | acc | prec | rec | spec |
|---|---|---|---|---|---|
| dense_top1 alone | 0.941 | 0.934 | 0.981 | 0.914 | 0.969 |
| dense + lex | 0.945 | | | | |
| **dense + rrf + lex** | **0.951** | | | | |
| all 8 features | 0.948 | | | | |

**Not worth it.** The best combination buys **+0.010 balanced accuracy** in
exchange for a logistic-regression model with fitted coefficients, scaler state,
a training pipeline and a scikit-learn dependency in the request path — versus
one float comparison. Adding all eight features is *worse* than three, the usual
sign of fitting noise. Phase 4 conclusion: **use the single dense threshold.**

---

## The operating curve (Phase 3b) — this is the decision, not the number

"Best balanced accuracy" is one point on a curve, and it is not obviously the
right one. The two errors are not symmetric: a false abstention is visible and
recoverable (the student rephrases), while a false acceptance is a confident
wrong answer the student may not catch.

| T | false abst. | false acc. | prec | rec | spec | bal.acc | keyword refused | absent caught |
|---|---|---|---|---|---|---|---|---|
| 0.1650 | 23 | **0** | **1.000** | 0.856 | **1.000** | 0.928 | 37.5% | 100% |
| 0.1700 | 19 | 1 | 0.993 | 0.881 | 0.989 | 0.935 | 32.5% | 97.7% |
| 0.1750 | 15 | 2 | 0.986 | 0.906 | 0.978 | 0.942 | 27.5% | 95.5% |
| **0.1800** | 13 | 3 | 0.980 | 0.919 | 0.967 | **0.943** | 25.0% | 93.2% |
| 0.1900 | 9 | 9 | 0.944 | 0.944 | 0.900 | 0.922 | 20.0% | 84.1% |
| 0.1950 | 6 | 15 | 0.911 | 0.963 | 0.833 | 0.898 | 15.0% | 72.7% |
| 0.2050 | 2 | 34 | 0.823 | 0.988 | 0.622 | 0.805 | 5.0% | 36.4% |

Read the right-hand columns. The curve collapses quickly above about 0.19: at
0.2050 the system answers **63% of the questions it has no evidence for**. The
previously suggested **0.194 sits on the far side of that cliff** — it would let
through roughly 12% of unanswerable questions and 27% of the in-subject-absent
ones. It was fitted against easy negatives and does not survive harder ones.

**T = 0.165 is notable**: zero false acceptances across all 90 negatives, while
still answering 85.6% of answerable questions.

### Where the cost falls — almost entirely on one class

False abstention at T = 0.1768, by phrasing:

| class | refused | rate |
|---|---|---|
| positive | 1/40 | 2.5% |
| positive_noisy | 2/40 | 5.0% |
| **positive_keyword** | **10/40** | **25.0%** |
| positive_verbose | 0/40 | 0.0% |

False acceptance, by negative class:

| class | answered | rate |
|---|---|---|
| out_of_domain | 0/12 | 0% |
| cross_subject_overlap | 0/34 | 0% |
| **in_subject_absent** | **2/44** | **4.5%** |

Refusing one in four keyword queries would make the feature feel broken to a
student who types `TCP congestion control window` instead of a sentence. **This
is the blocker for promotion, and it is a retrieval problem rather than a
threshold problem** — the threshold is only exposing it.

---

## Conclusion

| claim | verdict |
|---|---|
| Dense distance supports abstention | **CONFIRMED** — 0.941 held-out, vs 0.500 baseline |
| RRF score is a usable confidence signal | **REJECTED** — 0.711; structurally rank-only |
| Multi-signal fusion is worth the complexity | **REJECTED** — +0.010 for a trained model |
| The earlier near-perfect result | **WEAKENED** — 0.976 → 0.941 against real negatives |
| Threshold ≤ 0.194 | **REJECTED** — past the cliff; ~12% false acceptance |
| Ready to promote | **NO** — 25% keyword false-abstention must be fixed first |

## Proposed production change

**None yet** — deliberately. The threshold is not promoted, per the standing
instruction. What this phase establishes is that *if* abstention ships, it should
be a single `dense_top1` comparison in the range **0.165–0.180**, chosen by
explicit policy rather than by maximising balanced accuracy, and that it should
not ship until keyword-query retrieval improves.

That makes **Phase 5 (query rewriting) a prerequisite, not a parallel track.**

## Threats to validity

- 40 source questions expanded 4× — the four phrasings of one question are not
  independent, so the effective n is nearer 40 than 160 on the positive side.
- Degradations are synthetic (`make_keyword`, `make_verbose`), generated by rule.
  They are plausible but are not observed student queries.
- Negatives are absent-by-vocabulary. A topic discussed without its usual term
  would be mislabelled; the anchor rule reduces but does not eliminate this.
- One corpus, one embedding model. The 0.165–0.180 band is specific to
  e5-large-v2 on this content and must be re-measured if either changes.
