"""
Tests for the retrieval observation log.

The whole point of this module is that it is a passenger, never a dependency.
So the tests are weighted towards the ways it could break retrieval rather than
towards the correctness of the numbers it writes:

  - retrieval output must be identical whether observation is on or off
  - an unwritable log, a full disk, or a serialisation failure must not
    propagate to the caller
  - the raw query must not reach the log unless explicitly opted in
  - no credential-shaped or slide-content field may be written

A failure here means a student loses an answer because a log file could not be
appended to, which is never an acceptable trade.
"""

import json
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from engine import observability
from engine.observability import observe, record_retrieval, query_shape
from engine.tools import run_hybrid_search, reset_bm25_cache
from indexing.models import Base, Document, Slide

SUBJECT = "CN"


class _StubEmbedder:
    def embed_query(self, text):
        return [0.0] * 8


class _StubChroma:
    def __init__(self, ids, distances=None):
        self._ids, self._distances = ids, distances

    def query(self, query_embedding, n_results=10, where=None):
        ids = self._ids[:n_results]
        out = {"ids": [ids], "metadatas": [[{"source_file": "x.md"} for _ in ids]]}
        if self._distances is not None:
            out["distances"] = [self._distances[:n_results]]
        return out


@pytest.fixture()
def session(tmp_path):
    reset_bm25_cache()
    engine = create_engine(f"sqlite:///{tmp_path / 'obs.db'}")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()
    reset_bm25_cache()


@pytest.fixture()
def logfile(tmp_path, monkeypatch):
    path = tmp_path / "obs.jsonl"
    monkeypatch.setenv("EXAMAI_OBSERVE_PATH", str(path))
    monkeypatch.setenv("EXAMAI_OBSERVE_RETRIEVAL", "1")
    monkeypatch.delenv("EXAMAI_OBSERVE_QUERY_TEXT", raising=False)
    monkeypatch.setattr(observability, "_WARNED", False)
    return path


def _seed(session, pages=4):
    doc = Document(filename="CN1.md", original_filename="CN1.pdf",
                   file_hash="hCN1", status="processed", subject=SUBJECT)
    session.add(doc)
    session.flush()
    for p in range(1, pages + 1):
        session.add(Slide(
            doc_id=doc.id, page_number=p, subject=SUBJECT, slide_type="concept",
            summary=f"CN summary {p} with plenty of substantive words here",
            concepts="tcp, udp", chapter="ch",
            raw_text=f"CN body page {p} transport protocols marker{p}",
            is_embedded=True, importance_score=0.5))
    session.commit()
    return doc.id


def _read(path):
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l]


# ── it must not change retrieval ─────────────────────────────────────────

def test_observation_does_not_change_results(session, logfile, monkeypatch):
    did = _seed(session)
    ids = [f"doc{did}_page{p}" for p in (1, 2, 3)]

    monkeypatch.setenv("EXAMAI_OBSERVE_RETRIEVAL", "0")
    off = run_hybrid_search("transport", SUBJECT, session, _StubEmbedder(),
                            _StubChroma(ids, [0.1, 0.2, 0.3]), top_k=6)

    monkeypatch.setenv("EXAMAI_OBSERVE_RETRIEVAL", "1")
    with observe("t", SUBJECT, "transport") as obs:
        on = run_hybrid_search("transport", SUBJECT, session, _StubEmbedder(),
                               _StubChroma(ids, [0.1, 0.2, 0.3]), top_k=6,
                               stats=obs.stats)
        obs.done(on, answered=True)

    assert off == on
    assert len(_read(logfile)) == 1


def test_disabled_writes_nothing(session, logfile, monkeypatch):
    monkeypatch.setenv("EXAMAI_OBSERVE_RETRIEVAL", "0")
    with observe("t", SUBJECT, "q") as obs:
        obs.done([], answered=False)
    assert not logfile.exists()


# ── it must not be able to break the caller ──────────────────────────────

def test_unwritable_log_does_not_raise(session, monkeypatch, tmp_path):
    # Point the log at a path that cannot be created (a file used as a dir).
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("EXAMAI_OBSERVE_PATH", str(blocker / "sub" / "obs.jsonl"))
    monkeypatch.setenv("EXAMAI_OBSERVE_RETRIEVAL", "1")

    did = _seed(session)
    with observe("t", SUBJECT, "transport") as obs:
        out = run_hybrid_search("transport", SUBJECT, session, _StubEmbedder(),
                                _StubChroma([f"doc{did}_page1"], [0.1]),
                                top_k=6, stats=obs.stats)
        obs.done(out, answered=True)
    assert out, "retrieval must succeed even though the log could not be written"


