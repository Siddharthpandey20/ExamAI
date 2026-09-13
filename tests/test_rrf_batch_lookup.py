"""
Semantics tests for the batched RRF candidate lookup.

The fusion loop used to issue one Slide query and one Document query per
fused candidate — roughly 72 queries for a 36-candidate fusion. They are now
resolved in two batch queries.

The batch must preserve the previous behaviour exactly:
  - slides are matched on (doc_id, page_number) with NO subject filter,
    which is deliberate: the unfiltered dense fallback is a documented gap
    (see test_security_regression) and tightening it here would be a silent
    behaviour change;
  - a candidate with no matching slide row is skipped;
  - a slide whose Document row is missing still yields doc=None, which
    slide_to_dict renders as an empty filename;
  - non-substantive slides are still filtered out;
  - ordering is unaffected, because the final sort is total.

Driven with a stub embedder and stub Chroma so the fusion path is exercised
without a GPU, a model or a vector store.
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
    """Returns a fixed dense ranking of chroma ids."""

    def __init__(self, ids):
        self._ids = ids
        self.last_where = None

    def query(self, query_embedding, n_results=10, where=None):
        self.last_where = where
        ids = self._ids[:n_results]
        return {"ids": [ids], "metadatas": [[{"source_file": "x.md"} for _ in ids]]}


@pytest.fixture()
def session(tmp_path):
    reset_bm25_cache()
    engine = create_engine(f"sqlite:///{tmp_path / 'rrf.db'}")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()
    reset_bm25_cache()


def _seed(session, subject=SUBJECT, doc_id_hint=1, pages=4, with_doc=True):
    doc = None
    if with_doc:
        doc = Document(filename=f"{subject}{doc_id_hint}.md",
                       original_filename=f"{subject}{doc_id_hint}.pdf",
                       file_hash=f"h{subject}{doc_id_hint}", status="processed",
                       subject=subject)
        session.add(doc)
        session.flush()
    did = doc.id if doc else 999
    for p in range(1, pages + 1):
        session.add(Slide(
            doc_id=did, page_number=p, subject=subject, slide_type="concept",
            summary=f"{subject} summary {p} with plenty of substantive words here",
            concepts="tcp, udp", chapter="ch",
            raw_text=f"{subject} body text page {p} describing transport protocols",
            is_embedded=True, importance_score=0.5))
    session.commit()
    return did


def test_normal_retrieval_returns_expected_slides(session):
    did = _seed(session)
    chroma = _StubChroma([f"doc{did}_page{p}" for p in (1, 2, 3)])
    out = run_hybrid_search("transport protocols", SUBJECT, session,
                            _StubEmbedder(), chroma, top_k=6)
    assert out
    assert all(r["doc_id"] == did for r in out)
    assert {r["page_number"] for r in out} >= {1, 2, 3}


def test_missing_slide_rows_are_skipped(session):
    """A dense hit pointing at a slide that no longer exists must be dropped."""
    did = _seed(session, pages=2)
    chroma = _StubChroma([f"doc{did}_page1", f"doc{did}_page404", "doc777_page1"])
    out = run_hybrid_search("transport", SUBJECT, session,
                            _StubEmbedder(), chroma, top_k=6)
    pages = {(r["doc_id"], r["page_number"]) for r in out}
    assert (did, 404) not in pages
    assert (777, 1) not in pages
    assert (did, 1) in pages


def test_slide_without_a_document_row_yields_empty_filename(session):
    """doc=None must still produce a result, with filename ''."""
    did = _seed(session, with_doc=False, pages=2)     # slides reference doc 999
    chroma = _StubChroma([f"doc{did}_page1"])
    out = run_hybrid_search("transport", SUBJECT, session,
                            _StubEmbedder(), chroma, top_k=6)
    assert out, "a slide with a missing document must still be returned"
    assert out[0]["filename"] == ""


def test_filename_comes_from_the_document(session):
    did = _seed(session)
    chroma = _StubChroma([f"doc{did}_page1"])
    out = run_hybrid_search("transport", SUBJECT, session,
                            _StubEmbedder(), chroma, top_k=6)
    assert out[0]["filename"] == f"{SUBJECT}1.pdf"


def test_mixed_documents_resolve_correctly(session):
    d1 = _seed(session, doc_id_hint=1, pages=2)
    d2 = _seed(session, doc_id_hint=2, pages=2)
    chroma = _StubChroma([f"doc{d1}_page1", f"doc{d2}_page1", f"doc{d2}_page2"])
    out = run_hybrid_search("transport", SUBJECT, session,
                            _StubEmbedder(), chroma, top_k=6)
    by_doc = {}
    for r in out:
        by_doc.setdefault(r["doc_id"], set()).add(r["page_number"])
    assert d1 in by_doc and d2 in by_doc
    for r in out:
        expected = f"{SUBJECT}1.pdf" if r["doc_id"] == d1 else f"{SUBJECT}2.pdf"
        assert r["filename"] == expected, "batched document join mismatched a slide"


def test_non_substantive_slides_are_filtered(session):
    did = _seed(session, pages=1)
    thin = Slide(doc_id=did, page_number=50, subject=SUBJECT, slide_type="other",
                 summary="", concepts="", raw_text="hi", is_embedded=True)
    session.add(thin)
    session.commit()
    chroma = _StubChroma([f"doc{did}_page50", f"doc{did}_page1"])
    out = run_hybrid_search("transport", SUBJECT, session,
                            _StubEmbedder(), chroma, top_k=6)
    assert 50 not in {r["page_number"] for r in out}


def test_subject_filter_is_passed_to_chroma(session):
    did = _seed(session, pages=2)
    chroma = _StubChroma([f"doc{did}_page1"])
    run_hybrid_search("transport", SUBJECT, session, _StubEmbedder(), chroma, top_k=6)
    assert chroma.last_where == {"subject": SUBJECT}


def test_ordering_is_deterministic_across_repeats(session):
    did = _seed(session, pages=4)
    ids = [f"doc{did}_page{p}" for p in (1, 2, 3, 4)]
    chroma = _StubChroma(ids)
    runs = [[(r["doc_id"], r["page_number"]) for r in
             run_hybrid_search("transport protocols", SUBJECT, session,
                               _StubEmbedder(), chroma, top_k=6)]
            for _ in range(5)]
    assert all(r == runs[0] for r in runs)


def test_results_are_sorted_by_score_then_doc_then_page(session):
    did = _seed(session, pages=4)
    chroma = _StubChroma([f"doc{did}_page{p}" for p in (1, 2, 3, 4)])
    out = run_hybrid_search("transport protocols", SUBJECT, session,
                            _StubEmbedder(), chroma, top_k=6)
    keys = [(-r["rrf_score"], r["doc_id"], r["page_number"]) for r in out]
    assert keys == sorted(keys)


def test_empty_dense_and_empty_corpus_returns_nothing(session):
    out = run_hybrid_search("anything", "NOSUCH", session,
                            _StubEmbedder(), _StubChroma([]), top_k=6)
    assert out == []
