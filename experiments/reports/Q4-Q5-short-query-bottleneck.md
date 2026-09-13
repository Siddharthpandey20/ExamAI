# Q4–Q5 — The real bottleneck is short-query retrieval

**Status:** complete · **My hypothesis was rejected; what replaced it is more
useful.** Dense distance is *not* a length artifact — it honestly reports that
short queries retrieve badly. Since real traffic has a median of 5 words and 35%
of it is three words or fewer, **short-query retrieval, not confidence
estimation, is where this system loses.**

**No production code was modified.**

---

## Q4 — the hypothesis I set out to prove, and did not

> Among answerable evaluation queries, mean distance ordered monotonically by
> length — verbose 0.1313 < plain 0.1392 < keyword 0.1544 < real 0.1775 — and
> backwards from informativeness. So distance may be measuring query length,
> making a fixed threshold a length filter that penalises the short queries most
> of real traffic consists of.

**Rejected.** The controlled test says the opposite. Holding the question fixed
and appending domain-neutral English:

| padding | words | mean dense | R@1 |
|---|---|---|---|
| +0 | 15 | 0.1402 | 0.500 |
| +20 | 38 | 0.1572 | 0.450 |
| +60 | 84 | **0.1723** | 0.400 |

Padding *raises* distance. And the unanswerable control moves the same way
(0.2484 → 0.2706), so padding is not selectively flattering either class.

### But the truncation arm is the real finding

Truncating **the same questions** to their first *k* words:

| k | mean dense | R@1 | R@5 |
|---|---|---|---|
| 2 | **0.1946** | **0.100** | 0.150 |
| 3 | 0.1810 | 0.200 | 0.250 |
| 5 | 0.1626 | 0.400 | 0.550 |
| 8 | 0.1456 | 0.400 | 0.600 |
| 12 | 0.1440 | 0.500 | 0.650 |
| full (15) | 0.1402 | 0.500 | 0.700 |

Distance and recall degrade **together**. At two words the distance is 0.1946 —
above every threshold ever fitted — and R@1 is 0.100. The threshold is not
unfairly penalising short queries; **short queries genuinely fail**, and the
distance is correctly reporting it.

That is a more uncomfortable result than the confound would have been. A
confounded signal can be recalibrated. A real failure has to be fixed.

## Q5 — which retriever is failing, and why

### All of them, and at one word none of them work

Same questions, truncated, per retriever:

| query length | dense R@1 | sparse R@1 | fused R@1 | dense R@5 | sparse R@5 | fused R@5 |
|---|---|---|---|---|---|---|
| 1 word | 0.040 | 0.040 | 0.040 | 0.080 | 0.160 | 0.120 |
| 2 words | 0.080 | 0.080 | 0.080 | 0.120 | 0.120 | 0.120 |
| 3 words | 0.160 | **0.200** | **0.200** | 0.200 | 0.240 | 0.240 |
| 5 words | 0.360 | 0.280 | **0.400** | 0.520 | 0.520 | **0.600** |
| 8 words | 0.400 | 0.440 | **0.480** | 0.680 | 0.520 | 0.680 |
| full | **0.600** | 0.520 | 0.560 | 0.720 | 0.680 | **0.760** |

Two things stand out.

**Sparse does not rescue short queries.** BM25 with an exact high-IDF token
match ought to be the best case for a one-word acronym query, and it is not
better than dense. The problem is not the choice of retriever.

**Fusion is not free at full length.** Dense alone gets R@1 0.600 where RRF gets
0.560 — fusion costs a rank-1 hit on the longest queries while gaining on
medium ones. n=25, so that is one question and **not** significant; recorded as
a lead, not a finding.

### The mechanism: short queries are ambiguous, not hard

Real acronym queries, showing each retriever's top-1 slide id:

| query | subject | dense | sparse | fused | agree |
|---|---|---|---|---|---|
| **TCP** | CN | 396 | 511 | **103** | no |
| SMTP | CN | 205 | 149 | 149 | no |
| irq | CA | 215 | 210 | 215 | no |
| FIQ | CA | 215 | 210 | **210** | no |
| Waterfall model | SE | 88 | 88 | 88 | **yes** |
| is DFDs covered | SE | 84 | 84 | 84 | **yes** |

