"""
engine/llm.py — Smart multi-model Groq client with rate tracking and fallback.

Strategy:
  1. Round-robin primary model selection to spread load across models.
  2. Proactive rate-limit checks (RPM, TPM, TPD) before calling.
  3. On 429 or quota error → automatically fallback to next model.
  4. For large contexts → split into chunks and distribute across models
     in parallel (chunk 1 → model A, chunk 2 → model B, ...).

All state is in-memory (resets on restart — intentional, since Groq
resets per-minute counters on their side too).
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field

from openai import AsyncOpenAI, RateLimitError, APIStatusError

from engine.config import (
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_MODELS,
    CHUNK_SIZE_CHARS,
)

log = logging.getLogger(__name__)

_client = AsyncOpenAI(base_url=GROQ_BASE_URL, api_key=GROQ_API_KEY)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    return max(len(text) // 4, 1)


# ── Per-model rate tracker ───────────────────────────────────────────────

@dataclass
class _ModelTracker:
    """Tracks usage counters for a single model."""
    model: str
    rpm: int              # max requests per minute
    tpm: int              # max tokens per minute
    rpd: int              # max requests per day
    tpd: int              # max tokens per day

    # Minute-window counters
    _req_min: int = 0
    _tok_min: int = 0
    _min_start: float = field(default_factory=time.time)

    # Day-window counters
    _req_day: int = 0
    _tok_day: int = 0
    _day_start: float = field(default_factory=time.time)

    # Backoff: set when we get a 429
    _blocked_until: float = 0.0

    def _reset_minute(self):
        now = time.time()
        if now - self._min_start >= 60:
            self._req_min = 0
            self._tok_min = 0
            self._min_start = now

    def _reset_day(self):
        now = time.time()
        if now - self._day_start >= 86400:
            self._req_day = 0
            self._tok_day = 0
            self._day_start = now

    def can_send(self, est_tokens: int) -> bool:
        """Check if this model can accept a request with estimated token count."""
        if time.time() < self._blocked_until:
            return False
        self._reset_minute()
        self._reset_day()

        if self._req_min >= self.rpm:
            return False
        if self._tok_min + est_tokens > self.tpm:
            return False
        if self._req_day >= self.rpd:
            return False
        if self._tok_day + est_tokens > self.tpd:
            return False
        return True

    def record_usage(self, tokens: int):
        """Record a successful request."""
        self._reset_minute()
        self._reset_day()
        self._req_min += 1
        self._tok_min += tokens
        self._req_day += 1
        self._tok_day += tokens

    def mark_blocked(self, seconds: float = 60):
        """Mark model as blocked after a 429 response."""
        self._blocked_until = time.time() + seconds
        log.warning(f"[LLM] Model '{self.model}' rate-limited, blocked for {seconds}s")

    @property
    def day_tokens_remaining(self) -> int:
        self._reset_day()
        return max(self.tpd - self._tok_day, 0)


# ── Model pool ───────────────────────────────────────────────────────────

class ModelPool:
    """
    Round-robin model pool with automatic fallback.

    Usage:
        pool = ModelPool()
        text = await pool.complete(system, user)
        text = await pool.complete_chunked(system, chunks, merge_system)
    """

    def __init__(self):
        self._trackers = [
            _ModelTracker(
                model=cfg["model"],
                rpm=cfg["rpm"],
                tpm=cfg["tpm"],
                rpd=cfg["rpd"],
                tpd=cfg["tpd"],
            )
            for cfg in GROQ_MODELS
        ]
        self._rr_index = 0  # round-robin counter

    def _pick_model(self, est_tokens: int) -> _ModelTracker | None:
        """Pick the next available model using round-robin + fallback."""
        n = len(self._trackers)
        # Try starting from round-robin position
        for offset in range(n):
            idx = (self._rr_index + offset) % n
            t = self._trackers[idx]
            if t.can_send(est_tokens):
                self._rr_index = (idx + 1) % n
                return t
        return None

    def get_best_model_name(self, est_tokens: int = 500) -> str:
        """Return the model name that should be used next (for agent init)."""
        t = self._pick_model(est_tokens)
        return t.model if t else self._trackers[0].model

    async def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 2500,
    ) -> tuple[str, str]:
        """
        Single chat completion with automatic model fallback.

        Returns (response_text, model_used).
        Raises RuntimeError if all models are exhausted.
        """
        est = _estimate_tokens(system + user)

        for attempt in range(len(self._trackers)):
            tracker = self._pick_model(est)
            if tracker is None:
                # All models rate-limited — wait 30s and try once more
                log.warning("[LLM] All models busy, waiting 30s ...")
                await asyncio.sleep(30)
                tracker = self._pick_model(est)
                if tracker is None:
                    raise RuntimeError("All Groq models are rate-limited. Try again later.")

            try:
                resp = await _client.chat.completions.create(
                    model=tracker.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                used = (resp.usage.total_tokens if resp.usage else est)
                tracker.record_usage(used)
                text = resp.choices[0].message.content or ""
                log.info(f"[LLM] {tracker.model}: {used} tokens")
                return text, tracker.model

            except RateLimitError:
                tracker.mark_blocked(60)
                continue
            except APIStatusError as e:
                if e.status_code == 429:
                    tracker.mark_blocked(60)
                    continue
                raise

        raise RuntimeError("All Groq models failed after retries.")

    async def complete_chunked(
        self,
        system: str,
        chunks: list[str],
        merge_system: str = "",
        temperature: float = 0.3,
        max_tokens: int = 2500,
    ) -> tuple[str, str]:
        """
        Process multiple context chunks in parallel across models, then merge.

        Each chunk is sent as a separate LLM call. Chunks are distributed
        across models to avoid hitting any single model's rate limit.

        If only 1 chunk → behaves like complete().

        Returns (merged_response, models_used_csv).
        """
        if len(chunks) <= 1:
            return await self.complete(
                system, chunks[0] if chunks else "", temperature, max_tokens,
            )

        # Fire all chunks in parallel
        async def _do_chunk(chunk_text: str) -> tuple[str, str]:
            return await self.complete(system, chunk_text, temperature, max_tokens)

        results = await asyncio.gather(
            *[_do_chunk(c) for c in chunks],
            return_exceptions=True,
        )

        # Collect successful responses
        partial_answers: list[str] = []
        models_used: set[str] = set()
        for r in results:
            if isinstance(r, Exception):
                log.warning(f"[LLM] Chunk failed: {r}")
                continue
            text, model = r
            partial_answers.append(text)
            models_used.add(model)

        if not partial_answers:
            raise RuntimeError("All chunk calls failed.")

        if len(partial_answers) == 1:
            return partial_answers[0], ",".join(models_used)

        # Merge partial answers with a final LLM call
        merge_prompt = (
            "Combine these partial responses into a single coherent answer. "
            "Remove duplicates, keep all slide references, maintain structure.\n\n"
            + "\n\n---\n\n".join(
                f"[Part {i+1}]\n{a}" for i, a in enumerate(partial_answers)
            )
        )
        final_system = merge_system or system
        merged, merge_model = await self.complete(
            final_system, merge_prompt, temperature, max_tokens,
        )
        models_used.add(merge_model)
        return merged, ",".join(models_used)


# ── Chunking helper ──────────────────────────────────────────────────────

def chunk_text(text: str, max_chars: int = CHUNK_SIZE_CHARS) -> list[str]:
    """
    Split text into chunks, breaking at double-newlines when possible.
    Returns a list of chunks each ≤ max_chars.
    """
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        # Try to break at a double-newline
        cut = remaining[:max_chars].rfind("\n\n")
        if cut < max_chars // 3:
            # No good break point — try single newline
            cut = remaining[:max_chars].rfind("\n")
        if cut < max_chars // 3:
            cut = max_chars
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()

    return chunks


# ── Module-level singleton ───────────────────────────────────────────────
pool = ModelPool()
