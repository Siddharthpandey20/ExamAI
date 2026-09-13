# P11 — Negation-safe rewriting, and independent validation

**Status:** complete · **Conclusion: the P5 finding does NOT replicate.**

Two results, and the second is the important one:

1. `content_only` can be made negation-safe at essentially no cost. The safe
   variant passes the minimal-pair gate 40/40 where the original fails 7/40, and
   scores within 0.002 balanced accuracy of it on the original evaluation set.
2. **On an independently constructed evaluation set, the benefit disappears
   entirely** — for both variants. P5's central claim was an artifact of the
   evaluation set's lineage.

**No production code was modified in this phase.**

---

## Gate 1 — negation safety is a property, not a score

`content_safe` is `content_only` with negation and contrast terms preserved
(`not`, `no`, `never`, `without`, `except`, `unless`, `versus`, `unlike`, …).

| variant | pairs | collapsed | rate | verdict |
|---|---|---|---|---|
| baseline | 40 | 0 | 0.0% | PASS |
| **content_only** | 40 | **7** | **17.5%** | **FAIL** |
| **content_safe** | 40 | **0** | **0.0%** | **PASS** |

A collapsed pair, from the run:

```
'Is emails reliably protocols their used here?'
'Is emails reliably protocols their not used here?'
      both -> 'emails reliably protocols used here'
```

This is pass/fail and no retrieval score can offset it. The fix works, and it is
cheap — one set membership test per token.

## The safe variant costs nothing on the original set

Set A = the 250-item hard set plus the 40 negation items (n=290).

| variant | R@1 | R@5 | bal.acc | T | positive | keyword | negation | noisy | verbose |
|---|---|---|---|---|---|---|---|---|---|
| baseline | 0.590 | 0.790 | 0.919 | 0.1793 | 0.725 | 0.575 | 0.475 | 0.650 | 0.525 |
| content_only | 0.650 | 0.805 | **0.974** | 0.1911 | 0.700 | 0.600 | 0.575 | 0.675 | 0.700 |
| **content_safe** | 0.645 | 0.810 | **0.972** | 0.1911 | 0.700 | 0.600 | 0.550 | 0.675 | 0.700 |

Paired bootstrap vs baseline, 2000 resamples:

| variant | Δ bal.acc 95% CI | P(better) | verdict |
|---|---|---|---|
| content_only | [+0.0305, +0.0769] | 100.0% | established |
| content_safe | [+0.0292, +0.0750] | 100.0% | established |

Preserving negation costs **0.002 balanced accuracy**. If the transform were
going to ship, it should obviously ship in the safe form. But —

---

## Gate 2 — the independent set, and the finding that matters

Everything measured in P3 and P5 traces back to one source: `eval/eval_set.json`,
40 questions from the project's own generation pipeline, degraded four ways by
rules I wrote and then measured with metrics I chose. If that pipeline has a
house style, those experiments measured how retrieval handles *that style*.

**Set B shares none of that lineage.** It is built from the 40 unique PYQ
questions already in the database — real exam questions written by an instructor
before any of this work existed. Multi-part, differently phrased, differently
distributed across subjects (CN 14, CA 8, ML 7, OS 5; CA and OS had no positives
at all in the earlier work).

Gold labels are assigned by **IDF-weighted lexical overlap, not by embedding**.
`pyq_matches` already exists in the database with a `similarity_score` and using
it would have been the obvious shortcut — and exactly the circularity this
project has been avoiding, since those matches were produced by the same
embedding model whose distances are the signal under test.

### Result

| variant | R@1 | R@5 | bal.acc | T |
|---|---|---|---|---|
| **baseline** | **0.706** | 0.824 | 0.912 | 0.1888 |
| content_only | 0.676 | 0.882 | 0.912 | 0.1882 |
| content_safe | 0.647 | 0.882 | 0.897 | 0.1882 |

| variant | Δ bal.acc 95% CI | P(better) | verdict |
|---|---|---|---|
| content_only | [−0.0307, +0.0571] | 62.2% | **not established** |
| content_safe | [−0.0526, +0.0338] | 30.2% | **not established** |

And with no refitting at all — applying the threshold fitted on Set A:

