"""
Regression tests for LLM model fallback.

These exist because of a real outage. Two of the three ids in GROQ_MODELS were
decommissioned by the provider and began returning HTTP 404. `complete()`
handled 429 but re-raised everything else, so a 404 propagated instead of
falling through to the next model in the chain, and 4 of every 6 requests
failed. Reasoning mode was worse: `get_best_model_name()` handed it a dead
model with no round-robin to rescue it, so it failed every time.

The distinction that matters: a 429 is transient and the model should be
retried shortly; a 404 never recovers on its own, because the id is gone until
someone edits the config. Treating them the same in either direction is wrong -
retrying a retired model forever wastes a request per round, and giving up on a
rate-limited one throws away capacity.

Driven entirely with a stub client, so no network and no API key.
"""

import asyncio

import httpx
import pytest
from openai import APIStatusError, RateLimitError

from engine import llm as llm_mod
from engine.llm import ModelPool


def _response(status: int) -> httpx.Response:
    return httpx.Response(status_code=status,
                          request=httpx.Request("POST", "http://stub/chat"))


def _status_error(status: int) -> APIStatusError:
    body = {"error": {"message": f"stubbed {status}"}}
    if status == 429:
        return RateLimitError("rate limited", response=_response(429), body=body)
    return APIStatusError(f"status {status}", response=_response(status), body=body)


class _StubCompletions:
    """Fails for named models, succeeds for the rest, and records every call."""

    def __init__(self, failures: dict[str, int]):
        self.failures = failures
        self.calls: list[str] = []

    async def create(self, *, model, messages, temperature=0.3, max_tokens=None):
        self.calls.append(model)
        if model in self.failures:
            raise _status_error(self.failures[model])

        class _Usage:
            total_tokens = 42

        class _Msg:
            content = f"answer from {model}"

        class _Choice:
            message = _Msg()

        class _Resp:
            usage = _Usage()
            choices = [_Choice()]

        return _Resp()


class _StubClient:
    def __init__(self, failures):
        self.chat = type("chat", (), {})()
        self.chat.completions = _StubCompletions(failures)


@pytest.fixture()
def pool(monkeypatch):
    monkeypatch.setattr(llm_mod, "GROQ_MODELS", [
        {"model": "dead-a", "rpm": 60, "tpm": 100_000, "rpd": 1000, "tpd": 1_000_000},
        {"model": "alive-b", "rpm": 60, "tpm": 100_000, "rpd": 1000, "tpd": 1_000_000},
        {"model": "dead-c", "rpm": 60, "tpm": 100_000, "rpd": 1000, "tpd": 1_000_000},
    ])
    return ModelPool()


def _install(monkeypatch, failures):
    stub = _StubClient(failures)
    monkeypatch.setattr(llm_mod, "_client", stub)
    return stub.chat.completions


# ── the bug this file exists for ─────────────────────────────────────────

def test_404_falls_back_instead_of_raising(pool, monkeypatch):
    """The outage: a decommissioned model must not take the request down."""
    calls = _install(monkeypatch, {"dead-a": 404, "dead-c": 404})
    text, used = asyncio.run(pool.complete("sys", "user"))
    assert used == "alive-b"
    assert text == "answer from alive-b"
    assert "dead-a" in calls.calls or "dead-c" in calls.calls, \
        "a dead model should have been attempted before falling back"


def test_404_retires_the_model_for_later_requests(pool, monkeypatch):
    """A 404 never recovers, so the model should stop being attempted."""
    calls = _install(monkeypatch, {"dead-a": 404, "dead-c": 404})
    for _ in range(4):
        _, used = asyncio.run(pool.complete("sys", "user"))
        assert used == "alive-b"
    assert calls.calls.count("dead-a") <= 1
    assert calls.calls.count("dead-c") <= 1
    assert sorted(pool.unavailable_models()) == ["dead-a", "dead-c"]
    assert pool.available_models() == ["alive-b"]


def test_get_best_model_name_never_returns_a_KNOWN_retired_model(pool, monkeypatch):
    """Reasoning mode builds its agent from this and has no fallback.

    The guarantee is deliberately "never a model KNOWN to be dead", not "never
    a dead model": a model that has not been tried yet is indistinguishable
    from a live one, and discovering otherwise costs a request. The /models
    health endpoint exists to find those proactively.
    """
    _install(monkeypatch, {"dead-a": 404, "dead-c": 404})
    for _ in range(6):                       # enough rounds to meet every id
        asyncio.run(pool.complete("sys", "user"))
    assert sorted(pool.unavailable_models()) == ["dead-a", "dead-c"]
    for _ in range(3):
        assert pool.get_best_model_name() == "alive-b"


def test_get_best_model_name_prefers_live_over_known_dead(pool, monkeypatch):
    """Even when every live model is rate-limited, never hand back a dead id."""
    _install(monkeypatch, {"dead-a": 404, "dead-c": 404})
    asyncio.run(pool.complete("sys", "user"))          # retires dead-a
    for t in pool._trackers:
        if t.model == "alive-b":
            t.mark_blocked(60)                          # busy, but alive
    assert pool.get_best_model_name() != "dead-a"


def test_all_models_dead_raises_a_message_that_names_the_cause(pool, monkeypatch):
    _install(monkeypatch, {"dead-a": 404, "alive-b": 404, "dead-c": 404})
    with pytest.raises(RuntimeError) as exc:
        asyncio.run(pool.complete("sys", "user"))
    msg = str(exc.value)
    assert "404" in msg and "GROQ_MODELS" in msg
    assert "rate-limited" not in msg, \
        "a stale config must not be reported as a rate limit"


# ── 429 behaviour must be unchanged ──────────────────────────────────────

def test_429_still_falls_back(pool, monkeypatch):
    _install(monkeypatch, {"dead-a": 429})
    _, used = asyncio.run(pool.complete("sys", "user"))
    assert used in ("alive-b", "dead-c")


def test_429_is_temporary_not_permanent(pool, monkeypatch):
    """A rate-limited model is blocked, never retired - capacity comes back."""
    _install(monkeypatch, {"dead-a": 429})
    asyncio.run(pool.complete("sys", "user"))
    assert pool.unavailable_models() == []
    assert "dead-a" in pool.available_models()


def test_other_status_codes_still_propagate(pool, monkeypatch):
    """500 is a real error; swallowing it would hide provider outages."""
    _install(monkeypatch, {"dead-a": 500, "alive-b": 500, "dead-c": 500})
    with pytest.raises(APIStatusError):
        asyncio.run(pool.complete("sys", "user"))


def test_healthy_pool_is_unaffected(pool, monkeypatch):
    _install(monkeypatch, {})
    used = {asyncio.run(pool.complete("sys", "user"))[1] for _ in range(3)}
    assert used <= {"dead-a", "alive-b", "dead-c"}
    assert pool.unavailable_models() == []
