"""
test_gemini.py — Tests for Gemini fallback, dynamic batching, and distributed rate limiting.

Tests run without any actual Gemini/LLM API calls or trace infrastructure.

Coverage:
  1. Dynamic batch sizing (compute_batches)
  2. Model fallback on HTTP 429
  3. Distributed rate limiter (RedisRateLimiter / RedisSemaphore)
     - Redis-backed cross-process limiting
     - Local fallback when Redis is unavailable
  4. Pipeline integration (end-to-end with mocked LLM + no trace)
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from openai import RateLimitError

from structuring.slide_agent import (
    compute_batches,
    run_slide_agent,
    GeminiQuotaExhausted,
    _is_rate_limit_error,
    build_instructions_slide_agent,
    _fallback_metadata,
)
from structuring.rate_limiter import (
    RedisRateLimiter,
    RedisSemaphore,
    semaphore_slot,
    _LocalRateLimiter,
    _LocalSemaphore,
    reset_redis_state,
    _get_redis,
)
from structuring.config import (
    SLIDE_BATCH_SIZE,
    SLIDE_BATCH_MERGE_THRESHOLD,
    GEMINI_MODEL,
    GEMINI_FALLBACK_MODEL,
)
from structuring.schemas import (
    ParsedSlide,
    DocumentOverview,
    ChapterInfo,
    SlideMetadata,
    SlideType,
    SlideBatchResponse,
)


# ═════════════════════════════════════════════════════════════════════════
# Helpers — build fake objects without touching any API
# ═════════════════════════════════════════════════════════════════════════

def _make_slides(n: int) -> list[ParsedSlide]:
    return [
        ParsedSlide(
            slide_number=i + 1,
            header=f"Slide {i + 1}",
            content=f"Content of slide {i + 1}",
            preview=f"Preview {i + 1}",
        )
        for i in range(n)
    ]


def _make_overview() -> DocumentOverview:
    return DocumentOverview(
        document_title="Test Document",
        subject="TestSubject",
        overarching_summary="A test document.",
        chapters=[
            ChapterInfo(chapter_name="Ch1", slide_range="1-10", key_topics=["topic1"]),
        ],
        total_slides=10,
        ai_subject="TestSubject",
    )


def _make_batch_response(slide_numbers: list[int]) -> SlideBatchResponse:
    return SlideBatchResponse(
        slides=[
            SlideMetadata(
                slide_number=n,
                parent_topic="Ch1",
                slide_type=SlideType.CONCEPT,
                core_concepts=["test"],
                exam_signals=False,
                slide_summary=f"Summary for slide {n}",
                chapter="Ch1",
            )
            for n in slide_numbers
        ]
    )


def _make_429_error() -> RateLimitError:
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {}
    mock_response.json.return_value = {"error": {"message": "rate limit exceeded"}}
    return RateLimitError(
        message="rate limit exceeded",
        response=mock_response,
        body={"error": {"message": "rate limit exceeded"}},
    )


def _patch_limiter():
    """Patch the distributed rate limiter to be a no-op (instant acquire)."""
    return patch("structuring.slide_agent._limiter.acquire", new_callable=AsyncMock)


def _patch_custom_span():
    """Patch custom_span to be a no-op context manager."""
    class _FakeSpan:
        def __enter__(self): return self
        def __exit__(self, *a): pass
    return patch("structuring.slide_agent.custom_span", return_value=_FakeSpan())


def _parse_slide_nums_from_content(content: str) -> list[int]:
    """Extract slide numbers from batch content text."""
    nums = []
    for line in content.split("\n"):
        if line.startswith("--- Slide "):
            num = int(line.split("--- Slide ")[1].split(" ---")[0])
            nums.append(num)
    return nums


def _auto_response(**kwargs) -> MagicMock:
    """Build a mock Gemini response that matches the input slides."""
    nums = _parse_slide_nums_from_content(kwargs["messages"][1]["content"])
    resp = _make_batch_response(nums)
    mock = MagicMock()
    mock.choices = [MagicMock()]
    mock.choices[0].message.parsed = resp
    return mock


# ═════════════════════════════════════════════════════════════════════════
# 1. Dynamic Batch Sizing — compute_batches()
# ═════════════════════════════════════════════════════════════════════════

class TestComputeBatches:

    def test_zero_slides(self):
        assert compute_batches(0) == []

    def test_single_slide(self):
        assert compute_batches(1) == [(0, 1)]

    def test_exact_batch_size(self):
        batches = compute_batches(SLIDE_BATCH_SIZE)
        assert len(batches) == 1
        assert batches == [(0, SLIDE_BATCH_SIZE)]

    def test_merge_small_remainder(self):
        """32 slides (25+7) → 1 call instead of 2."""
        total = SLIDE_BATCH_SIZE + 7
        batches = compute_batches(total)
        assert len(batches) == 1
        assert batches == [(0, total)]

    def test_merge_at_threshold(self):
        """37 slides (25+12) at boundary → still 1 batch."""
        total = SLIDE_BATCH_SIZE + SLIDE_BATCH_MERGE_THRESHOLD
        batches = compute_batches(total)
        assert len(batches) == 1

    def test_beyond_merge_threshold(self):
        """38 slides → 2 batches."""
        total = SLIDE_BATCH_SIZE + SLIDE_BATCH_MERGE_THRESHOLD + 1
        batches = compute_batches(total)
        assert len(batches) == 2
        assert sum(e - s for s, e in batches) == total

    def test_50_slides_exact_split(self):
        batches = compute_batches(50)
        assert len(batches) == 2
        assert batches == [(0, 25), (25, 50)]

    def test_large_count_even_distribution(self):
        batches = compute_batches(60)
        sizes = [e - s for s, e in batches]
        assert sum(sizes) == 60
        assert max(sizes) - min(sizes) <= 1

    def test_coverage_always_complete(self):
        for total in [1, 10, 25, 32, 37, 38, 50, 52, 75, 100]:
            batches = compute_batches(total)
            assert sum(e - s for s, e in batches) == total
            for i in range(1, len(batches)):
                assert batches[i][0] == batches[i - 1][1]


# ═════════════════════════════════════════════════════════════════════════
# 2. Rate Limit Error Detection
# ═════════════════════════════════════════════════════════════════════════

class TestRateLimitDetection:

    def test_openai_rate_limit_error(self):
        assert _is_rate_limit_error(_make_429_error()) is True

    def test_generic_exception_not_rate_limit(self):
        assert _is_rate_limit_error(ValueError("x")) is False

    def test_status_code_429_attribute(self):
        err = Exception("quota exceeded")
        err.status_code = 429
        assert _is_rate_limit_error(err) is True

    def test_status_code_500_not_rate_limit(self):
        err = Exception("server error")
        err.status_code = 500
        assert _is_rate_limit_error(err) is False


# ═════════════════════════════════════════════════════════════════════════
# 3. Fallback Logic — run_slide_agent() with mocked Gemini
# ═════════════════════════════════════════════════════════════════════════

class TestFallbackLogic:

    @pytest.mark.asyncio
    async def test_primary_model_success_no_fallback(self):
        slides = _make_slides(5)
        overview = _make_overview()
        expected = _make_batch_response([s.slide_number for s in slides])

        mock_parsed = MagicMock()
        mock_parsed.choices = [MagicMock()]
        mock_parsed.choices[0].message.parsed = expected

        with _patch_limiter(), _patch_custom_span():
            with patch("structuring.slide_agent.AsyncOpenAI") as MockClient:
                instance = MockClient.return_value
                instance.beta.chat.completions.parse = AsyncMock(return_value=mock_parsed)

                result = await run_slide_agent(overview, slides)

                call_args = instance.beta.chat.completions.parse.call_args
                assert call_args.kwargs["model"] == GEMINI_MODEL
                assert len(result) == 5

    @pytest.mark.asyncio
    async def test_429_triggers_fallback_model(self):
        slides = _make_slides(5)
        overview = _make_overview()

        expected = _make_batch_response([s.slide_number for s in slides])
        mock_parsed = MagicMock()
        mock_parsed.choices = [MagicMock()]
        mock_parsed.choices[0].message.parsed = expected

        call_count = 0

        async def _fake_parse(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                assert kwargs["model"] == GEMINI_MODEL
                raise _make_429_error()
            else:
                assert kwargs["model"] == GEMINI_FALLBACK_MODEL
                return mock_parsed

        with _patch_limiter(), _patch_custom_span():
            with patch("structuring.slide_agent.AsyncOpenAI") as MockClient:
                instance = MockClient.return_value
                instance.beta.chat.completions.parse = AsyncMock(side_effect=_fake_parse)

                result = await run_slide_agent(overview, slides)
                assert call_count == 2
                assert len(result) == 5

    @pytest.mark.asyncio
    async def test_both_models_429_raises_quota_exhausted(self):
        slides = _make_slides(5)
        overview = _make_overview()

        with _patch_limiter(), _patch_custom_span():
            with patch("structuring.slide_agent.AsyncOpenAI") as MockClient:
                instance = MockClient.return_value
                instance.beta.chat.completions.parse = AsyncMock(
                    side_effect=lambda **kw: (_ for _ in ()).throw(_make_429_error())
                )

                with pytest.raises(GeminiQuotaExhausted) as exc_info:
                    await run_slide_agent(overview, slides)

                msg = str(exc_info.value)
                assert "daily quota exhausted" in msg
                assert "re-upload" in msg
                assert "tomorrow" in msg

    @pytest.mark.asyncio
    async def test_non_429_error_returns_placeholder(self):
        slides = _make_slides(3)
        overview = _make_overview()

        with _patch_limiter(), _patch_custom_span():
            with patch("structuring.slide_agent.AsyncOpenAI") as MockClient:
                instance = MockClient.return_value
                instance.beta.chat.completions.parse = AsyncMock(
                    side_effect=ValueError("Internal server error")
                )

                result = await run_slide_agent(overview, slides)
                assert len(result) == 3
                for meta in result:
                    assert meta.slide_type == SlideType.OTHER
                    assert "[Classification failed]" in meta.slide_summary

    @pytest.mark.asyncio
    async def test_dynamic_batching_saves_api_call(self):
        """32 slides → exactly 1 API call, not 2."""
        slides = _make_slides(32)
        overview = _make_overview()

        with _patch_limiter(), _patch_custom_span():
            with patch("structuring.slide_agent.AsyncOpenAI") as MockClient:
                instance = MockClient.return_value
                instance.beta.chat.completions.parse = AsyncMock(side_effect=_auto_response)

                result = await run_slide_agent(overview, slides)
                assert instance.beta.chat.completions.parse.call_count == 1
                assert len(result) == 32

    @pytest.mark.asyncio
    async def test_50_slides_needs_two_calls(self):
        slides = _make_slides(50)
        overview = _make_overview()

        with _patch_limiter(), _patch_custom_span():
            with patch("structuring.slide_agent.AsyncOpenAI") as MockClient:
                instance = MockClient.return_value
                instance.beta.chat.completions.parse = AsyncMock(side_effect=_auto_response)

                result = await run_slide_agent(overview, slides)
                assert instance.beta.chat.completions.parse.call_count == 2
                assert len(result) == 50

    @pytest.mark.asyncio
    async def test_fallback_sticks_for_subsequent_batches(self):
        """Once fallback is activated, subsequent batches use fallback model."""
        slides = _make_slides(50)
        overview = _make_overview()

        models_called = []

        async def _track_model(**kwargs):
            model = kwargs["model"]
            models_called.append(model)
            if model == GEMINI_MODEL:
                raise _make_429_error()
            return _auto_response(**kwargs)

        with _patch_limiter(), _patch_custom_span():
            with patch("structuring.slide_agent.AsyncOpenAI") as MockClient:
                instance = MockClient.return_value
                instance.beta.chat.completions.parse = AsyncMock(side_effect=_track_model)

                result = await run_slide_agent(overview, slides)
                assert len(result) == 50
                assert GEMINI_MODEL in models_called
                assert GEMINI_FALLBACK_MODEL in models_called


# ═════════════════════════════════════════════════════════════════════════
# 4. Distributed Rate Limiter — RedisRateLimiter
# ═════════════════════════════════════════════════════════════════════════

class TestRedisRateLimiter:
    """Test the distributed rate limiter with a fake Redis."""

    def _make_fake_redis(self):
        """Build a mock Redis that simulates sorted-set rate limiting."""
        store = {}  # key -> list of (member, score) tuples

        def _zremrangebyscore(key, lo, hi):
            if key not in store:
                return 0
            hi = float(hi)
            before = len(store[key])
            store[key] = [(m, s) for m, s in store[key] if s > hi]
            return before - len(store[key])

        def _zcard(key):
            return len(store.get(key, []))

        def _zadd(key, mapping):
            if key not in store:
                store[key] = []
            for member, score in mapping.items():
                store[key].append((member, score))

        def _zrange(key, start, end, withscores=False):
            items = store.get(key, [])
            items.sort(key=lambda x: x[1])
            sliced = items[start:end + 1] if end >= 0 else items[start:]
            if withscores:
                return sliced
            return [m for m, s in sliced]

        def _expire(key, ttl):
            pass

        mock_redis = MagicMock()
        mock_redis.zremrangebyscore = MagicMock(side_effect=_zremrangebyscore)
        mock_redis.zcard = MagicMock(side_effect=_zcard)
        mock_redis.zadd = MagicMock(side_effect=_zadd)
        mock_redis.zrange = MagicMock(side_effect=_zrange)
        mock_redis.expire = MagicMock(side_effect=_expire)

        # Pipeline support
        pipe_mock = MagicMock()
        pipe_mock.zremrangebyscore = MagicMock(side_effect=lambda *a: None)
        pipe_mock.zcard = MagicMock(side_effect=lambda *a: None)

        def _pipe_execute():
            _zremrangebyscore("examai:rate_limit:test_limiter", "-inf", time.time() - 60.0)
            count = _zcard("examai:rate_limit:test_limiter")
            return [None, count]

        pipe_mock.execute = MagicMock(side_effect=_pipe_execute)
        mock_redis.pipeline = MagicMock(return_value=pipe_mock)

        return mock_redis, store

    @pytest.mark.asyncio
    async def test_redis_limiter_allows_within_limit(self):
        """Calls within the limit should pass immediately."""
        fake_redis, store = self._make_fake_redis()

        with patch("structuring.rate_limiter._get_redis", return_value=fake_redis):
            limiter = RedisRateLimiter("test_limiter", max_calls=5, window=60.0)
            for _ in range(5):
                await limiter.acquire()

        # 5 entries should be in the sorted set
        assert len(store.get("examai:rate_limit:test_limiter", [])) == 5

    @pytest.mark.asyncio
    async def test_redis_limiter_blocks_over_limit(self):
        """Calls over the limit should block (we verify by timeout)."""
        fake_redis, store = self._make_fake_redis()

        with patch("structuring.rate_limiter._get_redis", return_value=fake_redis):
            limiter = RedisRateLimiter("test_limiter", max_calls=2, window=60.0)
            await limiter.acquire()
            await limiter.acquire()

            # Third call should block — verify via timeout
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(limiter.acquire(), timeout=0.3)

    @pytest.mark.asyncio
    async def test_local_fallback_when_redis_unavailable(self):
        """When Redis is None, falls back to local in-process limiter."""
        with patch("structuring.rate_limiter._get_redis", return_value=None):
            limiter = RedisRateLimiter("test_local", max_calls=3, window=60.0)
            # Should work using local fallback without error
            for _ in range(3):
                await limiter.acquire()

            # Fourth should block
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(limiter.acquire(), timeout=0.3)

    @pytest.mark.asyncio
    async def test_redis_error_falls_back_to_local(self):
        """If Redis raises during acquire, falls back gracefully."""
        broken_redis = MagicMock()
        broken_redis.pipeline.side_effect = ConnectionError("Redis connection lost")

        with patch("structuring.rate_limiter._get_redis", return_value=broken_redis):
            limiter = RedisRateLimiter("test_broken", max_calls=5, window=60.0)
            # Should not crash — falls back to local
            await limiter.acquire()

    @pytest.mark.asyncio
    async def test_multiple_limiters_share_redis_key(self):
        """Two limiter instances with same name share the same Redis key.
        Simulates two worker processes sharing a global limit."""
        fake_redis, store = self._make_fake_redis()

        with patch("structuring.rate_limiter._get_redis", return_value=fake_redis):
            # Simulate Worker 1 and Worker 2 with separate limiter instances
            worker1_limiter = RedisRateLimiter("test_limiter", max_calls=3, window=60.0)
            worker2_limiter = RedisRateLimiter("test_limiter", max_calls=3, window=60.0)

            await worker1_limiter.acquire()  # count = 1
            await worker2_limiter.acquire()  # count = 2
            await worker1_limiter.acquire()  # count = 3

            # Fourth call from any worker should block — global limit hit
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(worker2_limiter.acquire(), timeout=0.3)


# ═════════════════════════════════════════════════════════════════════════
# 5. Distributed Semaphore — RedisSemaphore
# ═════════════════════════════════════════════════════════════════════════

class TestRedisSemaphore:

    def _make_fake_redis(self):
        """Build a mock Redis that simulates sorted-set semaphore with Lua script support."""
        store = {}

        def _zremrangebyscore(key, lo, hi):
            if key not in store:
                return 0
            hi = float(hi)
            before = len(store[key])
            store[key] = [(m, s) for m, s in store[key] if s > hi]
            return before - len(store[key])

        def _zcard(key):
            return len(store.get(key, []))

        def _zadd(key, mapping):
            if key not in store:
                store[key] = []
            for member, score in mapping.items():
                store[key].append((member, score))

        def _zrem(key, member):
            if key in store:
                store[key] = [(m, s) for m, s in store[key] if m != member]

        def _expire(key, ttl):
            pass

        def _register_script(lua_src):
            """Return a callable that emulates the atomic acquire Lua script."""
            def _run_script(keys, args):
                key = keys[0]
                stale_thr = float(args[0])
                max_c = int(args[1])
                holder = args[2]
                now = float(args[3])
                # Prune stale
                _zremrangebyscore(key, "-inf", stale_thr)
                # Check count + add if room
                if _zcard(key) < max_c:
                    _zadd(key, {holder: now})
                    return 1
                return 0
            return _run_script

        mock_redis = MagicMock()
        mock_redis.zremrangebyscore = MagicMock(side_effect=_zremrangebyscore)
        mock_redis.zcard = MagicMock(side_effect=_zcard)
        mock_redis.zadd = MagicMock(side_effect=_zadd)
        mock_redis.zrem = MagicMock(side_effect=_zrem)
        mock_redis.expire = MagicMock(side_effect=_expire)
        mock_redis.register_script = MagicMock(side_effect=_register_script)
        return mock_redis, store

    @pytest.mark.asyncio
    async def test_semaphore_allows_within_limit(self):
        fake_redis, store = self._make_fake_redis()

        with patch("structuring.rate_limiter._get_redis", return_value=fake_redis):
            sem = RedisSemaphore("test_sem", max_concurrent=2, ttl=60.0)
            await sem.acquire()  # holder 1
            assert len(store.get("examai:semaphore:test_sem", [])) == 1

    @pytest.mark.asyncio
    async def test_semaphore_release_frees_slot(self):
        fake_redis, store = self._make_fake_redis()

        with patch("structuring.rate_limiter._get_redis", return_value=fake_redis):
            sem = RedisSemaphore("test_sem", max_concurrent=1, ttl=60.0)
            holder = await sem.acquire()
            assert len(store["examai:semaphore:test_sem"]) == 1

            sem.release(holder)
            assert len(store["examai:semaphore:test_sem"]) == 0

    @pytest.mark.asyncio
    async def test_semaphore_blocks_over_limit(self):
        fake_redis, store = self._make_fake_redis()

        with patch("structuring.rate_limiter._get_redis", return_value=fake_redis):
            sem1 = RedisSemaphore("test_sem", max_concurrent=1, ttl=60.0)
            sem2 = RedisSemaphore("test_sem", max_concurrent=1, ttl=60.0)

            await sem1.acquire()

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(sem2.acquire(), timeout=0.5)

    @pytest.mark.asyncio
    async def test_semaphore_context_manager(self):
        fake_redis, store = self._make_fake_redis()

        with patch("structuring.rate_limiter._get_redis", return_value=fake_redis):
            sem = RedisSemaphore("test_ctx", max_concurrent=1, ttl=60.0)

            async with semaphore_slot(sem):
                assert len(store["examai:semaphore:test_ctx"]) == 1

            # After exiting context, slot should be released
            assert len(store["examai:semaphore:test_ctx"]) == 0

    @pytest.mark.asyncio
    async def test_semaphore_local_fallback(self):
        """Without Redis, semaphore uses local threading.Semaphore."""
        with patch("structuring.rate_limiter._get_redis", return_value=None):
            sem = RedisSemaphore("test_local", max_concurrent=2, ttl=60.0)
            await sem.acquire()
            await sem.acquire()

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(sem.acquire(), timeout=0.3)


# ═════════════════════════════════════════════════════════════════════════
# 6. Local Fallback Unit Tests
# ═════════════════════════════════════════════════════════════════════════

class TestLocalFallbacks:

    @pytest.mark.asyncio
    async def test_local_rate_limiter_enforces_limit(self):
        limiter = _LocalRateLimiter(max_calls=2, window=60.0)
        await limiter.acquire()
        await limiter.acquire()

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(limiter.acquire(), timeout=0.3)

    @pytest.mark.asyncio
    async def test_local_semaphore_enforces_concurrency(self):
        sem = _LocalSemaphore(max_concurrent=1)
        await sem.acquire()

        # Can't acquire second without release
        acquired = False

        async def _try_acquire():
            nonlocal acquired
            await sem.acquire()
            acquired = True

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(_try_acquire(), timeout=0.3)

        assert acquired is False
        sem.release()

        # Now it should work
        await asyncio.wait_for(_try_acquire(), timeout=1.0)
        assert acquired is True


# ═════════════════════════════════════════════════════════════════════════
# 7. Pipeline Integration — full slide_agent flow without LLM or trace
# ═════════════════════════════════════════════════════════════════════════

class TestPipelineIntegration:
    """End-to-end tests of run_slide_agent with all LLM and trace mocked out."""

    @pytest.mark.asyncio
    async def test_full_pipeline_small_doc(self):
        """10 slides → 1 batch, all classified, sorted output."""
        slides = _make_slides(10)
        overview = _make_overview()

        with _patch_limiter(), _patch_custom_span():
            with patch("structuring.slide_agent.AsyncOpenAI") as MockClient:
                instance = MockClient.return_value
                instance.beta.chat.completions.parse = AsyncMock(side_effect=_auto_response)

                result = await run_slide_agent(overview, slides)

                assert len(result) == 10
                # Output is sorted by slide_number
                assert [m.slide_number for m in result] == list(range(1, 11))
                # All have correct type
                assert all(m.slide_type == SlideType.CONCEPT for m in result)

    @pytest.mark.asyncio
    async def test_full_pipeline_medium_doc(self):
        """35 slides → 1 batch (merged), correct count."""
        slides = _make_slides(35)
        overview = _make_overview()

        with _patch_limiter(), _patch_custom_span():
            with patch("structuring.slide_agent.AsyncOpenAI") as MockClient:
                instance = MockClient.return_value
                instance.beta.chat.completions.parse = AsyncMock(side_effect=_auto_response)

                result = await run_slide_agent(overview, slides)

                assert len(result) == 35
                assert instance.beta.chat.completions.parse.call_count == 1

    @pytest.mark.asyncio
    async def test_full_pipeline_large_doc(self):
        """75 slides → 3 batches, all 75 classified and sorted."""
        slides = _make_slides(75)
        overview = _make_overview()

        with _patch_limiter(), _patch_custom_span():
            with patch("structuring.slide_agent.AsyncOpenAI") as MockClient:
                instance = MockClient.return_value
                instance.beta.chat.completions.parse = AsyncMock(side_effect=_auto_response)

                result = await run_slide_agent(overview, slides)

                assert len(result) == 75
                assert instance.beta.chat.completions.parse.call_count == 3
                assert [m.slide_number for m in result] == list(range(1, 76))

    @pytest.mark.asyncio
    async def test_partial_failure_recovers(self):
        """If one batch fails (non-429), others still succeed. No crash."""
        slides = _make_slides(50)  # 2 batches
        overview = _make_overview()

        call_count = 0

        async def _fail_first_batch(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Simulated API error")
            return _auto_response(**kwargs)

        with _patch_limiter(), _patch_custom_span():
            with patch("structuring.slide_agent.AsyncOpenAI") as MockClient:
                instance = MockClient.return_value
                instance.beta.chat.completions.parse = AsyncMock(side_effect=_fail_first_batch)

                result = await run_slide_agent(overview, slides)

                assert len(result) == 50
                # First batch should have fallback metadata
                failed_slides = [m for m in result if "[Classification failed]" in m.slide_summary]
                success_slides = [m for m in result if "[Classification failed]" not in m.slide_summary]
                assert len(failed_slides) == 25
                assert len(success_slides) == 25

    @pytest.mark.asyncio
    async def test_429_fallback_pipeline_completes(self):
        """Primary 429 → fallback model → pipeline still completes."""
        slides = _make_slides(25)
        overview = _make_overview()

        models_used = []

        async def _primary_429(**kwargs):
            models_used.append(kwargs["model"])
            if kwargs["model"] == GEMINI_MODEL:
                raise _make_429_error()
            return _auto_response(**kwargs)

        with _patch_limiter(), _patch_custom_span():
            with patch("structuring.slide_agent.AsyncOpenAI") as MockClient:
                instance = MockClient.return_value
                instance.beta.chat.completions.parse = AsyncMock(side_effect=_primary_429)

                result = await run_slide_agent(overview, slides)

                assert len(result) == 25
                assert GEMINI_MODEL in models_used
                assert GEMINI_FALLBACK_MODEL in models_used

    @pytest.mark.asyncio
    async def test_empty_slides_returns_empty(self):
        """0 slides → 0 batches, empty result."""
        overview = _make_overview()

        with _patch_limiter(), _patch_custom_span():
            with patch("structuring.slide_agent.AsyncOpenAI") as MockClient:
                instance = MockClient.return_value
                result = await run_slide_agent(overview, [])
                assert result == []
                assert instance.beta.chat.completions.parse.call_count == 0


# ═════════════════════════════════════════════════════════════════════════
# Run with: pytest test_gemini.py -v
# ═════════════════════════════════════════════════════════════════════════