| set | baseline | content_only | content_safe |
|---|---|---|---|
| A | 0.919 | 0.930 | 0.930 |
| **B** | **0.838** | **0.838** | **0.838** |

On the independent set the three variants are **identical to three decimal
places**, and R@1 moves the wrong way: 0.706 → 0.676 → 0.647.

### What this means

P5 concluded "CONFIRMED — `content_only` improves separation, established by
paired bootstrap." That conclusion was correct about the data it had and wrong
about the world. The mechanism is now clear in hindsight: the transform's
measured benefit came largely from stripping filler out of `positive_verbose`
queries — and I wrote the filler. Real exam questions contain no such padding,
so there is nothing for the transform to remove except signal.

**The P5 verdict is revised from CONFIRMED to NOT REPLICATED.**

This is also the clearest vindication of building the independent set. Two
bootstrap intervals on 250 and 290 items both said "established" with P(better)
= 99.9% and 100.0%. Neither was wrong arithmetically. Both were answering a
narrower question than the one that mattered.

### Honest limits on this conclusion

Set B has 34 answerable items. The intervals are wide and "not established" is
**not** proof of no effect. What can be said:

- there is **no evidence of benefit** on independent data, and
- the point estimates lean **negative** on R@1 for both variants, and
- the effect on Set A was large enough that, if real, something should have been
  visible here.

The right reading is "unsupported and probably absent", not "disproven".

---

## Threshold transfer, by contrast, holds up well

The same comparison for the *threshold value* gives the opposite answer:

| | fitted T | bal.acc |
|---|---|---|
| Set A (n=290) | 0.1793 | 0.919 |
| Set B (n=68) | 0.1888 | 0.912 |

Two entirely independent evaluation sets, fitted separately, land **0.0095
apart**. Applying A's threshold to B costs +0.074 balanced accuracy; the reverse
costs +0.019.

But the absolute performance on real questions is lower: at A's threshold, Set B
sees **10/34 (29%) false abstentions** against 1/34 false acceptances. Real exam
questions sit further from the corpus than generated ones (mean answerable
distance 0.1642 vs 0.1479), so a threshold tuned on generated questions refuses
too many real ones.

| | n | mean | p25 | median | p75 |
|---|---|---|---|---|---|
| A answerable | 200 | 0.1479 | 0.1283 | 0.1428 | 0.1659 |
| B answerable | 34 | 0.1642 | 0.1459 | 0.1641 | 0.1845 |
| A unanswerable | 90 | 0.2182 | 0.1977 | 0.2167 | 0.2298 |
| B unanswerable | 34 | 0.2234 | 0.2074 | 0.2229 | 0.2393 |

The separation exists in both. It is just narrower where the questions are real.

---

## Conclusion

| claim | verdict |
|---|---|
| `content_only` can be made negation-safe | **CONFIRMED** — 40/40, costs 0.002 |
| `content_only` improves separation (P5) | **NOT REPLICATED** on independent data |
| `content_safe` improves separation | **NOT REPLICATED** — leans negative |
| Rewriting should ship | **NO** — no independent evidence of benefit |
| The threshold *value* transfers across lineages | **CONFIRMED** — 0.0095 apart |
| The threshold's *performance* transfers | **NO** — 29% false abstention on real questions |

## Proposed production change

**None.** Rewriting is now recommended **against**, not merely deferred: it has
no demonstrated benefit on independent data, it carries a correctness risk that
needs a curated word list to contain, and it would change retrieval for every
user. The negation-safe variant is worth keeping in the experiments directory
only as the correct implementation should the question ever be revisited.

## Threats to validity

- Set B is small (34 answerable, 34 unanswerable) and its intervals are wide.
- Its gold labels come from lexical overlap, which structurally favours
  candidates that share wording — the same bias applies to all three variants
  being compared, so relative comparison is sound, but absolute R@1 on Set B is
  not comparable to Set A's.
- 6 of 40 PYQ questions were rejected for weak lexical grounding, several of
  them OCR-garbled in the source data ("Cousidor a systom with 2honn of phyalont
  monory"). Those are real questions the system would face and they are absent
  from this evaluation.
- Both sets come from one corpus and one embedding model.
