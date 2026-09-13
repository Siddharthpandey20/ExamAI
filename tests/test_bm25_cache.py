"""
Correctness tests for the cached BM25 index.

The sparse index used to be rebuilt from scratch on every query. It is now
cached per subject, keyed on a SHA-256 of the corpus rows themselves.

The key is the content rather than a proxy for a measured reason:
engine.cache._content_fingerprint counts documents, slides and PYQs, and does
NOT change when raw_text is edited, when summary is edited, or when
is_embedded flips — all of which indexing.pipeline.index_file does via
upsert_slide followed by mark_slides_embedded while leaving counts identical.
A cache keyed on that fingerprint would serve stale results.

These tests are the staleness gate: if any of them can observe a stale
result, the optimisation is wrong and must be reverted.
"""

import threading

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import engine.tools as tools
from engine.tools import _corpus_digest, _corpus_rows, _get_bm25_index, reset_bm25_cache
from indexing.models import Base, Document, Slide


@pytest.fixture()
def session(tmp_path):
    reset_bm25_cache()
    engine = create_engine(f"sqlite:///{tmp_path / 'bm25.db'}")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()
    reset_bm25_cache()


def _add_doc(session, subject, pages=3, text="transport layer protocols", marker=None):
    """Seed a document. *marker* lands on page 1 only.

    BM25 assigns negative IDF to a term present in EVERY document, and the
    production code keeps only scores > 0, so a search term must appear in a
    subset of the corpus to discriminate. That is pre-existing BM25
    behaviour and unrelated to caching, but it dictates how these fixtures
    are built.
    """
    doc = Document(filename=f"{subject}.md", file_hash=f"h-{subject}",
                   status="processed", subject=subject)
    session.add(doc)
    session.flush()
    for p in range(1, pages + 1):
        raw = f"{text} page {p}"
        if marker and p == 1:
            raw = f"{marker} {raw}"
        session.add(Slide(doc_id=doc.id, page_number=p, subject=subject,
                          summary=f"{subject} summary {p}", concepts="tcp, udp",
                          raw_text=raw, is_embedded=True))
    session.commit()
    return doc


def _search(session, subject, term):
    """Slide ids the sparse index returns for *term*, best first."""
    bm25, rows = _get_bm25_index(session, subject)
    if bm25 is None:
        return []
    q = tools._tokenize(term)
    if not q:
        return []
    scores = bm25.get_scores(q)
    ranked = sorted(((i, scores[i]) for i in range(len(scores)) if scores[i] > 0),
                    key=lambda x: x[1], reverse=True)
    return [rows[i].id for i, _ in ranked]


# ── Test 1: baseline ─────────────────────────────────────────────────────

def test_search_matches_uncached_behaviour(session):
    _add_doc(session, "CN", marker="baselinemarker")
    first = _search(session, "CN", "baselinemarker")
    assert first, "fixture should match"

    reset_bm25_cache()                       # force a cold rebuild
    assert _search(session, "CN", "baselinemarker") == first


def test_cache_is_reused_when_nothing_changes(session):
    _add_doc(session, "CN")
    a, _ = _get_bm25_index(session, "CN")
    b, _ = _get_bm25_index(session, "CN")
    assert a is b, "unchanged corpus must reuse the same index object"


# ── Test 2: a new document must appear immediately ───────────────────────

def test_new_document_is_visible_immediately(session):
    _add_doc(session, "CN")
    _get_bm25_index(session, "CN")                       # warm the cache
    assert _search(session, "CN", "zebracrossing") == []

    doc = Document(filename="new.md", file_hash="h-new", status="processed", subject="CN")
    session.add(doc)
    session.flush()
    session.add(Slide(doc_id=doc.id, page_number=1, subject="CN",
                      summary="new slide", concepts="x",
                      raw_text="zebracrossing distinctive term", is_embedded=True))
    session.commit()

    assert _search(session, "CN", "zebracrossing"), "new document not visible - STALE"


# ── Test 3: an edit with unchanged counts must be visible ────────────────

def test_edited_text_is_visible_immediately(session):
    """The case the count-based fingerprint misses entirely."""
    _add_doc(session, "CN")
    _get_bm25_index(session, "CN")
    assert _search(session, "CN", "quokkasignal") == []

    slide = session.query(Slide).filter(Slide.page_number == 1).first()
    slide.raw_text = "quokkasignal replaces the old text"
    session.commit()

    hits = _search(session, "CN", "quokkasignal")
    assert hits == [slide.id], "edited text not visible - STALE"


def test_edited_summary_is_visible_immediately(session):
    _add_doc(session, "CN")
    _get_bm25_index(session, "CN")
    slide = session.query(Slide).filter(Slide.page_number == 2).first()
    slide.summary = "aardvarkmarker in the summary"
    session.commit()
    assert _search(session, "CN", "aardvarkmarker") == [slide.id]


# ── Test 4: removed content must stop appearing ──────────────────────────

def test_deleted_slide_stops_appearing(session):
    _add_doc(session, "CN")
    slide = session.query(Slide).filter(Slide.page_number == 1).first()
    slide.raw_text = "narwhaltoken unique here"
    session.commit()
    assert _search(session, "CN", "narwhaltoken") == [slide.id]

    session.delete(slide)
    session.commit()
    assert _search(session, "CN", "narwhaltoken") == [], "deleted slide still served - STALE"


