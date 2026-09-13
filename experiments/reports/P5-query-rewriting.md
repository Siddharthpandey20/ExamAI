# P5 — Deterministic query rewriting

**Status:** complete · **Conclusion: CONFIRMED, but not for the reason expected.**
Stripping a query to its content terms improves class **separation** — established
by paired bootstrap, 95% CI `[+0.0091, +0.0510]` — and that separation is what
buys back the keyword-query refusals. It does **not** improve keyword retrieval,
which was the original hypothesis.

**No production code was modified.** No LLM was used; every rewrite is a pure
string function.

---

## Hypothesis under test

> The phrasing penalty measured in Phase 2 (R@1: positive 0.725 → keyword 0.575
> → verbose 0.525) can be recovered by cheap deterministic rewriting, which
> would relieve the 25% keyword false-abstention that blocked P3 promotion.

Five variants, all pure functions: `strip_filler` (drop conversational words),
`content_only` (drop filler **and** stopwords), `template` (wrap a terse query in
question shape, since e5 was trained on natural-language queries), and
`strip+template`.

## Guarding against measuring my own generator

The verbose queries were built by prepending a fixed template. A rewriter that
deleted exactly that template would score brilliantly and prove nothing. Three
guards, stated in the script header:

- the filler list is generic conversational vocabulary and contains no
  multi-word phrase from the generator template;
- every variant is scored on **all four** phrasings, including plain positives,
  where a good rewrite must be nearly a no-op;
- verbose and keyword gains are reported **separately**, and only the keyword
  ones are treated as evidence.

That guard turned out to matter — see the significance table.

---

## Retrieval results (R@1)

| variant | positive | noisy | keyword | verbose | ALL |
|---|---|---|---|---|---|
| baseline | 0.725 | 0.650 | 0.575 | 0.525 | 0.619 |
| strip_filler | 0.700 (−0.025) | 0.700 (+0.050) | 0.550 (−0.025) | 0.650 (+0.125) | 0.650 |
| **content_only** | 0.700 (−0.025) | 0.675 (+0.025) | 0.600 (+0.025) | 0.700 (+0.175) | **0.669** |
| template | 0.725 (+0.000) | 0.650 (+0.000) | 0.625 (+0.050) | 0.525 (+0.000) | 0.631 |
| strip+template | 0.700 (−0.025) | 0.700 (+0.050) | 0.625 (+0.050) | 0.650 (+0.125) | 0.669 |

### Almost none of this survives a significance test

Paired exact McNemar on the per-question win/loss pattern (`b` lost, `c` gained):

| variant | scope | b | c | net | p | verdict |
|---|---|---|---|---|---|---|
| content_only | all positives | 4 | 12 | +8 | 0.077 | trend |
| content_only | positive | 3 | 2 | −1 | 1.000 | noise |
| content_only | keyword | 0 | 1 | +1 | 1.000 | noise |
| **content_only** | **verbose** | 0 | 7 | +7 | **0.016** | **significant** |
| strip_filler | verbose | 0 | 5 | +5 | 0.063 | trend |
| template | keyword | 1 | 3 | +2 | 0.625 | noise |

The **only** significant retrieval gain is on `positive_verbose` — which is
precisely the class the circularity warning flagged as untrustworthy. Taken at
face value, the retrieval hypothesis is **not supported**: the apparent +0.050
keyword gain is one question, and the honest reading is that deterministic
rewriting does not fix keyword retrieval.

If the experiment had stopped at the recall table, it would have reported a win
that is not there.

---

## The real effect: separation, not recall

The negatives move away faster than the positives do. Mean top-1 distance:

| variant | positive | keyword | **in_subject_absent** | cross_subject | out_of_domain |
|---|---|---|---|---|---|
| baseline | 0.1392 | 0.1544 | 0.2022 | 0.2254 | 0.2564 |
| **content_only** | 0.1413 | 0.1545 | **0.2161** | 0.2247 | 0.2432 |

Positives are unchanged (0.1392 → 0.1413, 0.1544 → 0.1545) while
`in_subject_absent` — the hardest negative class — moves +0.0139 further away.
Stripping filler removes vocabulary that a wrong-but-plausible slide can match
on, so the query lands on subject terms only.

### Paired bootstrap over items, 2000 resamples

| variant | Δ balanced acc | 95% CI | P(better) | verdict |
|---|---|---|---|---|
| **content_only** | **+0.0274** | **[+0.0091, +0.0510]** | 99.9% | **established** |
| strip_filler | +0.0101 | [−0.0045, +0.0299] | 92.2% | not established |
| template | +0.0038 | [−0.0031, +0.0177] | 80.6% | not established |
| strip+template | −0.0160 | [−0.0336, +0.0107] | 15.2% | not established |

`content_only` is the one variant whose interval clears zero. Note that
`strip+template` is actively **worse** — composing two rewrites that each look
harmless produces a query shape that pulls negatives back in.

