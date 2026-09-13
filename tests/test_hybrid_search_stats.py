"""
Tests for the `stats` observability out-parameter on run_hybrid_search.

The parameter exists because RRF discards the one signal that distinguishes a
good match from a hopeless one: RRF scores a *rank*, 1/(RRF_K + rank), so the
top fused hit scores ~0.0328 whether the nearest slide is a perfect match or
absurd. ChromaDB already computes the cosine distance and the fusion threw it
away.

The overriding requirement is that adding it changed NOTHING. In particular it
is an out-parameter rather than an extra key on the returned dicts, because
engine/reasoning_mode.py serialises those dicts straight into an LLM prompt —
a new key there would silently alter production prompt content. The first two
tests are the ones that matter; the rest check the values are actually right.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from engine.tools import run_hybrid_search, reset_bm25_cache
from indexing.models import Base, Document, Slide

SUBJECT = "CN"


class _StubEmbedder:
    def embed_query(self, text):
        return [0.0] * 8


class _StubChroma:
    """Stub Chroma. `distances` is optional so both client shapes are covered."""

    def __init__(self, ids, distances=None):
        self._ids = ids
        self._distances = distances

    def query(self, query_embedding, n_results=10, where=None):
        ids = self._ids[:n_results]
        out = {"ids": [ids], "metadatas": [[{"source_file": "x.md"} for _ in ids]]}
        if self._distances is not None:
            out["distances"] = [self._distances[:n_results]]
        return out


@pytest.fixture()
def session(tmp_path):
    reset_bm25_cache()
    engine = create_engine(f"sqlite:///{tmp_path / 'stats.db'}")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()
    reset_bm25_cache()


def _seed(session, pages=4, substantive_pages=None):
    doc = Document(filename="CN1.md", original_filename="CN1.pdf",
                   file_hash="hCN1", status="processed", subject=SUBJECT)
    session.add(doc)
    session.flush()
    for p in range(1, pages + 1):
        if substantive_pages is not None and p not in substantive_pages:
            # Heading-only slide: filtered out by is_substantive.
            session.add(Slide(doc_id=doc.id, page_number=p, subject=SUBJECT,
                              slide_type="other", summary="Ch", concepts="",
                              chapter="ch", raw_text="Ch", is_embedded=True,
                              importance_score=0.1))
            continue
        session.add(Slide(
            doc_id=doc.id, page_number=p, subject=SUBJECT, slide_type="concept",
            summary=f"CN summary {p} with plenty of substantive words here",
            concepts="tcp, udp", chapter="ch",
            raw_text=f"CN body text page {p} describing transport protocols marker{p}",
            is_embedded=True, importance_score=0.5))
    session.commit()
    return doc.id


# ── the two that actually guard production ───────────────────────────────

def test_omitting_stats_leaves_results_byte_identical(session):
    """The default path must be indistinguishable from before the change."""
    did = _seed(session)
    ids = [f"doc{did}_page{p}" for p in (1, 2, 3)]
    dists = [0.11, 0.22, 0.33]

    without = run_hybrid_search("transport protocols", SUBJECT, session,
                                _StubEmbedder(), _StubChroma(ids, dists), top_k=6)
    collected = {}
    with_stats = run_hybrid_search("transport protocols", SUBJECT, session,
                                   _StubEmbedder(), _StubChroma(ids, dists),
                                   top_k=6, stats=collected)

    assert without == with_stats, "passing stats must not change the results"
    assert collected, "stats dict should have been populated"


def test_returned_dicts_gain_no_new_keys(session):
    """reasoning_mode json.dumps()es these dicts into an LLM prompt.

    A stray key would change production prompt content, which is exactly the
    silent behaviour change this design avoids.
    """
    did = _seed(session)
    chroma = _StubChroma([f"doc{did}_page{p}" for p in (1, 2)], [0.1, 0.2])
    out = run_hybrid_search("transport", SUBJECT, session, _StubEmbedder(),
                            chroma, top_k=6, stats={})
    assert out
    for row in out:
        assert "distance" not in row
        assert "dense_distance" not in row
        assert "dense_top1" not in row


# ── the values are correct ───────────────────────────────────────────────

def test_stats_reports_nearest_distance(session):
    did = _seed(session)
    chroma = _StubChroma([f"doc{did}_page{p}" for p in (1, 2, 3)],
                         [0.1234, 0.4567, 0.6789])
    stats = {}
    run_hybrid_search("transport", SUBJECT, session, _StubEmbedder(), chroma,
                      top_k=6, stats=stats)
    assert stats["dense_top1"] == pytest.approx(0.1234)
    assert stats["dense_min"] == pytest.approx(0.1234)
    assert stats["dense_mean"] == pytest.approx((0.1234 + 0.4567 + 0.6789) / 3)
    assert stats["n_dense"] == 3
    assert stats["n_returned"] == len(
        run_hybrid_search("transport", SUBJECT, session, _StubEmbedder(),
                          chroma, top_k=6))


def test_missing_distances_from_chroma_is_not_an_error(session):
    """Some Chroma client versions omit `distances`. That must degrade, not crash."""
    did = _seed(session)
    chroma = _StubChroma([f"doc{did}_page{p}" for p in (1, 2)])  # no distances
    stats = {}
    out = run_hybrid_search("transport", SUBJECT, session, _StubEmbedder(),
                            chroma, top_k=6, stats=stats)
    assert out
    assert stats["dense_top1"] is None
    assert stats["dense_mean"] is None
    assert stats["n_dense"] == 2


def test_top_result_distance_differs_from_dense_top1_when_nearest_is_filtered(session):
    """The nearest slide is not always the one returned first.

    Page 1 is the closest dense hit but is heading-only, so is_substantive drops
    it. dense_top1 must still report the raw nearest distance while
    top_result_distance reports the slide the user actually sees — conflating
    the two would mean thresholding on a slide that was never shown.
    """
    did = _seed(session, pages=3, substantive_pages={2, 3})
    chroma = _StubChroma([f"doc{did}_page{p}" for p in (1, 2, 3)],
                         [0.05, 0.40, 0.60])
    stats = {}
    out = run_hybrid_search("transport", SUBJECT, session, _StubEmbedder(),
                            chroma, top_k=6, stats=stats)
    assert out, "substantive slides should still be returned"
    assert 1 not in {r["page_number"] for r in out}
    assert stats["dense_top1"] == pytest.approx(0.05)
    assert stats["top_result_distance"] != pytest.approx(0.05)


def test_stats_dict_is_caller_owned(session):
    """Two searches must not share state - the Celery pool runs threads."""
    did = _seed(session)
    chroma_a = _StubChroma([f"doc{did}_page1"], [0.10])
    chroma_b = _StubChroma([f"doc{did}_page2"], [0.90])
    a, b = {}, {}
    run_hybrid_search("transport", SUBJECT, session, _StubEmbedder(), chroma_a,
                      top_k=6, stats=a)
    run_hybrid_search("transport", SUBJECT, session, _StubEmbedder(), chroma_b,
                      top_k=6, stats=b)
    assert a["dense_top1"] == pytest.approx(0.10)
    assert b["dense_top1"] == pytest.approx(0.90)


def test_empty_subject_populates_stats_without_crashing(session):
    _seed(session)
    stats = {}
    out = run_hybrid_search("anything", "NOSUCH", session, _StubEmbedder(),
                            _StubChroma([], []), top_k=5, stats=stats)
    assert out == []
    assert stats["dense_top1"] is None
    assert stats["top_result_distance"] is None
    assert stats["n_returned"] == 0
