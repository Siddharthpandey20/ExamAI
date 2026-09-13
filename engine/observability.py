"""
engine/observability.py — privacy-safe retrieval observation log.

Why this exists
---------------
Every retrieval-quality conclusion this project has reached was measured on
constructed evaluation sets, and each time the evaluation was made more
realistic the measured performance fell. The one thing never measured is what
students actually type. A replay of the 31 distinct queries in query_cache
showed a median length of 4 words, with 12 of them two words or fewer - a
distribution nothing in the evaluation sets resembles.

This module records where real queries land in the dense-distance distribution
so that any future confidence decision is calibrated on real traffic rather
than on synthetic questions.

What it does NOT do
-------------------
It does not change retrieval, ranking, filtering, context, prompts or answers.
It is called after a search has already produced its result, it returns None,
and its failures are swallowed. If the log cannot be written, retrieval
continues unaffected - this is an observability feature, never a dependency.

Privacy
-------
The raw query is NOT stored. Each observation keeps a truncated SHA-256 of the
normalised text, which is enough to recognise a repeated question without
retaining what was asked, plus structural features (length, shape) that are
what the distance analysis actually needs. No slide text, filename, document
content, credential or model key is written. Set EXAMAI_OBSERVE_QUERY_TEXT=1 to
include the raw text as well - off by default, and intended only for a local
debugging session on your own machine.

Disable entirely with EXAMAI_OBSERVE_RETRIEVAL=0.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_LOCK = threading.Lock()

# Celery runs a threads pool, so appends are serialised by _LOCK. The cap stops
# an unattended instance from filling a disk; once reached the log stops
# growing rather than rotating, because losing observations is preferable to
# deleting data the user may not have analysed yet.
_MAX_BYTES = 32 * 1024 * 1024
_WARNED = False

_WH = {"what", "why", "how", "when", "where", "which", "who", "whose", "whom"}


def _enabled() -> bool:
    return os.getenv("EXAMAI_OBSERVE_RETRIEVAL", "1").strip().lower() not in (
        "0", "false", "no", "off")


def _log_path() -> Path:
    raw = os.getenv("EXAMAI_OBSERVE_PATH")
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[1] / "logs" / "retrieval_observations.jsonl"


def query_shape(query: str) -> dict:
    """Structural features of a query. No content is retained."""
    q = query or ""
    words = re.findall(r"[A-Za-z0-9/+._-]+", q)
    lowered = {w.lower() for w in words}
    acronyms = [w for w in words if len(w) > 1 and w.isupper()]
    return {
        "n_chars": len(q),
        "n_words": len(words),
        "has_question_mark": "?" in q,
        "n_acronyms": len(acronyms),
        # A short query with no interrogative is the "keyword" shape that the
        # evaluation sets showed to be the hardest for a distance threshold.
        "keyword_shape": len(words) <= 6 and not (lowered & _WH),
        "all_acronym": bool(words) and len(acronyms) == len(words),
    }


def _fingerprint(query: str) -> str:
    norm = " ".join((query or "").lower().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def record_retrieval(
    *,
    endpoint: str,
    subject: str,
    query: str,
    stats: dict | None,
    results: list | None,
    latency_ms: float | None = None,
    answered: bool | None = None,
    extra: dict | None = None,
) -> None:
    """Append one observation. Never raises, never returns a value.

    Deliberately takes what the caller already has rather than recomputing
    anything, so it cannot disagree with the retrieval it is describing.
    """
    global _WARNED
    try:
        if not _enabled():
            return

        stats = stats or {}
        results = results or []
        top = results[0] if results else {}

        row = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "endpoint": endpoint,
            "subject": subject,
            "query_id": _fingerprint(query),
            **query_shape(query),
            "dense_top1": stats.get("dense_top1"),
            "dense_mean": stats.get("dense_mean"),
            "top_result_distance": stats.get("top_result_distance"),
            "n_dense": stats.get("n_dense"),
            "n_sparse": stats.get("n_sparse"),
            "n_fused": stats.get("n_fused"),
            "n_returned": stats.get("n_returned"),
            "rrf_top1": top.get("rrf_score"),
            # Whether both retrievers surfaced the winner. The production
            # coverage gate thresholds RRF score, which - since RRF scores a
            # rank - is really just this boolean in disguise.
            "both_retrievers": (top.get("dense_rank") is not None
                                and top.get("sparse_rank") is not None),
            "latency_ms": round(latency_ms, 2) if latency_ms is not None else None,
            "answered": answered,
        }
        if extra:
            row.update(extra)
        if os.getenv("EXAMAI_OBSERVE_QUERY_TEXT", "0").strip().lower() in (
                "1", "true", "yes", "on"):
            row["query_text"] = query

        path = _log_path()
        line = json.dumps(row, ensure_ascii=False, default=str) + "\n"
        with _LOCK:
            try:
                if path.exists() and path.stat().st_size >= _MAX_BYTES:
                    if not _WARNED:
                        log.warning("retrieval observation log at size cap (%s); "
                                    "no further observations recorded", path)
                        _WARNED = True
                    return
            except OSError:
                pass
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)
    except Exception:                      # noqa: BLE001 - observability only
        # A logging failure must never surface to a student mid-question.
        log.debug("retrieval observation not recorded", exc_info=True)


class observe:
    """Context manager that times a retrieval and records it on exit.

    Usage keeps the call site to two lines and guarantees the timing covers
    exactly the search:

        with observe("fast_search", subject, query) as obs:
            slides = run_hybrid_search(..., stats=obs.stats)
        obs.done(slides)
    """

    def __init__(self, endpoint: str, subject: str, query: str):
        self.endpoint, self.subject, self.query = endpoint, subject, query
        self.stats: dict = {}
        self._t0 = time.perf_counter()
        self._results = None
        self._answered = None
        self._extra = None

    def done(self, results, answered=None, **extra):
        self._results, self._answered = results, answered
        self._extra = extra or None
        return results

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        record_retrieval(
            endpoint=self.endpoint, subject=self.subject, query=self.query,
            stats=self.stats, results=self._results,
            latency_ms=(time.perf_counter() - self._t0) * 1000,
            answered=self._answered, extra=self._extra,
        )
        return False                        # never suppress an exception
