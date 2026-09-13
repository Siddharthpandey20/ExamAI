# G2 — Fusion, candidate pools, context depth, and routing

**Status:** complete · **Mostly negative, which is the useful part.** The
existing retrieval configuration is close to optimal on every axis tested, and
four plausible improvements are now ruled out with measurements. The single
positive signal is **query-length routing**, where the ordering of dense and
hybrid retrieval *reverses*.

**No production code was modified.** Retrieval-only, deterministic, no LLM.

114 items: 40 generated eval questions, 40 keyword-style phrasings, 34
independent PYQ exam questions with lexically assigned gold sets.

---

## Fusion method — RRF is already the right choice

| config | R@1 | R@3 | R@5 | MRR | nDCG@5 |
|---|---|---|---|---|---|
| **RRF K=60 (production)** | **0.667** | 0.763 | 0.816 | **0.723** | 0.717 |
| dense only | 0.640 | 0.728 | 0.754 | 0.687 | 0.679 |
| sparse only | 0.640 | 0.737 | 0.798 | 0.696 | 0.704 |
| weighted dense=0.7 | 0.640 | **0.789** | **0.833** | 0.717 | 0.719 |
| weighted dense=0.9 | 0.667 | 0.772 | 0.825 | **0.724** | **0.723** |

Weighted fusion — which *keeps* the score magnitude RRF discards — matches RRF
at best (+0.001 MRR at w=0.9, which is the weighting that nearly ignores sparse).
The hypothesis that preserving magnitude would help is **rejected**.

Both single retrievers are worse than the fusion, so hybrid retrieval is
earning its place.

## RRF K — the parameter does not matter here

| K | 1 | 3 | 5 | 10 | 20 | **60** | 120 |
|---|---|---|---|---|---|---|---|
| R@1 | 0.658 | 0.649 | 0.667 | 0.667 | 0.667 | **0.667** | 0.667 |
| MRR | 0.717 | 0.708 | 0.722 | 0.721 | 0.722 | **0.723** | 0.723 |

My hypothesis was that K=60 — a value tuned for TREC runs with hundreds of
candidates — over-flattens a 15-candidate list. **Rejected.** The metric is flat
from K=5 to K=120; only K=1 and K=3 are slightly worse. K=60 needs no change,
and more importantly **no one should spend time tuning it**.

## Candidate pool — flat from 5 to 120

| fetch_n | 5 | 10 | **15** | 30 | 60 | 120 |
|---|---|---|---|---|---|---|
| R@1 | 0.667 | 0.667 | **0.667** | 0.667 | 0.667 | 0.667 |
| MRR | 0.716 | 0.720 | **0.723** | 0.723 | 0.723 | 0.723 |

Enlarging the pool 8× changes nothing. The gold slide is either in the first few
candidates or not in the list at all. **Rejected.**

## Context depth — production's top-6 is a sensible point

| option | gold in context | slides | ~tokens |
|---|---|---|---|
| top 3 | 0.763 | 3.0 | 378 |
| top 5 | 0.816 | 5.0 | 624 |
| **top 6 (production)** | **0.842** | 6.0 | 743 |
| top 8 | 0.842 | 8.0 | 978 |
| top 10 | 0.860 | 10.0 | 1213 |
| top 5 + adjacent pages | 0.833 | 12.0 | 1443 |
| top 6 + adjacent pages | 0.860 | 14.1 | 1693 |

Two results:

- **Adjacent-slide expansion is dominated.** `top 6 + adjacent` reaches 0.860
  using 14.1 slides and 1693 tokens; plain `top 10` reaches the *same* 0.860
  with 10 slides and 1213 tokens. Adding neighbours costs 40% more context for
  no recall. **Rejected** — the intuition that slide N±1 continues the topic
  does not pay.
- top 6 → top 10 buys +0.018 gold-in-context for +63% tokens. Defensible either
  way; not an improvement worth claiming.

Given G1 showed correctness is bounded by whether gold reaches the context, the
ceiling here matters: **even at top-10 the gold slide is absent 14% of the
time.** That is the headroom, and no context-packing option recovers it.

---

## Routing — the one positive signal

| subset | n | RRF K=60 | dense only | weighted 0.7 |
|---|---|---|---|---|
| all | 114 | 0.667 / 0.723 | 0.640 / 0.687 | 0.640 / 0.717 |
| **short (≤6 words)** | 49 | 0.633 / 0.709 | **0.694 / 0.715** | 0.653 / 0.711 |
| **long (>6 words)** | 65 | **0.692 / 0.733** | 0.600 / 0.666 | 0.631 / 0.721 |
| independent PYQ | 34 | **0.706 / 0.744** | 0.471 / 0.575 | 0.676 / 0.748 |

*(cells are R@1 / MRR)*

The interesting feature is not that one retriever wins — it is that **the
ordering reverses with query length**. Dense-only is better on short queries
(+0.061 R@1) and much worse on long ones (−0.092), and catastrophically worse on
real exam questions (−0.235).

There is a mechanism behind it, established in Q5: a one-token query gives BM25
nothing to discriminate with (`tcp` matches 477 slides equally), while a long
question gives it many terms. A reversal with a mechanism is more credible than
a bare difference — but 0.694 vs 0.633 on 49 items is three questions, so it is
tested separately in G4 before being called a finding.

---

## Conclusion

| hypothesis | verdict |
|---|---|
| Weighted fusion beats RRF by keeping score magnitude | **REJECTED** — ties at best |
| RRF K=60 is mistuned for short candidate lists | **REJECTED** — flat K=5…120 |
| A larger candidate pool helps | **REJECTED** — flat to fetch_n=120 |
| Adjacent-slide expansion helps | **REJECTED** — dominated by plain top-10 |
| More context helps | **MARGINAL** — +0.018 for +63% tokens |
| Hybrid beats either retriever alone | **CONFIRMED** |
| Query length should route retrieval strategy | **PROMISING** — see G4 |

## Proposed production change

**None from this phase.** Four tuning avenues are now closed, which is worth
recording explicitly: nobody should spend time on RRF K, pool size, fusion
weights or neighbour expansion. The only live candidate is routing, and it needs
the significance test in G4 first.

## Threats to validity

- 114 items across three sets with different construction; the independent PYQ
  subset is 34 items with multi-slide gold sets, so its R@1 is not comparable to
  the single-gold subsets.
- Retrieval metrics only. G1 showed correctness tracks gold-in-context, so
  recall is a reasonable proxy — but a context change that alters *ordering*
  could affect the answer without moving recall, and that is not measured here.
- The context-cost column estimates tokens as chars/4.
