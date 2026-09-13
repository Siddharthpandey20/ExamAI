# Steps 0–2 — negation eval coverage, dense_top1 plumbing, generalization

**Status:** complete · **Production behaviour unchanged.** One production file was
modified (`engine/tools.py`) to add an opt-in observability parameter that is
inert by default, proven both by unit tests and by a byte-identical replay of
250 real retrievals. 252/252 tests pass.

No abstention was implemented. No rewriting was implemented. No threshold was
promoted. `0.194` is not used anywhere.

---

## Step 0 — the evaluation blind spot

P5 verified that `content_only` inverts negated questions, and that **no metric
in the project could see it**: not one of the 250 eval items contained a
negation. Fixing the transform's word list without fixing the eval set would
have moved the blind spot rather than closing it.

Two constructions, deliberately different in kind:

**Retrieval items (40).** Negated phrasings of the existing questions, gold slide
unchanged. The stated assumption is recorded in the generator: *the label
answers "which slide holds the evidence", and negating a question does not move
the evidence.* "What does TCP guarantee?" and "What does TCP not guarantee?" are
answered from the same slide.

**Minimal pairs (40).** An affirmative and a negated form differing by one
inserted word, carrying no gold slide at all. This is a **property test, not a
measurement**: a transform that maps both members to the same string has
provably destroyed a distinction, and no balanced-accuracy number rehabilitates
that.

The distinction matters. Retrieval metrics can only show that negation handling
is *mediocre*; a minimal pair shows that it is *wrong*.

A first attempt built the negated questions from the first N content words,
which produced word salad ("Why is you UDP TCP handle process sending not always
the right choice?"). That would have measured the extractor rather than
negation, so extraction was rewritten to prefer acronyms and technical nouns.

## Step 1 — observability plumbing

`run_hybrid_search` computed Chroma's `distances` and threw them away. It now
accepts an optional `stats` dict:

```python
run_hybrid_search(q, subject, session, embedder, chroma, stats=collected)
# collected["dense_top1"], ["dense_mean"], ["top_result_distance"], ...
```

### Why an out-parameter rather than a key on the result dicts

The obvious design — add `dense_distance` to each returned slide dict — would
have been a **silent production behaviour change**. `engine/reasoning_mode.py`
does `json.dumps(results)` and feeds the result straight to the LLM as tool
output, so a new key would alter production prompt content and token usage.
An out-parameter touches nothing when omitted. It is also caller-owned, so
concurrent searches on the Celery thread pool share no state.

`top_result_distance` is reported separately from `dense_top1` on purpose: the
nearest slide is not always the one returned first, because it may be filtered
as non-substantive or outranked by a candidate both retrievers found.
Conflating them would mean thresholding on a slide the user never saw. There is
a test for exactly this.

### Proof that it changed nothing

| check | result |
|---|---|
| 7 new unit tests (identity, no new keys, missing-distances, caller-owned) | pass |
| Full suite | **252/252** (245 before + 7 new) |
| **Replay of 250 real items: retrieved slide ids** | **0 differences** |
| Replay: hit@1 | 0 differences |
| Replay: dense_top1 vs the old separate probe query | 0 differences |

The last row also retires a latent risk: earlier scripts issued their *own*
Chroma query to obtain distances, so every threshold number depended on that
probe being identical to the query inside `run_hybrid_search`. It was — but it
was never checked, and it no longer has to be.

## Step 2 — does the threshold generalize?

### It transfers across subjects

Leave-one-subject-out: fit on all subjects but one, test on the held-out subject.

| held out | n | T fitted elsewhere | bal.acc held out | T refitted here | gap |
|---|---|---|---|---|---|
| CN | 120 | 0.1768 | 0.868 | 0.1736 | +0.041 |
| DAA | 38 | 0.1808 | 0.863 | 0.1646 | +0.057 |
| DBMS | 50 | 0.1793 | 0.929 | 0.1703 | +0.000 |
| ML | 44 | 0.1793 | 0.933 | 0.1749 | +0.000 |

Threshold fitted on other subjects: **0.1791 ± 0.0014**. Mean cost of not having
the held-out subject's data: **+0.024**. The value is a property of the embedding
space, not of one subject's vocabulary.

### It does not transfer across question types

The 40 negation items did not exist when 0.1768 was fitted, so applying it to
them is a genuine out-of-sample test:

| question type | n | refused at T=0.1793 |
|---|---|---|
| positive_verbose | 40 | 0.0% |
| positive | 40 | 2.5% |
| positive_noisy | 40 | 5.0% |
| positive_keyword | 40 | 25.0% |
| **positive_negation** | 40 | **37.5%** |

Negated questions retrieve worse (R@1 0.725 → **0.475**) and sit much further
away (mean distance 0.1392 → **0.1763**, against 0.2022 for questions whose
answer is genuinely absent). **70% of negation items sit at or beyond the
closest unanswerable question.** To the embedding, an answerable-but-negated
question looks much like a question about material that is not there.

Adding one realistic question type dropped balanced accuracy from **0.948 to
0.914**, and refitting recovers almost none of it — at the refitted 0.1793,
37.5% of negation items are still refused.

### The pattern

Each realistic question type added to the evaluation set has lowered the
measured performance: keyword 25% refused, negation 37.5%. The headline 0.941
is a function of **which phrasings happen to be in the eval set**, and there is
no reason to think the set is finished. This is the strongest argument against
promoting any threshold on current evidence.

---

## Correction to an earlier reported number

Earlier reports cited hybrid retrieval latency as **p50 ≈ 31 ms**. Measured now
on the same machine, it is **p50 ≈ 90–98 ms**, and the split is:

| stage | p50 |
|---|---|
| `embed_query` alone | 69.8 ms |
| full `run_hybrid_search` | 97.6 ms |

I could not reproduce the 31 ms figure and could not explain the gap — the
embedder is confirmed on CUDA with 5 GB free, and replicating the old script's
call pattern exactly still yields 98 ms. Treat 31 ms as unreliable rather than
as a regression; the plumbing change adds only a dict build over ~15 items.

The robust and useful fact is the **split**: roughly **71% of retrieval latency
is the query embedding**, not the search. That strengthens the P6 rejection of
conditional retry considerably — a second pass costs another ~70 ms embedding,
not a cheap re-rank.

## Conclusion

| claim | verdict |
|---|---|
| The eval set could not see the negation defect | **CONFIRMED** — now it can |
| The plumbing is inert by default | **CONFIRMED** — 0 differences on 250 real items |
| Threshold generalizes across subjects | **CONFIRMED** — 0.1791 ± 0.0014 |
| Threshold generalizes across question types | **REJECTED** — 37.5% refusal on negation |
| Ready to promote a threshold | **NO**, and further from it than before |

## Proposed production change

**None.** Step 1 is already in the tree as an inert capability; it gates nothing
and is read by no production code path. Steps 3–4 from the earlier checkpoint
are further away than they looked, because the measured performance of the
abstention rule fell every time the evaluation became more realistic.
