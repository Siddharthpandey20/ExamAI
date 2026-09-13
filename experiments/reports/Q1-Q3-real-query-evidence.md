# Q1–Q3 — Real-query observability, and what real queries reveal

**Status:** complete · **Two findings, both consequential.**

1. **A production confidence gate is broken.** `fast_coverage` reports
   `covered: true` for **31/31** real user queries, including "kaju katli" (an
   Indian sweet) asked against the ML corpus. Its `"low"` branch is
   mathematically unreachable.
2. **The abstention proposal is not viable on current evidence.** At the fitted
   threshold, **52% of genuinely answerable real queries would be refused** —
   against 2.5% on the generated evaluation set.

Production retrieval behaviour is unchanged. Observability was added and proven
inert: 290/290 replayed queries return identical results; 267/267 tests pass.

---

## Q1 — the coverage gate that is already in production

`engine/fast_mode.py::fast_coverage` classifies coverage like this:

```python
top_score = slides[0].get("rrf_score", 0)
if   top_score > 0.025: confidence = "high"
elif top_score > 0.015: confidence = "medium"
else:                   confidence = "low"
...
"covered": confidence in ("high", "medium")
```

That boolean is returned to the student, and the string is also interpolated
into the LLM prompt (`Match confidence: high (top RRF score 0.0328)`).

### The arithmetic makes it a near-constant

RRF scores a rank: `1/(RRF_K + rank)` with `RRF_K = 60`. A rank-1 hit therefore
contributes exactly `1/61 = 0.01639`.

| how the top slide was found | score | label | covered |
|---|---|---|---|
| both retrievers, rank 1 | 0.03279 | high | **true** |
| one retriever, rank 1 | 0.01639 | medium | **true** |
| `"low"` requires ≤ 0.015 | — | unreachable for any rank-1 hit | — |

`covered` is `false` only when the result list is *empty*. The gate is not
measuring coverage; it is measuring **whether dense and sparse retrieval
happened to agree** — and reporting that to the student as a judgement about
their own study material.

### Confirmed on 31 real queries

| query | subject | rrf | confidence | covered | dense_top1 | top slide returned |
|---|---|---|---|---|---|---|
| **kaju katli** | ML | 0.01639 | medium | **true** | 0.2986 | "title slide for the topic The Error term" |
| **kaju katli** | CA | 0.01639 | medium | **true** | 0.2775 | "title slide introducing the Thumb instruction set" |
| **ARQ** | CA | 0.01639 | medium | **true** | 0.2429 | — |
| **linear regression** | CA | 0.03227 | high | **true** | 0.2345 | "teaching plan for the Computer Architecture course" |
| **Linear Algebra** | CN | 0.02874 | high | **true** | 0.1885 | "transition from TCP slow start to congestion avoidance" |

`covered=True` for **31/31**. Labels produced: 27 high, 4 medium, **0 low**.

**The signal that would fix it is already computed and was being discarded.**
`dense_top1` puts the four nonsense queries at 0.2060–0.2986 while real
answerable ones sit at 0.1254–0.1627. That is exactly the separation the earlier
phases measured — and exactly why the `stats` plumbing was added.

## Q2 — the observability change is inert

| check | result |
|---|---|
| Retrieval identity, 290 real replayed items | **0 differences** |
| Full test suite | **267 passed** (252 + 15 new) |
| Retrieval p50, observation **off** | 88.60 ms |
| Retrieval p50, observation **on** | 87.41 ms (within noise) |
| The append alone | 2.216 ms p50 — **2.5%** of one retrieval |
| Raw query text in log | **none** |
| Filenames / slide text in log | **none** |

The module records a truncated SHA-256 of the normalised query plus structural
features (length, question mark, acronym count, keyword shape), never the text.
Failures are swallowed: an unwritable log, a full disk, or an unserialisable
field cannot propagate to the caller. There is a test for each, because the
failure mode being prevented is *a student losing an answer because a log file
could not be appended to*.

The 2.2 ms append is real but small against an 88 ms retrieval and a
~1800 ms LLM call. Not optimised further; buffering would add a flush-on-crash
failure mode for no meaningful gain.

## Q3 — where real queries actually land

31 distinct free-text queries from `query_cache`, typed between 2026-03-09 and
2026-04-06 — before this work began, so uninfluenced by it. Nothing fabricated.

### Labels are lexical, and the first rule was wrong

A first pass labelled on the single rarest term and got two wrong. Recording
this because the same brittleness would have corrupted the headline:

- *"reliably send emails application"* → CN was called unanswerable because
  `emails` occurs 0×. `email` occurs 24× and `e-mail` 49×. A plural, not an
  absence.
