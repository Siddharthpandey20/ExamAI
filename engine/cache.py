"""
engine/cache.py — Two-level SQLite-backed response cache for LLM queries.

Level 1 — Exact hash match (instant, no LLM cost).
Level 2 — Fuzzy semantic match via local Ollama (detects paraphrased queries).

Cache persists **indefinitely** until:
  • New documents or PYQ are added for the subject  → content fingerprint changes
  • User explicitly passes force=True               → bypass cache entirely

Content fingerprint = "doc_count:slide_count:pyq_count" for the subject.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import func

from indexing.database import SessionFactory
from indexing.models import QueryCache, Document, Slide, PYQQuestion

log = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_hash(subject: str, endpoint: str, query: str) -> str:
    """Deterministic SHA-256 hash of (subject, endpoint, normalised query)."""
    normalised = query.strip().lower()
    raw = f"{subject}|{endpoint}|{normalised}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _content_fingerprint(subject: str, session) -> str:
    """Snapshot of how much content exists for a subject right now."""
    doc_count = (
        session.query(func.count(Document.id))
        .filter(Document.subject == subject)
        .scalar()
    ) or 0
    slide_count = (
        session.query(func.count(Slide.id))
        .filter(Slide.subject == subject)
        .scalar()
    ) or 0
    pyq_count = (
        session.query(func.count(PYQQuestion.id))
        .filter(PYQQuestion.subject == subject)
        .scalar()
    ) or 0
    return f"{doc_count}:{slide_count}:{pyq_count}"


def _get_cache_by_hash(qhash: str, subject: str, session) -> dict | None:
    """Return cached response for a given hash, checking fingerprint."""
    entry = (
        session.query(QueryCache)
        .filter(QueryCache.query_hash == qhash)
        .first()
    )
    if entry is None:
        return None

    fp = _content_fingerprint(subject, session)
    if entry.content_fingerprint and entry.content_fingerprint != fp:
        # Content changed — stale cache
        session.delete(entry)
        session.commit()
        log.info(f"[Cache] Stale (content changed) for '{entry.endpoint}' on {subject}")
        return None

    age = datetime.now(timezone.utc) - entry.created_at.replace(tzinfo=timezone.utc)
    log.info(f"[Cache] HIT for '{entry.endpoint}' on {subject} (age={age})")
    result = json.loads(entry.response_json)
    result["_cached"] = True
    result["_cache_age_minutes"] = int(age.total_seconds() / 60)
    return result


# ── Level 1: Exact match ────────────────────────────────────────────────

def check_cache(subject: str, endpoint: str, query: str) -> dict | None:
    """Exact hash-based cache lookup. Returns dict or None."""
    qhash = _make_hash(subject, endpoint, query)
    session = SessionFactory()
    try:
        return _get_cache_by_hash(qhash, subject, session)
    except Exception:
        session.rollback()
        return None
    finally:
        session.close()


# ── Level 2: Smart check (exact → fuzzy) ────────────────────────────────

async def smart_cache_check(
    subject: str,
    endpoint: str,
    query: str,
    force: bool = False,
) -> tuple[dict | None, str]:
    """
    Two-level cache check.

    Returns (cached_response_or_None, normalized_query).
    The normalized query should be used for the LLM call + cache store.
    """
    if force:
        return None, query

    # Level 1: exact hash match
    exact = check_cache(subject, endpoint, query)
    if exact:
        return exact, query

    # Level 2: fuzzy match via local Ollama
    try:
        from engine.query_matcher import find_matching_query
        match_result = await find_matching_query(query, subject, endpoint)
    except Exception:
        log.debug("Fuzzy matching unavailable", exc_info=True)
        match_result = None

    if match_result is not None:
        if match_result.is_existing and match_result.matched_query_hash:
            session = SessionFactory()
            try:
                cached = _get_cache_by_hash(
                    match_result.matched_query_hash, subject, session,
                )
                if cached:
                    cached["_fuzzy_match"] = True
                    return cached, match_result.normalized_query
            except Exception:
                session.rollback()
            finally:
                session.close()
        # No match but we got a better query text
        return None, match_result.normalized_query

    return None, query


# ── Store ────────────────────────────────────────────────────────────────

def store_cache(
    subject: str,
    endpoint: str,
    query: str,
    response: dict,
    model_used: str = "",
):
    """
    Store an LLM response in the cache with the current content fingerprint.

    If an entry with the same hash already exists, it is replaced.
    """
    qhash = _make_hash(subject, endpoint, query)
    session = SessionFactory()
    try:
        fp = _content_fingerprint(subject, session)
        existing = (
            session.query(QueryCache)
            .filter(QueryCache.query_hash == qhash)
            .first()
        )

        # Strip internal cache metadata before persisting
        clean = {k: v for k, v in response.items() if not k.startswith("_")}

        if existing:
            existing.response_json = json.dumps(clean)
            existing.model_used = model_used
            existing.created_at = datetime.now(timezone.utc)
            existing.content_fingerprint = fp
        else:
            entry = QueryCache(
                subject=subject,
                query_hash=qhash,
                query_text=query.strip(),
                endpoint=endpoint,
                response_json=json.dumps(clean),
                model_used=model_used,
                created_at=datetime.now(timezone.utc),
                content_fingerprint=fp,
            )
            session.add(entry)

        session.commit()
        log.info(f"[Cache] Stored '{endpoint}' on {subject} (model={model_used})")
    except Exception:
        session.rollback()
        log.warning("[Cache] Failed to store response", exc_info=True)
    finally:
        session.close()
