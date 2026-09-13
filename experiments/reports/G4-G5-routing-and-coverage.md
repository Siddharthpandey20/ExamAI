# G4/G5 — Query routing, and what to do about `fast_coverage`

**Status:** complete · **Two results: a real effect too small to ship, and a
coverage fix that needs no threshold at all.**

**No production code was modified.**

---

# G4 — query-length routing

G2 found the one positive retrieval signal in an otherwise negative sweep:
dense-only beats RRF on short queries and loses badly on long ones. A reversal
is more interesting than a difference, and it has a mechanism (Q5: `tcp` matches
477 slides, so BM25 has nothing to discriminate on for a one-token query).

## Paired significance, 114 items

| subset | n | RRF R@1 | dense R@1 | b | c | p | verdict |
|---|---|---|---|---|---|---|---|
| short (≤6 words) | 49 | 0.633 | **0.694** | 1 | 4 | 0.375 | noise |
| medium (7–12) | 16 | **0.812** | 0.625 | 4 | 1 | 0.375 | noise |
| long (>12 words) | 49 | **0.653** | 0.592 | 5 | 2 | 0.453 | noise |
| **independent PYQ** | 34 | **0.706** | 0.471 | 9 | 1 | **0.021** | **significant** |
| all | 114 | 0.667 | 0.640 | 10 | 7 | 0.629 | noise |

*(b = RRF won that question, c = dense won)*

No individual length bucket reaches significance. The only significant cell is
that **RRF is decisively better on real exam questions** (p = 0.021) — which
argues for hybrid retrieval, not for routing.

## But the interaction is real

Routing is only justified if the gap **reverses**, so the interaction is the
quantity to test, not either half:

| | |
|---|---|
| dense − RRF on short queries | **+0.061** |
| dense − RRF on long queries | **−0.092** |
| interaction | **+0.154** |
| bootstrap 95% CI | **[+0.020, +0.297]** |
| P(interaction > 0) | 98.8% |

**Established.** The reversal is not chance.

## And it is worth almost nothing

| routing rule | R@1 | vs all-RRF |
|---|---|---|
| dense when ≤3 words | 0.667 | +0.000 (**+0 questions**) |
| dense when ≤6 words | 0.693 | +0.026 (**+3 questions**) |
| dense when ≤8 words | 0.693 | +0.026 (**+3 questions**) |

A statistically real effect worth **three questions out of 114**, in exchange
for a branch in the retrieval path, a length threshold to maintain, and two
code paths to test.

**Verdict: real, and not worth shipping.** This is the distinction the session
was meant to enforce — "significant" and "worth doing" are different questions,
and this effect passes the first and fails the second.

---

# G5 — `fast_coverage` contradicts itself

Q1 established that the `covered` boolean is computed from RRF score and is
effectively always `true`. G1 established something else: the LLM, given the
same slides, often says plainly that the material does not cover the topic.

**Both ship in the same response object.**

```python
{"covered": <from RRF score>, "confidence": ..., "answer": <LLM prose>}
```

## 24 probes across four independently constructed classes

Labels are lexical — anchor terms and corpus frequency — never embedding.

| class | n | **boolean correct** | **prose correct** |
|---|---|---|---|
| known_present | 6 | **6/6** | **6/6** |
| known_absent | 10 | **0/10** | 5/10 |
| related_insufficient | 5 | **0/5** | 3/5 |
| short_ambiguous | 3 | 3/3 | 2/3 |
| **overall** | **24** | **9/24 (38%)** | **16/24 (67%)** |

**9 of 24 responses (38%) are internally contradictory** — `covered: true` while
the answer text says it is not covered. Examples: WebRTC signalling, VLAN
trunking, CAP theorem, multiversion concurrency control, database sharding, and
gradient descent asked against Computer Networks.

## What this means for the workstream

The brief said to investigate coverage signals and, if none is reliable, to say
so and move on. The result is better than that:

> **The question is not which threshold should replace the RRF gate. It is why a
> boolean is being derived from a rank score at all, when the generator has
> already produced a verdict from the evidence — and is nearly twice as accurate.**

Q8 could not find a threshold the three labelled populations agreed on. This
sidesteps the problem: the prose verdict costs **nothing** (the call already
happens), needs **no threshold**, requires **no tuning per corpus**, and scores
67% against the boolean's 38%.

The honest limit: 67% is better, not good. On `known_absent` the prose is right
only 5/10. A coverage feature built on it would still be wrong a third of the
time — but it would no longer be wrong in the specific way that tells a student
their syllabus covers **kaju katli**.

---

## Conclusion

| claim | verdict |
|---|---|
| Query-length routing has a real basis | **CONFIRMED** — interaction CI [+0.020, +0.297] |
| Query-length routing is worth shipping | **REJECTED** — +3 questions of 114 |
| RRF beats dense on real exam questions | **CONFIRMED** — p = 0.021 |
| A better coverage *threshold* exists | **REJECTED** (Q8, unchanged) |
| The `covered` boolean is trustworthy | **REJECTED** — 38%, and 0/10 on absent topics |
| The LLM's own verdict is better | **CONFIRMED** — 67% vs 38%, at zero extra cost |
| Coverage is solved by this | **NO** — 67% is an improvement, not a solution |

## Proposed production change

**None applied.** The best-evidenced candidate to emerge from the entire session
is: **derive `covered` from the answer the model already produced rather than
from `rrf_score`.** It needs no threshold, no extra call and no per-corpus
tuning, and it is measurably better than what ships today.

It still needs, before promotion:
1. a fixture set — known-present and known-absent topics — asserting that
   `covered` matches reality, which does not exist today;
2. a decision about how to extract the verdict (a regex over prose is brittle;
   asking for a structured field is cleaner but changes the prompt);
3. a larger probe set than 24.

## Threats to validity

- 24 coverage probes, 10 of them absent topics.
- The prose verdict was detected by regex over the answer text; a model that
  hedges in unusual wording would be misread. That fragility is an argument for
  a structured output field rather than for the current design.
- Runs on `llama3:8b`, not the production model.
- Routing numbers use single-gold subsets alongside a multi-gold PYQ subset;
  R@1 is not comparable *across* subsets, only within.