- *"...difference b/w imap and ftp? why we need pop3?"* was called unanswerable
  because `pop3` occurs 0×, though `imap` occurs 40× and ftp is covered. One
  uncovered clause does not make a multi-part question unanswerable.

The corrected rule uses coverage over **all** content terms with light
morphology, and excludes three app-generated prompts that are not student
questions. Still purely lexical, still independent of any embedding.

### The distributions

| population | n | mean | p10 | p50 | p90 |
|---|---|---|---|---|---|
| eval: plain positives (generated) | 40 | 0.1392 | 0.1165 | 0.1371 | 0.1686 |
| eval: all answerable | 200 | 0.1479 | 0.1154 | 0.1429 | 0.1893 |
| eval: keyword-style positives | 40 | 0.1544 | 0.1160 | 0.1543 | 0.2030 |
| independent PYQ: answerable | 34 | 0.1642 | 0.1277 | 0.1669 | 0.2002 |
| **REAL QUERIES: answerable** | **21** | **0.1775** | **0.1336** | **0.1793** | **0.2056** |
| | | | | | |
| eval: unanswerable | 90 | 0.2182 | 0.1903 | 0.2174 | 0.2555 |
| independent PYQ: unanswerable | 34 | 0.2234 | 0.1981 | 0.2230 | 0.2571 |
| REAL QUERIES: unanswerable | 4 | 0.2562 | 0.2060 | 0.2775 | 0.2986 |

Real answerable queries sit **+0.038 further out** than generated plain
positives, and their median (0.1793) lands *exactly on* the threshold fitted
from the evaluation data (0.1768–0.1793).

### Why: students do not type the way the eval set does

| population | n | median words | ≤3 words | ≤6 words |
|---|---|---|---|---|
| **REAL user queries** | 31 | **5** | **35%** | **65%** |
| eval plain positives | 40 | 13 | 2% | 18% |

Real queries are `TCP`, `SMTP`, `irq`, `FIQ`, `ARQ`, `Waterfall model`,
`is DFDs covered`. The evaluation set is full of 13-word generated questions.
Two thirds of real traffic is the **keyword shape** that every phase measured as
the hardest case.

### What a threshold would have done to real traffic

| T | answerable refused | unanswerable caught |
|---|---|---|
| 0.1650 | **13/21 = 62%** | 4/4 = 100% |
| **0.1768** | **11/21 = 52%** | 4/4 = 100% |
| **0.1793** | **11/21 = 52%** | 4/4 = 100% |
| 0.1900 | 7/21 = 33% | 4/4 = 100% |
| 0.2100 | 2/21 = 10% | 3/4 = 75% |

**Refusing half of all answerable questions is unshippable.** The evaluation set
predicted 2.5% false abstention for plain positives; real traffic gives 52%.

---

## Conclusion

| claim | verdict |
|---|---|
| `fast_coverage`'s confidence gate works | **REJECTED** — `covered=true` 31/31; `"low"` unreachable |
| Dense distance separates real nonsense from real questions | **SUPPORTED** — 0.206–0.299 vs 0.125–0.163 |
| The fitted threshold (0.1768–0.1793) is usable | **REJECTED** — 52% false abstention on real traffic |
| Generated evaluation sets predict real behaviour | **REJECTED** — real queries sit +0.038 further out |
| Observability is inert | **CONFIRMED** — 0/290 differences, 2.2 ms, no text logged |

## Proposed production change

**None yet**, but the priority order has changed. The most defensible candidate
is no longer "add abstention" but **"fix the coverage gate that already exists
and is wrong."** That is repairing a broken feature rather than adding a new
one, and the evidence for it is much stronger:

- the current gate's output is a near-constant `true`
- the four genuinely nonsense real queries are the four highest distances
  observed (0.2060, 0.2429, 0.2775, 0.2986)
- a `covered` decision is a much safer place for a distance test than an
  answer-suppressing abstention gate, because the user still receives the
  slides and the LLM's explanation either way

That is **not** a proposal to ship a threshold today. n=4 unanswerable real
queries cannot support fitting one. It is a statement about where the next
evidence should be gathered.

## Threats to validity

- 31 queries from one user over four weeks. Only 4 are lexically unanswerable.
- Labels are lexical coverage; a question answerable by material that uses
  different wording would be mislabelled, and the first version of the rule
  demonstrably made that error twice.
- `query_cache` holds only queries that reached an endpoint and were cached;
  queries that errored or were abandoned are invisible.
- One user, one corpus, one embedding model.
