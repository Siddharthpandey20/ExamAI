"""
Regression tests for the L1/L2 cache key mismatch.

Level 2 returns a normalised rewrite of the user's question, and the caller
uses that for retrieval and the prompt. The response was then stored under
the *normalised* hash — but Level 1 hashes whatever the user actually
typed, so asking the identical question twice never hit L1 and paid for
another fuzzy-match round trip every time.

store_cache(cache_key_query=...) keys the row on the raw question while
query_text stays normalised for L2 to compare against.

Runs against a throwaway SQLite file. No Ollama, no LLM, no network.
"""

import os
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine.cache as cache_mod  # noqa: E402
from engine.cache import _make_hash, check_cache, store_cache  # noqa: E402
from indexing.models import Base, QueryCache  # noqa: E402

RAW = "is tcp congestion control covered in ppt?"
NORMALISED = "TCP congestion control"
SUBJECT = "CN"


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """Point engine.cache at a throwaway database."""
    engine = create_engine(f"sqlite:///{tmp_path / 'cache.db'}")
    Base.metadata.create_all(engine)
    Factory = sessionmaker(bind=engine)
    monkeypatch.setattr(cache_mod, "SessionFactory", Factory)
    return Factory


def _response(tag="answer"):
    return {"answer": tag, "slides": [], "mode": "fast"}


# ── The mismatch itself ──────────────────────────────────────────────────

def test_raw_query_hits_l1_after_l2_normalisation(db):
    """The core regression: ask, then ask the identical thing again."""
    store_cache(SUBJECT, "search", NORMALISED, _response(), "groq",
                cache_key_query=RAW)

    hit = check_cache(SUBJECT, "search", RAW)
    assert hit is not None, "identical repeat query must hit L1"
    assert hit["answer"] == "answer"
    assert hit["_cached"] is True


def test_without_the_fix_the_raw_query_would_miss(db):
    """Documents the old behaviour: keying on the normalised text misses."""
    store_cache(SUBJECT, "search", NORMALISED, _response(), "groq")
    assert check_cache(SUBJECT, "search", RAW) is None
    assert check_cache(SUBJECT, "search", NORMALISED) is not None


def test_normalised_text_is_still_stored_for_l2(db):
    """L2 compares query_text, so it must keep the clean rewrite."""
    store_cache(SUBJECT, "search", NORMALISED, _response(), "groq",
                cache_key_query=RAW)
    s = db()
    try:
        row = s.query(QueryCache).one()
        assert row.query_text == NORMALISED
        assert row.query_hash == _make_hash(SUBJECT, "search", RAW)
    finally:
        s.close()


def test_only_one_row_is_written(db):
    store_cache(SUBJECT, "search", NORMALISED, _response(), "groq",
                cache_key_query=RAW)
    s = db()
    try:
        assert s.query(QueryCache).count() == 1
    finally:
        s.close()


def test_repeat_store_replaces_rather_than_duplicates(db):
    for tag in ("first", "second", "third"):
        store_cache(SUBJECT, "search", NORMALISED, _response(tag), "groq",
                    cache_key_query=RAW)
    s = db()
    try:
        assert s.query(QueryCache).count() == 1
    finally:
        s.close()
    assert check_cache(SUBJECT, "search", RAW)["answer"] == "third"


# ── Isolation guarantees must survive ────────────────────────────────────

def test_subjects_never_share_cached_results(db):
    store_cache("CN", "search", NORMALISED, _response("cn"), "groq", cache_key_query=RAW)
    store_cache("ML", "search", NORMALISED, _response("ml"), "groq", cache_key_query=RAW)

    assert check_cache("CN", "search", RAW)["answer"] == "cn"
    assert check_cache("ML", "search", RAW)["answer"] == "ml"
    assert check_cache("DBMS", "search", RAW) is None


def test_endpoints_never_collide(db):
    store_cache(SUBJECT, "search", NORMALISED, _response("s"), "groq", cache_key_query=RAW)
    store_cache(SUBJECT, "coverage", NORMALISED, _response("c"), "groq", cache_key_query=RAW)
    store_cache(SUBJECT, "reasoning", NORMALISED, _response("r"), "groq", cache_key_query=RAW)

    assert check_cache(SUBJECT, "search", RAW)["answer"] == "s"
    assert check_cache(SUBJECT, "coverage", RAW)["answer"] == "c"
    assert check_cache(SUBJECT, "reasoning", RAW)["answer"] == "r"


def test_different_raw_queries_do_not_collide(db):
    store_cache(SUBJECT, "search", NORMALISED, _response("a"), "groq",
                cache_key_query="explain tcp")
    store_cache(SUBJECT, "search", NORMALISED, _response("b"), "groq",
                cache_key_query="explain udp")

    assert check_cache(SUBJECT, "search", "explain tcp")["answer"] == "a"
    assert check_cache(SUBJECT, "search", "explain udp")["answer"] == "b"


def test_key_is_case_and_whitespace_insensitive_as_before(db):
    """_make_hash already lowercases and strips; that must not change."""
    store_cache(SUBJECT, "search", NORMALISED, _response(), "groq",
                cache_key_query="  Is TCP Covered?  ")
    assert check_cache(SUBJECT, "search", "is tcp covered?") is not None


# ── Unchanged behaviour for callers that pass no key ─────────────────────

def test_omitting_cache_key_query_keeps_original_behaviour(db):
    """study-plan and revision use deterministic keys and pass nothing."""
    store_cache(SUBJECT, "study-plan", f"study-plan:{SUBJECT}", _response("plan"), "groq")
    assert check_cache(SUBJECT, "study-plan", f"study-plan:{SUBJECT}")["answer"] == "plan"


def test_invalidation_still_works(db, monkeypatch):
    """A changed content fingerprint must still evict the entry."""
    monkeypatch.setattr(cache_mod, "_content_fingerprint", lambda subj, sess: "1:10:0")
    store_cache(SUBJECT, "search", NORMALISED, _response(), "groq", cache_key_query=RAW)
    assert check_cache(SUBJECT, "search", RAW) is not None

    monkeypatch.setattr(cache_mod, "_content_fingerprint", lambda subj, sess: "2:25:3")
    assert check_cache(SUBJECT, "search", RAW) is None, "stale entry must be evicted"

    s = db()
    try:
        assert s.query(QueryCache).count() == 0, "stale row must be deleted"
    finally:
        s.close()


def test_internal_metadata_is_not_persisted(db):
    resp = _response()
    resp["_cached"] = True
    resp["_fuzzy_match"] = True
    store_cache(SUBJECT, "search", NORMALISED, resp, "groq", cache_key_query=RAW)

    hit = check_cache(SUBJECT, "search", RAW)
    s = db()
    try:
        import json
        stored = json.loads(s.query(QueryCache).one().response_json)
    finally:
        s.close()
    assert "_fuzzy_match" not in stored
    assert hit["_cached"] is True  # re-added on read, not persisted
