# R1 / R1b — the system cannot say "not found", and the fix is already in the response

**Status:** complete · **Conclusion: SUPPORTED (strongly)**

**No production code was modified.** This report is the promotion checkpoint.

---

## What was found

The system answers questions it has no evidence for, with no way to tell.

42 negative probes were built — questions whose answer is genuinely absent from
the corpus. **All 42 returned five confident-looking slides.** Including:

> *"How long should I roast a whole chicken at 180 degrees?"* → 5 slides from
> the Computer Architecture corpus.

The RRF scores were indistinguishable from real questions:

| set | mean top-1 RRF |
|---|---|
| positives (gold retrieved) | 0.0325 |
| out-of-domain | 0.0297 |
| cross-subject | 0.0309 |

### Why RRF cannot detect this

Structural, not a tuning problem. RRF scores a **rank**: `1/(60 + rank)`. The
top hit contributes the same `1/61` whether the match is perfect or absurd. The
similarity *magnitude* is discarded during fusion, so no threshold on an RRF
score can ever recover it. This explains R3's negative result completely.

---

## The signal that does work

ChromaDB already returns the magnitude as `distances`, and
`run_hybrid_search` **reads `ids` and `metadatas` and ignores `distances`.**

| group | n | mean top-1 cosine distance | range |
|---|---|---|---|
| **positive** | 40 | **0.1392** | 0.0866 – **0.1939** |
| out_of_domain | 12 | 0.2564 | **0.1977** – 0.3142 |
| cross_subject | 30 | 0.2297 | 0.1675 – 0.2632 |

- **Leave-one-out accuracy 0.976** against a 0.512 majority baseline, **+0.463**
- Standardised separation **+1.79**
- The positive and out-of-domain ranges **do not overlap**: 0.1939 vs 0.1977
- Fitted rule: *answerable when top-1 distance ≤ 0.194*

Compare against R3, where the best honest signal for the same decision gained
**one question in forty**. This gains 38 of 82.

---

## Honest limitations

1. **The threshold is fitted on this corpus.** LOOCV validates the *method* at
   0.976; it does not prove 0.194 transfers to a different corpus, embedding
   model, or subject mix. Any production use should treat the constant as
   corpus-specific and re-derive it.
2. **These are mostly easy negatives.** Out-of-domain questions are far from the
   corpus by construction. The harder case — a question about a subject the
   corpus *does* cover but a detail it happens to omit — is under-represented,
   and 30 cross-subject probes already sit closer to the boundary (min 0.1675)
   than any out-of-domain probe.
3. **n = 82.** Adequate for a separation this large, not for fine tuning.
4. Two of 82 are misclassified under LOOCV; the method is not perfect.

---

## Proposed production change — FOR APPROVAL, NOT APPLIED

**Smallest version, two steps, both additive.**

**Step 1 — stop discarding the signal.** In `engine/tools.py`,
`run_hybrid_search` already receives `distances` from `chroma.query`. Capture the
per-slide distance and attach it to each fused result as `dense_distance`,
alongside the existing `rrf_score`. Nothing else changes: ordering, filtering
and the returned slides stay exactly as they are. This is observable-only and
cannot alter retrieval behaviour.

**Step 2 — a grounded not-found response**, only after step 1 has been measured
in place. In `engine/fast_mode.py`, when the best `dense_distance` exceeds the
threshold, return the existing "no relevant slides found" shape rather than
sending weak evidence to the LLM. `fast_coverage` already has the right
vocabulary for this.

**Files that would change:** `engine/tools.py` (step 1);
`engine/fast_mode.py` + `engine/config.py` (step 2).

**Risk.** Step 1: negligible, additive field. Step 2: a false abstention makes
the system refuse a question it could have answered — the failure mode the
checklist explicitly warns about ("a system that says not found for everything
is NOT an improvement"). Mitigation: the measured positive maximum is 0.1939, so
a threshold set with margin above it abstains on none of the 40 known-answerable
questions.

**Rollback.** Step 1: revert one commit; no stored state changes. Step 2: a
config constant set high enough disables abstention without a code change.

**Recommended sequencing.** Promote step 1 alone, confirm the distances look as
expected in real traffic, and only then decide on step 2. Step 1 is also what
makes R3/R4/R5 answerable, since it exposes the signal those experiments need.

---

## Artefacts

- `experiments/rag/r1_negative_probes.py` — builds and verifies the negatives
- `experiments/rag/r1b_raw_similarity.py` — the separation measurement
- `experiments/benchmarks/r1_negative_probes.json` — 42 probes, each with its
  verification record
- `experiments/benchmarks/r1b_raw_similarity.json` — per-question distances

The negatives need no human adjudication: their label is *absence*, and each
cross-subject probe was accepted only after checking its concepts do not occur
in the target subject (96 candidates were discarded for exactly that reason).
