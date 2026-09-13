# H1 — Raw text and source-ID citations: both rejected

**Status:** complete · **Conclusion: no production change is justified.**
The source-ID citation scheme made things **worse** on every axis that matters.
Raw text is mildly positive on groundedness but hurts citation completeness and
is not decisive at this sample size.

It also **corrects a finding from G1**: citation fabrication did not reproduce.

**No production code was changed.** 24 items × 3 variants, retrieval held fixed,
**96 LLM calls, assertion enforced.**

---

## The variants

Identical retrieval; only the context representation differs.

| | Context | Citation format |
|---|---|---|
| **A** current | `summary` + `concepts` | `Page N of filename` (free text) |
| **B** raw_text | A + the slide's actual text (capped 700 chars) | `Page N of filename` |
| **C** source_ids | B, but sources labelled `[S1]…[S6]` | `[S1]` — backend owns the mapping |

C is the architecture proposed in the v4 checkpoint: a citation can only name a
source that was actually supplied, so fabrication becomes *unrepresentable*
rather than discouraged.

---

## Result 1 — the fabrication problem did not reproduce

| variant | citations | fabricated | rate | naming a non-existent file |
|---|---|---|---|---|
| **A current** | 95 | **0** | **0.0%** | **0** |
| B raw_text | 87 | 1 | 1.1% | 1 |
| C source_ids | 150 | **0** | **0.0%** | 0 |

G1 reported three citations naming documents that do not exist
(`sdn_chapter.pdf`, `cap_theory.pdf`). **Here the current architecture produced
zero fabricated citations in 95.**

Two differences explain it: G1 pinned `openai/gpt-oss-120b` directly (the only
live model at the time), while this run uses the repaired three-model pool; and
G1 had 15 absent-topic items against 8 here.

**The honest revision: citation fabrication is real but rare, not endemic.**
G1's "3 fabricated" stands as an observation; the implied rate does not. This is
exactly why the v4 checkpoint listed the source-ID scheme as *needing
measurement before implementation* rather than as a decided fix — and the
measurement says the problem it solves is much smaller than it looked.

## Result 2 — source IDs made things worse

| | A current | B raw_text | **C source_ids** |
|---|---|---|---|
| correct (judged, 0–2) | 1.42 | **1.50** | **1.25** |
| grounded (judged, 0–2) | 1.33 | **1.50** | **1.21** |
| declined on absent topics | 5/8 (62%) | **6/8 (75%)** | **4/8 (50%)** |
| cited the gold slide | **70%** | 50% | **70%** |
| paired vs A — correct | — | 2 better, 1 worse | **0 better, 3 worse** |
| paired vs A — grounded | — | 3 better, 1 worse | **1 better, 3 worse** |

C loses on correctness, groundedness and — most damagingly — **declines less
often on topics the material does not cover** (50% vs 62%). It also emitted the
*most* citations (6.2 per answer vs 4.0), which reads as citation padding rather
than better provenance.

A plausible mechanism: stripping the human-readable page and filename from the
context removes information the model was using to reason about *what* it had.
Labels are easier to cite and easier to cite carelessly.

**Verdict: REJECTED.** The architecture prevents a failure that occurs at ~0–1%
and costs measurable quality across the board. That is a bad trade.

## Result 3 — raw text is mildly positive, not decisive

| | A current | B raw_text |
|---|---|---|
| grounded (judged) | 1.33 | **1.50** |
| unsupported claims (judged) | 0.62 | **0.08** |
| declined on absent topics | 62% | **75%** |
| **cited the gold slide** | **70%** | **50%** |
| context size | 1.00× | 0.93× |
| paired — grounded | — | **3 better, 1 worse, 20 tied** |

Groundedness improves and judged unsupported claims drop sharply, at *no* extra
context cost (B is slightly smaller because it drops some metadata fields).

But **citation completeness falls from 70% to 50%** — given the gold slide, B
cites it less often. For a tool whose product is provenance, that is a real
cost, not a rounding error.

Paired, B is 3-better/1-worse on groundedness across 24 items. **That is a
trend, not a result.**

**Verdict: NOT PROMOTED.** Promising enough to re-run at a larger sample;
nowhere near strong enough to change the context builder on.

---

## A caveat about one metric

"Unsupported specifics" (numbers and acronyms in the answer absent from the
context) rose A 1.79 → B 2.08 → C 4.08. **Do not read that as a ranking.** The
variants have *different contexts by construction*: A and B include page numbers
in the context text, C does not — so a number in C's answer has fewer chances to
match. The metric is valid *within* a variant and confounded *across* them.

Flagging it rather than quietly dropping it, because this is the third metric in
this project that looked like a finding and was an artifact.

---

## Conclusion

| claim | verdict |
|---|---|
| Citation fabrication is endemic in the current design | **REJECTED** — 0/95 here; G1's 3 cases were a different model and a larger absent set |
| Source-ID citations improve grounding | **REJECTED** — worse on correctness, groundedness and declining |
| Source-ID citations prevent fabrication | technically true, but it prevents a ~0–1% failure at measurable cost |
| Passing `raw_text` improves groundedness | **TREND** — 1.33 → 1.50, 3 better / 1 worse, n=24 |
| Passing `raw_text` is free | **REJECTED** — citation completeness 70% → 50% |
| Any of this should ship today | **NO** |

## Proposed production change

**None.** Both candidates from the v4 checkpoint are now measured and neither
justifies changing user-visible behaviour.

If revisited, the experiment to run is **B at a larger sample**, tracking
citation completeness as a first-class metric rather than a side effect — that
is the axis where it loses, and the one a bigger sample would settle.

## Threats to validity

- 24 items, 8 of them absent-topic. Paired differences of 2–3 items are not
  significant.
- The judge is the same model family that produced the answers.
- Answers came from the repaired three-model Groq pool, so different items may
  have been answered by different models — that is the production path, but it
  adds variance a single-model run would not have.
- `RAW_CHARS = 700` per slide is one arbitrary cap; a larger budget might change
  B's result in either direction.
