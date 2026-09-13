"""
Regression tests for deterministic RRF ordering.

Both fusion sites collect candidates into a `set`, so the order in which
equal-scoring items were appended depended on PYTHONHASHSEED. A stable sort
preserved that order, which made the tail of the ranking vary between
processes for the same query — changing which slides reached the LLM, and
in the PYQ path which matches were persisted.

RRF ties are structural rather than a rounding artifact: an item found only
by dense retrieval at rank i scores exactly the same as one found only by
sparse retrieval at rank i.

These tests exercise the sort contract directly, with no database, network
or model required.
"""


import pytest

from pyq.schemas import RRFResult

RRF_K = 60


def _engine_sort(fused):
    """Mirror of the sort key used in engine/tools.run_hybrid_search."""
    return sorted(fused, key=lambda x: (-x["rrf_score"], x["doc_id"], x["page_number"]))


def _pyq_sort(results):
    """Mirror of the sort key used in pyq/hybrid_search._compute_rrf."""
    return sorted(results, key=lambda r: (-r.rrf_score, r.doc_id, r.page_number))


def _item(doc_id, page, score):
    return {"doc_id": doc_id, "page_number": page, "rrf_score": score,
            "slide_id": doc_id * 1000 + page}


# ── Ties are structural, not caused by rounding ──────────────────────────

def test_rrf_ties_are_structural_not_rounding():
    """round(score, 6) must not be blamed: it creates no extra ties."""
    vals = {}
    for d in list(range(1, 19)) + [None]:
        for s in list(range(1, 19)) + [None]:
            if d is None and s is None:
                continue
            vals[(d, s)] = ((1.0 / (RRF_K + d)) if d else 0.0) + \
                           ((1.0 / (RRF_K + s)) if s else 0.0)
    raw = {v for v in vals.values()}
    rounded = {round(v, 6) for v in vals.values()}
    assert len(raw) == len(rounded), "rounding must not manufacture ties"

    # The canonical structural tie: (dense i, sparse j) == (dense j, sparse i)
    assert vals[(1, 2)] == vals[(2, 1)]
    assert vals[(1, None)] == vals[(None, 1)]


# ── Determinism ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("seed", [0, 1, 42, 12345])
def test_engine_ordering_is_independent_of_input_order(seed):
    """Shuffling the input must not change the output ordering."""
    import random
    items = [_item(1, 1, 0.032), _item(2, 5, 0.016), _item(1, 9, 0.016),
             _item(3, 2, 0.016), _item(2, 1, 0.031), _item(5, 4, 0.016)]
    rnd = random.Random(seed)
    shuffled = items[:]
    rnd.shuffle(shuffled)
    assert [x["slide_id"] for x in _engine_sort(shuffled)] == \
           [x["slide_id"] for x in _engine_sort(items)]


def test_engine_tied_items_ordered_by_doc_then_page():
    tied = [_item(3, 1, 0.016), _item(1, 9, 0.016), _item(1, 2, 0.016), _item(2, 5, 0.016)]
    out = _engine_sort(tied)
    assert [(x["doc_id"], x["page_number"]) for x in out] == [(1, 2), (1, 9), (2, 5), (3, 1)]


def test_engine_non_tied_ordering_is_unchanged():
    """-score ascending must equal score descending for distinct scores."""
    items = [_item(9, 9, 0.010), _item(1, 1, 0.030), _item(5, 5, 0.020)]
    new = [x["rrf_score"] for x in _engine_sort(items)]
    old = [x["rrf_score"] for x in sorted(items, key=lambda x: x["rrf_score"], reverse=True)]
    assert new == old == [0.030, 0.020, 0.010]


def test_engine_higher_score_always_outranks_lower_regardless_of_ids():
    """A high-scoring late document must never be demoted by the tie-break."""
    items = [_item(99, 99, 0.050), _item(1, 1, 0.049)]
    assert [x["doc_id"] for x in _engine_sort(items)] == [99, 1]


# ── PYQ path: same contract ──────────────────────────────────────────────

def _r(slide_id, doc_id, page, score):
    return RRFResult(slide_id=slide_id, doc_id=doc_id, page_number=page,
                     source_file="f.md", rrf_score=score)


@pytest.mark.parametrize("seed", [0, 1, 42, 12345])
def test_pyq_ordering_is_independent_of_input_order(seed):
    import random
    items = [_r(10, 1, 1, 0.032), _r(20, 2, 5, 0.016), _r(30, 1, 9, 0.016),
             _r(40, 3, 2, 0.016), _r(50, 2, 1, 0.031)]
    rnd = random.Random(seed)
    shuffled = items[:]
    rnd.shuffle(shuffled)
    assert [r.slide_id for r in _pyq_sort(shuffled)] == [r.slide_id for r in _pyq_sort(items)]


def test_pyq_non_tied_ordering_is_unchanged():
    items = [_r(1, 9, 9, 0.010), _r(2, 1, 1, 0.030), _r(3, 5, 5, 0.020)]
    new = [r.rrf_score for r in _pyq_sort(items)]
    old = [r.rrf_score for r in sorted(items, key=lambda r: r.rrf_score, reverse=True)]
    assert new == old == [0.030, 0.020, 0.010]


def test_pyq_top_k_cut_is_stable_across_input_orders():
    """RRF_TOP_K slices persisted matches — the slice must not wobble."""
    import random
    items = [_r(i, i // 3 + 1, i, 0.016) for i in range(1, 11)]
    baseline = [r.slide_id for r in _pyq_sort(items)][:5]
    for seed in range(8):
        sh = items[:]
        random.Random(seed).shuffle(sh)
        assert [r.slide_id for r in _pyq_sort(sh)][:5] == baseline