---

## Resolving an apparent contradiction

The cross-validated pipeline says `content_only` cuts keyword false-abstention
26.5% → 13.5%. But at a **fixed** threshold it refuses exactly as many keyword
queries as the baseline (10/40 at T=0.1768). Both are true, and the reconciliation
is the actual finding:

> The gain does not come from keyword queries getting closer to their gold slide.
> It comes from the negatives moving away, which lets the threshold rise from
> 0.1768 to 0.1922 at the same risk — and the more permissive threshold is what
> stops refusing keyword queries.

So the comparison must hold **risk** constant, not the threshold. Choosing each
variant's threshold to meet a false-acceptance budget:

| FA budget | variant | T | keyword refused | all refused | R@1 *among answered* |
|---|---|---|---|---|---|
| **0%** | baseline | 0.1653 | 37.5% | 13.8% | 0.659 |
| **0%** | **content_only** | 0.1762 | **25.0%** | 12.5% | 0.721 |
| 2% | baseline | 0.1718 | 27.5% | 10.0% | 0.646 |
| 2% | **content_only** | 0.1911 | **12.5%** | 3.8% | 0.675 |
| 5% | baseline | 0.1819 | 25.0% | 7.5% | 0.649 |
| 5% | **content_only** | 0.1993 | **7.5%** | 1.9% | 0.662 |

At every risk level `content_only` refuses far fewer questions. At a 2% budget it
answers 154/160 answerable questions versus the baseline's 144.

### The honest caveat

Look at the last column at the 2% budget: keyword R@1 *among questions the system
agreed to answer* is **0.600 for content_only versus 0.655 for the baseline**. It
answers more keyword queries and gets a slightly smaller fraction of them right.
It is buying coverage, and paying a little precision for it. That trade is
probably right for a study tool — an answer with a citation the student can check
beats a refusal — but it is a trade, not a free win, and it should not be
described as one.

---

## Conclusion

| claim | verdict |
|---|---|
| Deterministic rewriting improves keyword retrieval | **REJECTED** — +1 question, p=1.0 |
| Deterministic rewriting improves verbose retrieval | **UNPROVEN** — significant but circular |
| `content_only` improves answerable/unanswerable separation | **CONFIRMED** — CI clears zero |
| That separation relieves the P3 keyword blocker | **CONFIRMED** — 37.5% → 25.0% at matched zero risk |
| Composing rewrites is safe | **REJECTED** — `strip+template` is worse than either |
| LLM-based rewriting is worth trying next | **not yet** — see below |

## Proposed production change

**None yet.** Two things must happen first, in this order:

1. **Phase 6** must test whether rewriting *conditionally* (only when the first
   retrieval is borderline) keeps the separation gain without the −0.025 that
   `content_only` costs on plain, well-formed questions. Always-rewriting
   penalises the queries that were already fine.
2. Abstention and rewriting would ship **together or not at all**. Rewriting
   alone changes retrieval results for every user with no measured end-user
   benefit — its entire value here is enabling a safer abstention threshold.

LLM rewriting was **not** attempted. The deterministic result shows the mechanism
is filler removal, which an LLM cannot do more cheaply, and the P2 measurement
puts Ollama generation at 0.56 req/s — adding an LLM call to every query would
cost more latency than the whole retrieval path (p50 31 ms).

## Blocker if promoted later — negation inversion (verified, not hypothetical)

`not` is in the stopword list, so `content_only` **reverses the meaning** of any
negated question. Run against the actual implementation:

| raw query | rewritten | effect |
|---|---|---|
| `Why is symmetric encryption not used for key exchange?` | `symmetric encryption used key exchange` | **inverted** |
| `Explain why deadlock does not occur here` | `deadlock occur here` | **inverted** |
| `What is the difference between TCP and UDP?` | `difference TCP UDP` | fine |
| `TCP congestion control window` | *(unchanged)* | fine |

This is a correctness defect, not a ranking regression, and the evaluation set
**cannot see it**: no item contains a negation, so every metric in this report is
blind to it. The retrieval numbers above are unaffected, but they are also not
evidence that the transform is safe.

Any promotion must first exclude negation and contrast terms (`not`, `no`,
`never`, `except`, `unless`, `without`, `versus`, `vs`) from the stripped set,
**and** add eval coverage for negated questions — otherwise the fix is untested
too. Fixing the word list without extending the eval set would just move the
blind spot.

## Other risks

- The filler list is hand-written and English-only.
- `exam`, `slide`, `notes`, `chapter` are treated as filler. That is right for
  this corpus but would be wrong for a corpus *about* assessment design.
- The 0.1762–0.1993 band is specific to e5-large-v2 on this corpus.

## Threats to validity

- 40 source questions × 4 phrasings; the four are not independent.
- Verbose gains are partly an artifact of the generator, as flagged above.
- The bootstrap resamples items, so it accounts for sampling error but not for
  the synthetic origin of the degradations.