def test_unserialisable_extra_does_not_raise(logfile):
    class Exploding:
        def __repr__(self):
            raise RuntimeError("boom")

    # default=str is used, so this exercises the outer guard.
    record_retrieval(endpoint="t", subject=SUBJECT, query="q", stats={},
                     results=[], extra={"bad": Exploding()})
    # No exception is the assertion.


def test_exception_inside_the_block_is_not_suppressed(logfile):
    with pytest.raises(ValueError):
        with observe("t", SUBJECT, "q") as obs:
            obs.done([])
            raise ValueError("caller error")
    # and it still recorded what it had
    assert len(_read(logfile)) == 1


def test_size_cap_stops_growth(logfile, monkeypatch):
    monkeypatch.setattr(observability, "_MAX_BYTES", 10)
    for _ in range(5):
        record_retrieval(endpoint="t", subject=SUBJECT, query="q", stats={},
                         results=[])
    assert len(_read(logfile)) <= 1


# ── privacy ──────────────────────────────────────────────────────────────

def test_raw_query_is_not_logged_by_default(logfile):
    secret = "what is my password hunter2 for the admin account"
    record_retrieval(endpoint="t", subject=SUBJECT, query=secret, stats={},
                     results=[])
    blob = logfile.read_text(encoding="utf-8")
    assert "hunter2" not in blob
    assert "password" not in blob
    row = _read(logfile)[0]
    assert "query_text" not in row
    assert len(row["query_id"]) == 16


def test_raw_query_logged_only_when_opted_in(logfile, monkeypatch):
    monkeypatch.setenv("EXAMAI_OBSERVE_QUERY_TEXT", "1")
    record_retrieval(endpoint="t", subject=SUBJECT, query="hello world",
                     stats={}, results=[])
    assert _read(logfile)[0]["query_text"] == "hello world"


def test_no_slide_content_is_logged(session, logfile):
    did = _seed(session)
    with observe("t", SUBJECT, "transport") as obs:
        out = run_hybrid_search("transport", SUBJECT, session, _StubEmbedder(),
                                _StubChroma([f"doc{did}_page{p}" for p in (1, 2)],
                                            [0.1, 0.2]),
                                top_k=6, stats=obs.stats)
        obs.done(out, answered=True)
    blob = logfile.read_text(encoding="utf-8")
    assert "substantive words" not in blob
    assert "CN1.pdf" not in blob
    assert "marker1" not in blob


def test_same_query_gets_same_id_different_gets_different(logfile):
    record_retrieval(endpoint="t", subject=SUBJECT, query="What is TCP?",
                     stats={}, results=[])
    record_retrieval(endpoint="t", subject=SUBJECT, query="  what   is tcp?  ",
                     stats={}, results=[])
    record_retrieval(endpoint="t", subject=SUBJECT, query="What is UDP?",
                     stats={}, results=[])
    a, b, c = [r["query_id"] for r in _read(logfile)]
    assert a == b, "normalisation should make these the same question"
    assert a != c


# ── the recorded values are the ones retrieval actually used ─────────────

def test_records_distance_and_shape(session, logfile):
    did = _seed(session)
    with observe("fast_search", SUBJECT, "TCP") as obs:
        out = run_hybrid_search("transport", SUBJECT, session, _StubEmbedder(),
                                _StubChroma([f"doc{did}_page{p}" for p in (1, 2)],
                                            [0.1234, 0.5]),
                                top_k=6, stats=obs.stats)
        obs.done(out, answered=True)
    row = _read(logfile)[0]
    assert row["dense_top1"] == pytest.approx(0.1234)
    assert row["endpoint"] == "fast_search"
    assert row["answered"] is True
    assert row["n_words"] == 1
    assert row["all_acronym"] is True
    assert row["latency_ms"] >= 0


@pytest.mark.parametrize("q,expect", [
    ("TCP", {"n_words": 1, "all_acronym": True, "keyword_shape": True}),
    ("What is gradient descent?", {"has_question_mark": True,
                                   "keyword_shape": False}),
    ("packet switching advantages", {"keyword_shape": True,
                                     "all_acronym": False}),
    ("", {"n_words": 0, "all_acronym": False}),
])
def test_query_shape(q, expect):
    shape = query_shape(q)
    for k, v in expect.items():
        assert shape[k] == v, f"{q!r}: {k}"
