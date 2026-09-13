# G1 — Answer grounding and citation correctness

**Status:** complete · **Conclusion: retrieval is not the correctness
bottleneck — generation is the groundedness bottleneck.** When the right slide
reaches the LLM, the answer is correct 96% of the time. But 25 of 30 answers
contain at least one claim the judge could not trace to the context, the model
answers 33% of questions whose answer is verifiably absent, and it has invented
citations to documents that do not exist.

**No production code was modified.** Generation used the production prompt and
context builder, called directly so nothing was cached.

---

## Two measurement bugs, found and fixed before reporting

The first analysis produced two alarming numbers, both of which were mine:

| first reported | actual cause |
|---|---|
| "only **12.2%** of citations match the context" | The model writes `Page 62 of *CH2.pdf*` — a narrow no-break space and markdown asterisks. My regex captured `*CH2.pdf*`, which never matched `CH2.pdf`. **Page numbers matched 100% of the time, which was the tell.** Citation formatting is fine. |
| "**100%** of answers score below 0.8 grounding" | The metric counted every word over three characters, so the "ungrounded" terms were `able`, `above`, `after`, `across`, `actual` — ordinary English absent from terse slide summaries. It measured prose style, not grounding. |

Both are recorded rather than quietly corrected, because the first version
looked plausible and would have been a confident false finding. The corrected
grounding metric scores only **checkable specifics** — numbers, acronyms and
identifiers — which are the claims a student could look up and find wrong.

---

## What the production path actually sends the model

Two structural facts, neither previously documented:

**1. `_build_context` never passes `raw_text`.** It sends only `summary` and
`concepts` — both written by an LLM at ingestion time. Every answer is therefore
grounded in *a model's summary of a slide*, not the slide. An error introduced
at ingestion is invisible downstream and unfalsifiable by any retrieval metric.

**2. The prompt instructs confidence and forbids hedging:**

```
- Never say "Based on the data provided" or "According to the slides shared"
- Speak with authority as if you studied the material yourself
```

There is no instruction to stay within the evidence or to decline when the
slides do not cover the question. This is a prompt tuned for fluent, confident
prose — precisely the condition under which ungrounded claims are hardest for a
student to notice.

---

## Results — 45 answers (30 answerable, 15 verifiably absent)

### Correctness is high, and it tracks retrieval

| case | n | correct (0–2) | grounded (0–2) |
|---|---|---|---|
| gold slide **was** in context | 24 | **1.96** | 1.17 |
| gold slide was **not** in context | 6 | 1.50 | 0.83 |

**Retrieval succeeded yet the answer was still not fully correct in only 1 of 24
cases (4%).** When the evidence arrives, the model uses it. That settles the
question this workstream was built to answer:

> **Correctness is bounded by retrieval, not by generation.**

### Groundedness is not

| | answerable | insufficient |
|---|---|---|
| grounded = 2 (fully) | **8/30** | 8/15 |
| grounded = 1 | 17/30 | 2/15 |
| grounded = 0 | 5/30 | 5/15 |
| mean | **1.10 / 2** | 1.20 / 2 |
| total unsupported claims | **97** | 74 |
| answers with ≥1 unsupported claim | **25/30 (83%)** | 8/15 |

Roughly **3.2 unsupported claims per answer**. The model is correct *and*
elaborating beyond the slides — filling gaps from its own parametric knowledge.
For a general assistant that is often helpful. For an exam-prep tool it is the
central risk: the student believes what they read reflects *their syllabus*, and
has no way to tell which sentences came from the slides.

### Behaviour when the material does not cover the question

15 questions whose answer is lexically verified absent from the subject:

| | |
|---|---|
| answers that said so | **10/15 (67%)** |
| **answers that answered anyway** | **5/15 (33%)** |
| slide citations emitted for absent topics | 10 |

The five it answered anyway: DNSSEC validation, WebRTC signalling, NAT
traversal, database sharding, columnar storage. All plausible-sounding, all
absent from the corpus.

### Fabricated sources

Three citations point at documents that **do not exist** among the corpus's 30
files:

| question | invented citation |
|---|---|
| Explain OpenFlow as covered in this subject | page 23 of `sdn_chapter.pdf` |
| Explain CAP theorem as covered in this subject | page 12 of `cap_theory.pdf` |
| Explain MPLS label switching | page 17 / 19 of `chapter3.pdf` |

The model invented plausible filenames for topics it had no evidence for. This
is the most directly harmful failure found: a student could search for a
document that was never uploaded.

Notably, the 67% that *do* decline show the model is perfectly capable of
recognising missing evidence — it simply is not asked to, and the prompt pushes
the other way.

---

## Conclusion

| claim | verdict |
|---|---|
| Answer correctness is the bottleneck | **REJECTED** — 96% correct when gold is retrieved |
| Retrieval is the bottleneck for correctness | **CONFIRMED** — quality tracks whether gold reached the context |
| Answers stay within the evidence | **REJECTED** — 83% contain ≥1 unsupported claim |
| The system declines when evidence is absent | **PARTIALLY** — 67% do, 33% do not |
| Citations are well formatted | **CONFIRMED** (after fixing my parser) |
| Citations are always real | **REJECTED** — 3 citations to non-existent documents |

## Proposed production change

**None yet — measurement first, as instructed.** But the failure modes are now
specific enough to name what a future change would target, in order of evidence:

1. **The prompt actively discourages hedging** while the model demonstrably
   *can* recognise absent evidence (67% unprompted). This is the cheapest
   candidate and the one with the clearest mechanism.
2. **Citations are unverifiable by construction.** The filename is free text in
   prose. The retrieval layer knows exactly which slides were supplied; a
   citation naming a document not in the context could be detected mechanically
   with no model involved.
3. **Only summaries reach the model.** Whether passing `raw_text` improves
   groundedness is untested and is a real experiment, not an obvious fix — it
   would roughly triple context size.

None of these should be changed before the failure modes are reproduced on a
larger set; 30 answers graded by one model is a starting point, not a mandate.

## Threats to validity

- The judge is **the same model that wrote the answers**, which biases toward
  leniency. The mechanical numbers (citation counts, fabricated filenames) do
  not depend on it; the correctness and groundedness scores do.
- 30 answerable + 15 absent items, one subject mix, one generation model.
- Only `openai/gpt-oss-120b` was available (see the model-outage finding), so
  these results describe that model, not the intended production pool.
- The run did not persist the context string, so specifics could not be checked
  against it retrospectively. G6 records context and closes this gap.