For `TCP`, the three retrievers return **three different slides**, and the fused
answer (103) is one that *neither* retriever ranked first. RRF is working as
designed — a candidate ranked second by both beats one ranked first by one — but
for a single token the ranking has no signal to work with.

`tcp` occurs **477 times** in the CN corpus. There is no correct answer to
"TCP"; hundreds of slides are equally relevant. **This is an underspecified
query, not a retrieval failure**, and no reranker, embedding model or fusion
weight can fix it. The two queries where all three retrievers agree —
`Waterfall model`, `is DFDs covered` — are the two that name something specific.

That reframes the problem. The fix for short queries is not better retrieval; it
is either disambiguation (ask what about TCP), or presenting a topic overview
rather than pretending to have found *the* answer.

### Why the evaluation set disagreed with Q4 — confirmed

`positive_verbose` had a *lower* distance than plain positives, yet Q4's neutral
padding raised it. The filler was never neutral:

| variant | words | mean dense | R@1 |
|---|---|---|---|
| plain question | 15 | 0.1419 | **0.560** |
| + `make_verbose` filler | 41 | **0.1336** | 0.400 |
| + neutral filler (same length) | 38 | 0.1572 | 0.480 |

`make_verbose`'s padding ("going through the **slides** for my **exam**… **help**
me **understand**") is pedagogical vocabulary that appears throughout slide
summaries — 95% of its tokens occur in the corpus, and crucially its *content*
words do. The neutral padding's overlap is function words only.

**The filler lowered distance while lowering R@1 (0.560 → 0.400.)** It made
queries look *more* confident while retrieving *worse*.

This is the most important line in this report for any future abstention work:
**`dense_top1` can be fooled by padding a query with corpus vocabulary.** It also
retrospectively explains the P5 verbose-query result that the circularity
warning flagged — the gain was not phrasing robustness, it was the filler
dragging the embedding toward the corpus centroid.

---

## Conclusion

| claim | verdict |
|---|---|
| Dense distance is a length artifact | **REJECTED** — padding raises it; both classes move together |
| Short queries genuinely retrieve badly | **CONFIRMED** — R@1 0.100 at 2 words, 0.200 at 3 |
| Sparse retrieval rescues short/acronym queries | **REJECTED** — no better than dense at ≤2 words |
| Short queries are a retrieval problem | **REJECTED** — they are *underspecified*; `tcp` matches 477 slides |
| `dense_top1` can be gamed by corpus-vocabulary padding | **CONFIRMED** — distance down, recall down |
| RRF fusion beats dense alone at full length | **UNCERTAIN** — 0.560 vs 0.600, n=25, one question |

## Where the bottleneck actually is

Ranked by the evidence, for real traffic:

1. **Query underspecification.** 35% of real queries are ≤3 words, where R@1 is
   0.10–0.20 and the top result is close to arbitrary. This is the largest
   single loss and it is *not* fixable inside the retrieval stack.
2. **The broken coverage gate** (Q1) — already shipping, already wrong.
3. Confidence estimation / abstention — third, not first, and undermined by the
   padding result above.

## Proposed production change

**None.** Two leads worth measuring before anything is proposed:

- **Disambiguation for short queries.** When a query is ≤3 tokens and matches a
  high-frequency corpus term, returning a topic overview or asking which aspect
  is meant would serve the student better than a confident single slide. This
  needs a UX decision, not just a measurement.
- **Fusion weighting at full length.** Dense-only beat RRF by one question.
  Worth a properly powered test; far too weak to act on.

## Threats to validity

- 25 source questions for the truncation sweep; differences below ~0.08 R@1 are
  one question.
- Truncating a question to its first *k* words is not how a student writes a
  short query — they write `TCP`, not the first two words of a sentence. The
  real acronym probes partly compensate but are only 8 queries.
- `dense_only` re-resolves slides one at a time and is not the production path;
  it is used only for ranking comparison.
