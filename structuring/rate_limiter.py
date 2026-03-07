"""
rate_limiter.py — Simple token-bucket rate limiter for GROQ API calls.

Enforces a maximum of GROQ_MAX_CALLS_PER_MINUTE calls per 60-second window.
Thread-safe for future parallelism.
"""

import time
import threading
import logging

from structuring.config import GROQ_MAX_CALLS_PER_MINUTE

log = logging.getLogger(__name__)


class RateLimiter:
    """
    Token-bucket rate limiter.

    Allows up to `max_calls` calls per `window_seconds`.
    If the limit is reached, blocks until a slot opens.
    """

    def __init__(self, max_calls: int = GROQ_MAX_CALLS_PER_MINUTE, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window = window_seconds
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    def acquire(self):
        """Block until a rate-limit slot is available, then consume it."""
        while True:
            with self._lock:
                now = time.time()
                # Purge timestamps older than the window
                self._timestamps = [t for t in self._timestamps if now - t < self.window]

                if len(self._timestamps) < self.max_calls:
                    self._timestamps.append(now)
                    return  # Slot acquired

                # Calculate wait time until the oldest timestamp expires
                wait = self.window - (now - self._timestamps[0]) + 0.1

            log.info(f"[RateLimiter] Limit reached ({self.max_calls}/min). Waiting {wait:.1f}s...")
            time.sleep(wait)


# Module-level singleton for GROQ rate limiting
GROQ_limiter = RateLimiter()
