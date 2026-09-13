"""
routes/health.py — readiness probe.

GET /api/health        — liveness, defined in main.py, unchanged
GET /api/health/ready  — readiness: can this process actually serve traffic?
GET /api/health/models — are the configured LLM model ids still served?

Liveness and readiness answer different questions. The existing /api/health
returns a static ok, which is correct for "the process is up" but says
nothing about whether SQLite, Redis or ChromaDB are reachable — so a
container could pass its health check while every request fails.

Each probe is individually timed, cannot raise, and never reports a detail
that could leak a credential: connection URLs are not echoed back.
"""

import logging
import os
import time

from fastapi import APIRouter, Response

router = APIRouter()
log = logging.getLogger(__name__)

# A probe that takes longer than this is treated as failing: a readiness
# endpoint that blocks is worse than one that reports "not ready".
PROBE_TIMEOUT_SECONDS = 5


def _timed(name: str, fn) -> dict:
    """Run one probe, capturing status, duration and a safe detail."""
    start = time.perf_counter()
    try:
        detail = fn()
        ok = True
    except Exception as exc:
        detail = f"{type(exc).__name__}"
        ok = False
        log.warning(f"[health] {name} probe failed: {type(exc).__name__}")
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    if ok and elapsed_ms > PROBE_TIMEOUT_SECONDS * 1000:
        ok = False
        detail = f"slow ({elapsed_ms:.0f}ms)"
    return {"ok": ok, "detail": detail, "ms": elapsed_ms}


def _check_database() -> str:
    from sqlalchemy import text
    from indexing.database import engine
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return "reachable"


_redis_client = None


def _check_redis() -> str:
    """Ping Redis, reusing one client across probes.

    Building a fresh client per probe measured ~2.05s on this machine while a
    reused one takes ~0.4ms. The cost is not Redis: "localhost" resolves to
    IPv6 ::1 first, Redis is not listening there, and each new connection
    waits for that to time out before falling back to 127.0.0.1 (measured:
    2053ms via localhost, 29ms via 127.0.0.1). Setting
    REDIS_URL=redis://127.0.0.1:6379/0 avoids it for every other connection
    in the app too.

    Reusing the client still detects an outage — ping() fails on a dead
    connection — while keeping the probe cheap enough to poll frequently.
    """
    global _redis_client
    import redis
    if _redis_client is None:
        url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.Redis.from_url(url, socket_timeout=PROBE_TIMEOUT_SECONDS)
    try:
        _redis_client.ping()
    except Exception:
        _redis_client = None      # force a rebuild on the next probe
        raise
    return "reachable"


def _check_chroma() -> str:
    from engine import get_chroma
    return f"{get_chroma().count()} vectors"


def _llm_pool_state() -> dict:
    """What the pool has LEARNED at runtime. No network call.

    A model id that the provider has retired answers 404, and `complete()`
    retires it from the pool for the life of the process. Surfacing that here
    turns a silent per-request failure into something a dashboard can see,
    and costs nothing because it is just in-memory state.
    """
    try:
        from engine.llm import pool
        return {"configured": [t.model for t in pool._trackers],
                "usable": pool.available_models(),
                "retired_by_provider": pool.unavailable_models()}
    except Exception as exc:                      # noqa: BLE001
        return {"error": type(exc).__name__}


def _embedder_state() -> str:
    """Reported, never forced: loading the model takes far too long for a probe."""
    import engine
    return "loaded" if engine._embedder is not None else "not loaded (lazy)"


@router.get("/ready")
def readiness(response: Response):
    """503 when a dependency the request path needs is unreachable.

    Redis is required to enqueue any upload, ChromaDB to answer any search,
    and SQLite for everything, so all three gate readiness. The embedder is
    reported but does not gate: it loads lazily on first use by design.
    """
    checks = {
        "database": _timed("database", _check_database),
        "redis": _timed("redis", _check_redis),
        "chroma": _timed("chroma", _check_chroma),
    }
    ready = all(c["ok"] for c in checks.values())

    response.status_code = 200 if ready else 503
    return {
        "status": "ready" if ready else "not ready",
        "checks": checks,
        "embedder": _embedder_state(),
        # Reported, not gating: a provider retiring a model is a configuration
        # problem to be seen, not a reason to take this instance out of
        # rotation while the remaining models still serve traffic.
        "llm_models": _llm_pool_state(),
    }


@router.get("/models")
def model_liveness(response: Response):
    """Compare configured model ids against what the provider actually serves.

    Deliberately a separate endpoint rather than part of /ready: it makes a
    network call to a third party, and readiness probes are polled often and
    should not depend on someone else's uptime.

    This exists because two of three configured models were decommissioned and
    nothing detected it until 67% of requests were already failing. A 404 from
    a model id is not a transient error - it never recovers on its own - so it
    should be visible from a URL rather than inferred from logs.
    """
    from engine.config import GROQ_MODELS

    configured = [m["model"] for m in GROQ_MODELS]

    def _probe() -> str:
        from openai import OpenAI
        from engine.config import GROQ_API_KEY, GROQ_BASE_URL
        client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL,
                        timeout=PROBE_TIMEOUT_SECONDS)
        return ",".join(sorted(m.id for m in client.models.list().data))

    probe = _timed("provider_models", _probe)
    if not probe["ok"]:
        response.status_code = 503
        return {"status": "unknown", "configured": configured,
                "detail": probe["detail"],
                "note": "could not reach the provider to list models"}

    served = set(probe["detail"].split(",")) if probe["detail"] else set()
    missing = [m for m in configured if m not in served]
    response.status_code = 200 if not missing else 503
    return {
        "status": "ok" if not missing else "configuration stale",
        "configured": configured,
        "serving": [m for m in configured if m in served],
        "missing_at_provider": missing,
        "ms": probe["ms"],
        "action": (None if not missing else
                   "Remove or replace these ids in GROQ_MODELS "
                   "(engine/config.py); requests routed to them will 404."),
    }
