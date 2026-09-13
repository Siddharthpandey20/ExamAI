# G3/G6/G7 — Agentic RAG, iterative retrieval, and where honesty comes from

**Status:** complete · **Conclusion: agentic RAG is REJECTED as a replacement
and PROMISING for one narrow job.** It is worse at answering — correctness
0.94 vs 1.53, groundedness 0.94 vs 2.00, citations 0.1 vs 3.0 per answer, for
2.36× the tokens. But it declines on **75%** of questions the material does not
cover, where the baseline declines on **0%**.

An ablation shows that advantage is **not** reproducible with a prompt change.

**No production code was modified. Nothing was integrated.**

---

## A failed run, and why it is reported

The first attempt (G3) ran four concurrent Groq calls. The free tier 429s at
that rate, and the `chat()` helper caught the exception and returned `""`. The
output looked like a finished experiment:

```
system        correct   LLM calls   tokens
baseline         0.08        0.26      523
iterative        0.00        0.03       49
agentic          0.00        0.08       24
```

It would have been written up as *"agentic RAG does not help"*. It measured
nothing at all — every call had failed. **The tell was `llm_calls: 0.26`, when
every system makes at least one call by construction.**

G6 fixes it: strictly sequential, real backoff, failures **raise** instead of
becoming empty answers, and an assertion that each system made ≥1 call. Because
Groq's free tier made a sequential run take 643 s for a single item, G6 runs on
local Ollama (`llama3:8b`). Absolute quality is therefore lower than production
would deliver — but all three systems share the model, so the comparison, which
is the whole question, stays controlled.

---

## The three systems

| | control loop | LLM calls |
|---|---|---|
| **baseline** | none — retrieve top-6, answer | 1 |
| **iterative** | **deterministic**: if the retrieved summaries miss ≥34% of the query's content terms, re-retrieve on the missing terms and merge | 1 |
| **agentic** | LLM emits `SEARCH:` / `ANSWER:`, up to 3 searches, sees results between turns | 3 |

`iterative` exists to answer WS4 and WS10 at once: its verifier is a **set
difference**, costing microseconds. If it matches the agent, the orchestration
is buying nothing.

## Results — 17 hard queries (6 multi-slide, 4 short, 3 keyword, 4 insufficient)

| system | correct | grounded | unsupported | citations | tokens | vs baseline |
|---|---|---|---|---|---|---|
| **baseline** | **1.53** | **2.00** | 0.00 | **3.0** | 1248 | 1.00× |
| iterative | 1.47 | 1.94 | 0.00 | 3.6 | 1488 | 1.19× |
| **agentic** | **0.94** | **0.94** | 0.24 | **0.1** | 2946 | **2.36×** |

Paired, per query:

| | better | worse | tied |
|---|---|---|---|
| iterative vs baseline | 0 | 1 | 16 |
| **agentic vs baseline** | **1** | **9** | 7 |

The agent loses 9 of 17 and wins 1. It also **stops citing** — 0.1 citations per
answer against the baseline's 3.0 — which for a study tool that exists to point
students at their own slides is a serious regression on its own.

### By query kind — no class is rescued

| kind | n | baseline | iterative | agentic |
|---|---|---|---|---|
| multi_slide | 6 | **2.00** | 1.83 | 1.17 |
| short | 4 | **2.00** | 2.00 | 1.25 |
| keyword | 3 | **2.00** | 2.00 | 0.67 |
| **insufficient** | 4 | 0.00 | 0.00 | **0.50** |

Multi-hop and multi-slide questions were the strongest a-priori case for an
agent, and the agent is *worse* on them. Iterative retrieval also fails to help:
it is within noise of the baseline everywhere.

### The one place the agent wins decisively

| system | declined on absent topics | citations emitted for absent topics |
|---|---|---|
| baseline | **0/4 (0%)** | 7 |
| iterative | **0/4 (0%)** | 11 |
| **agentic** | **3/4 (75%)** | **0** |

The baseline and the deterministic controller confabulate on every single
question whose answer is not in the material, and cite slides while doing it.
The agent mostly refuses, and cites nothing.

---

## G7 — is that honesty from the architecture or from one sentence?

The comparison above was **confounded, and the confound was mine**. The agent
ran on a prompt containing:

> *"If the slides genuinely do not cover the question, say so plainly instead of
> guessing."*

while the baseline ran on the production prompt, which contains:

> *"Speak with authority as if you studied the material yourself"*

and no permission to decline at all. Attributing the difference to the
architecture without testing that would have been wrong.

G7 runs the **baseline architecture** — one retrieval, one LLM call — with the
production prompt plus a single added sentence granting permission to decline.
Nothing else changes.

| variant | correct | grounded | citations | tokens | declines on absent |
|---|---|---|---|---|---|
| production | 1.65 | **1.65** | 3.1 | 1285 | **0/4 (0%)** |
| **production + decline line** | **1.76** | 1.53 | 2.0 | 1282 | **0/4 (0%)** |
| agentic (G6) | 0.94 | 0.94 | 0.1 | 2946 | **3/4 (75%)** |

**The sentence does not reproduce it.** The decline rate stays at 0/4. It has a
smaller effect in the right direction — citations emitted for absent topics fall
from 4 to 2 — and it costs nothing on answerable questions (paired: 1 better, 0
worse, 16 tied; correctness identical at 2.15).

So the agent's honesty **is architectural**: seeing search results across turns
and being able to conclude that nothing matched is doing work that an
instruction alone does not.

**But n = 4 insufficient items.** 0/4 vs 3/4 is not significant (Fisher exact
p ≈ 0.14). This is a suggestive result on a tiny sample, and it is the single
most important thing to re-measure on a larger set.

---

## Conclusion

| claim | verdict |
|---|---|
| Agentic RAG improves answers on hard queries | **REJECTED** — −0.59 correctness, −1.06 groundedness, 9 losses to 1 win |
| It rescues multi-hop / multi-slide questions | **REJECTED** — worse on exactly those (1.17 vs 2.00) |
| It is worth 2.36× tokens | **REJECTED** for general use |
| Iterative retrieval captures the benefit more cheaply | **REJECTED** — no benefit to capture; within noise of baseline |
| A cheap deterministic verifier is enough | **REJECTED** — set-difference controller changed nothing |
| Agentic RAG is better at not-found behaviour | **PROMISING** — 75% vs 0%, but n=4 |
| That advantage is really just the prompt | **REJECTED** — the decline line alone gives 0/4 |
| The decline line is harmless on answerable questions | **CONFIRMED** — 1 better, 0 worse, 16 tied |

## Proposed production change

**None.** Two candidates worth further measurement, neither ready:

1. **The decline line.** Free, harmless on answerable questions, and it halved
   citations emitted for absent topics. It did **not** move the decline rate, so
   shipping it today would be shipping a change with no demonstrated benefit.
2. **An agent used only as a not-found detector** — never as the answer path.
   The architecture is better at recognising missing evidence and much worse at
   everything else, which argues for using it narrowly if at all. At 2.36×
   tokens for a check that fires rarely, this needs the larger sample first.

## Threats to validity

- **17 items, 4 of them insufficient.** Every number here is small-sample; the
  not-found result especially so.
- Runs on `llama3:8b` via Ollama, not the production model. A stronger model
  may follow the agent protocol better — or need it less.
- The agent's terse answers are penalised by a judge scoring completeness; some
  of the −0.59 is style, not substance.
- The judge is the same model that wrote the answers.
- G3's failure is a reminder that the harness can silently produce clean-looking
  numbers from nothing. The assertion added in G6 (`llm_calls >= 1`) should be
  standard in every future LLM experiment here.
