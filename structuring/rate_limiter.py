"""
rate_limiter.py — Distributed rate limiting via Redis.

Provides two primitives that work across multiple Celery worker processes:

  1. RedisRateLimiter  — sliding-window counter (e.g. 10 calls/60s for Gemini)
  2. RedisSemaphore    — distributed concurrency gate (e.g. 3 concurrent Ollama)

Both fall back to local in-process equivalents when Redis is unavailable,
so the pipeline never breaks — it just loses cross-process coordination.

Redis keys are auto-expired to avoid leaking memory.
"""

import asyncio
import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager

log = logging.getLogger(__name__)

# ── Redis connection (lazy, shared) ──────────────────────────────────────

_redis_client = None
_redis_lock = threading.Lock()
_redis_available = None  # None = not tested yet, True/False after first attempt


def _get_redis():
    """Lazy singleton Redis client. Returns None if Redis is unavailable."""
    global _redis_client, _redis_available
    if _redis_available is False:
        return None
    if _redis_client is not None:
        return _redis_client

    with _redis_lock:
        if _redis_client is not None:
            return _redis_client
        if _redis_available is False:
            return None

        try:
            import redis
            url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2)
            client.ping()
            _redis_client = client
            _redis_available = True
            log.info("[RateLimiter] Redis connected — using distributed rate limiting")
            return client
        except Exception as e:
            _redis_available = False
            log.warning(f"[RateLimiter] Redis unavailable ({e}) — falling back to local rate limiting")
            return None


def reset_redis_state():
    """Reset the cached Redis connection (for testing)."""
    global _redis_client, _redis_available
    with _redis_lock:
        _redis_client = None
        _redis_available = None


# ═════════════════════════════════════════════════════════════════════════
# 1. Distributed Sliding-Window Rate Limiter
# ═════════════════════════════════════════════════════════════════════════

class _LocalRateLimiter:
    """In-process fallback: sliding window using a timestamp list."""

    def __init__(self, max_calls: int, window: float = 60.0):
        self.max_calls = max_calls
        self.window = window
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    async def acquire(self):
        while True:
            with self._lock:
                now = time.time()
                self._timestamps = [t for t in self._timestamps if now - t < self.window]
                if len(self._timestamps) < self.max_calls:
                    self._timestamps.append(now)
                    return
                wait = self.window - (now - self._timestamps[0]) + 0.1
            await asyncio.sleep(wait)


class RedisRateLimiter:
    """
    Distributed sliding-window rate limiter backed by a Redis sorted set.

    Each API call adds a timestamped entry to a sorted set. Before allowing
    a new call, old entries outside the window are pruned and the count is
    checked. This ensures the limit is enforced globally across all workers.

    Falls back to a local in-process limiter if Redis is unavailable.
    """

    def __init__(self, name: str, max_calls: int, window: float = 60.0):
        self.name = name
        self.max_calls = max_calls
        self.window = window
        self._key = f"examai:rate_limit:{name}"
        self._local = _LocalRateLimiter(max_calls, window)
        self._worker_id = f"{os.getpid()}:{uuid.uuid4().hex[:6]}"

    async def acquire(self):
        """Wait until a rate-limit slot is available, then claim it."""
        r = _get_redis()
        if r is None:
            return await self._local.acquire()

        while True:
            try:
                now = time.time()
                window_start = now - self.window

                pipe = r.pipeline(True)
                pipe.zremrangebyscore(self._key, "-inf", window_start)
                pipe.zcard(self._key)
                _, count = pipe.execute()

                if count < self.max_calls:
                    member = f"{self._worker_id}:{now}"
                    r.zadd(self._key, {member: now})
                    r.expire(self._key, int(self.window) + 5)
                    return

                # Compute wait from oldest entry
                oldest = r.zrange(self._key, 0, 0, withscores=True)
                if oldest:
                    wait = self.window - (now - oldest[0][1]) + 0.1
                else:
                    wait = 1.0

                log.info(f"[RateLimiter:{self.name}] Global limit hit ({self.max_calls}/{self.window}s). "
                         f"Waiting {wait:.1f}s...")
                await asyncio.sleep(wait)

            except Exception as e:
                log.warning(f"[RateLimiter:{self.name}] Redis error ({e}), falling back to local")
                return await self._local.acquire()