def test_unembedding_a_slide_removes_it(session):
    """is_embedded gates corpus membership and leaves counts untouched."""
    _add_doc(session, "CN")
    slide = session.query(Slide).filter(Slide.page_number == 1).first()
    slide.raw_text = "pangolinkey unique here"
    session.commit()
    assert _search(session, "CN", "pangolinkey") == [slide.id]

    slide.is_embedded = False
    session.commit()
    assert _search(session, "CN", "pangolinkey") == [], "un-embedded slide still served - STALE"


# ── Test 5: subject isolation ────────────────────────────────────────────

def test_changing_one_subject_does_not_disturb_another(session):
    _add_doc(session, "CN")
    _add_doc(session, "ML", text="gradient descent optimisation", marker="mlmarker")

    ml_before = _search(session, "ML", "mlmarker")
    ml_index_before, _ = _get_bm25_index(session, "ML")
    assert ml_before

    doc = Document(filename="cn2.md", file_hash="h-cn2", status="processed", subject="CN")
    session.add(doc)
    session.flush()
    session.add(Slide(doc_id=doc.id, page_number=9, subject="CN", summary="s",
                      concepts="c", raw_text="gradient mention inside CN", is_embedded=True))
    session.commit()

    assert _search(session, "ML", "mlmarker") == ml_before, "subject B leaked subject A's change"
    ml_index_after, _ = _get_bm25_index(session, "ML")
    assert ml_index_after is ml_index_before, "subject B rebuilt unnecessarily"


def test_subjects_never_share_results(session):
    _add_doc(session, "CN", text="shared body text", marker="sharedmarker")
    _add_doc(session, "ML", text="shared body text", marker="sharedmarker")
    cn = set(_search(session, "CN", "sharedmarker"))
    ml = set(_search(session, "ML", "sharedmarker"))
    assert cn and ml and cn.isdisjoint(ml)


# ── Test 6: restart ──────────────────────────────────────────────────────

def test_cold_cache_reproduces_identical_results(session):
    """A fresh process starts with an empty cache and must agree."""
    _add_doc(session, "CN", marker="coldmarker")
    warm = _search(session, "CN", "coldmarker")
    assert warm
    reset_bm25_cache()
    assert _search(session, "CN", "coldmarker") == warm


# ── Test 7: concurrency ──────────────────────────────────────────────────

def test_concurrent_access_is_consistent(tmp_path):
    """Parallel readers must never see corrupt or crossed state."""
    reset_bm25_cache()
    engine = create_engine(f"sqlite:///{tmp_path / 'conc.db'}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Factory = sessionmaker(bind=engine)
    setup = Factory()
    _add_doc(setup, "CN", marker="cnmarker")
    _add_doc(setup, "ML", text="gradient descent optimisation", marker="mlmarker")
    setup.close()

    results, errors = [], []

    def worker(subject, term):
        try:
            s = Factory()
            try:
                for _ in range(8):
                    results.append((subject, tuple(_search(s, subject, term))))
            finally:
                s.close()
        except Exception as exc:          # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=a)
               for a in [("CN", "cnmarker"), ("ML", "mlmarker")] * 4]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent access raised: {errors}"
    for subject in ("CN", "ML"):
        seen = {r for s, r in results if s == subject}
        assert len(seen) == 1, f"{subject} produced inconsistent results under concurrency"
    reset_bm25_cache()


# ── Digest properties ────────────────────────────────────────────────────

def test_digest_changes_on_every_corpus_mutation(session):
    _add_doc(session, "CN")
    d0 = _corpus_digest(_corpus_rows(session, "CN"))
    assert _corpus_digest(_corpus_rows(session, "CN")) == d0, "digest must be stable"

    slide = session.query(Slide).filter(Slide.page_number == 1).first()
    slide.raw_text += " extra"
    session.commit()
    d1 = _corpus_digest(_corpus_rows(session, "CN"))
    assert d1 != d0

    slide.summary = "changed"
    session.commit()
    d2 = _corpus_digest(_corpus_rows(session, "CN"))
    assert d2 != d1

    slide.concepts = "changed too"
    session.commit()
    d3 = _corpus_digest(_corpus_rows(session, "CN"))
    assert d3 != d2

    slide.is_embedded = False
    session.commit()
    assert _corpus_digest(_corpus_rows(session, "CN")) != d3


def test_empty_corpus_is_handled(session):
    bm25, rows = _get_bm25_index(session, "NOSUCHSUBJECT")
    assert bm25 is None and rows == []


def test_slides_with_no_tokens_are_excluded(session):
    doc = Document(filename="x.md", file_hash="hx", status="processed", subject="CN")
    session.add(doc)
    session.flush()
    session.add(Slide(doc_id=doc.id, page_number=1, subject="CN",
                      summary="", concepts="", raw_text="!!! ***", is_embedded=True))
    session.commit()
    bm25, rows = _get_bm25_index(session, "CN")
    assert bm25 is None and rows == []