# ═════════════════════════════════════════════════════════════════════════
# 2. Distributed Semaphore (concurrency gate)
# ═════════════════════════════════════════════════════════════════════════

class _LocalSemaphore:
    """In-process fallback using threading.Semaphore."""

    def __init__(self, max_concurrent: int):
        self._sem = threading.Semaphore(max_concurrent)

    async def acquire(self) -> str:
        while not self._sem.acquire(blocking=False):
            await asyncio.sleep(0.1)
        return "__local__"

    def release(self, holder: str | None = None):
        self._sem.release()


class RedisSemaphore:
    """
    Distributed concurrency gate backed by Redis.

    Uses a sorted set where each holder registers with a TTL-stamped entry.
    Stale entries are auto-cleaned to prevent deadlocks if a worker crashes.

    Falls back to a local threading.Semaphore if Redis is unavailable.
    """

    # Lua script: atomic prune-stale + check-count + add-if-room.
    # Returns 1 if the holder was added, 0 if the semaphore is full.
    _LUA_ACQUIRE = """
    local key       = KEYS[1]
    local stale_thr = tonumber(ARGV[1])
    local max_c     = tonumber(ARGV[2])
    local holder    = ARGV[3]
    local now       = tonumber(ARGV[4])
    local ttl       = tonumber(ARGV[5])

    redis.call('ZREMRANGEBYSCORE', key, '-inf', stale_thr)
    if redis.call('ZCARD', key) < max_c then
        redis.call('ZADD', key, now, holder)
        redis.call('EXPIRE', key, ttl)
        return 1
    end
    return 0
    """

    def __init__(self, name: str, max_concurrent: int, ttl: float = 120.0):
        self.name = name
        self.max_concurrent = max_concurrent
        self.ttl = ttl
        self._key = f"examai:semaphore:{name}"
        self._local = _LocalSemaphore(max_concurrent)
        self._script = None  # lazy-registered Lua script

    def _get_script(self, r):
        """Lazy-register the Lua script on the Redis client."""
        if self._script is None:
            self._script = r.register_script(self._LUA_ACQUIRE)
        return self._script

    async def acquire(self) -> str:
        """Acquire a slot. Returns a holder token to pass to release()."""
        r = _get_redis()
        if r is None:
            return await self._local.acquire()

        holder = f"{os.getpid()}:{threading.current_thread().ident}:{uuid.uuid4().hex[:6]}"
        script = self._get_script(r)

        while True:
            try:
                now = time.time()
                stale_threshold = now - self.ttl

                acquired = script(
                    keys=[self._key],
                    args=[stale_threshold, self.max_concurrent, holder, now, int(self.ttl) + 10],
                )
                if acquired:
                    return holder

                await asyncio.sleep(0.5)

            except Exception as e:
                log.warning(f"[Semaphore:{self.name}] Redis error ({e}), falling back to local")
                self._script = None  # reset so it re-registers on retry
                return await self._local.acquire()

    def release(self, holder: str | None = None):
        """Release the slot identified by *holder* (returned by acquire)."""
        if holder is None or holder == "__local__":
            self._local.release()
            return

        r = _get_redis()
        if r is not None:
            try:
                r.zrem(self._key, holder)
            except Exception:
                pass


@asynccontextmanager
async def semaphore_slot(semaphore: RedisSemaphore):
    """Async context manager for acquiring/releasing a distributed semaphore."""
    holder = await semaphore.acquire()
    try:
        yield
    finally:
        semaphore.release(holder)
