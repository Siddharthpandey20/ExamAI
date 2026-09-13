# G0 — Two of three production LLM models are decommissioned

**Status:** verified · **Severity: this is a live outage, not a quality issue.**
**67% of production LLM calls fail right now**, and reasoning mode is
initialised with a model that no longer exists.

Found incidentally while setting up the grounding experiment. **No production
code was changed** — the fix is specified below and left for approval.

---

## What is wrong

`engine/config.py` defines a three-model fallback chain:

```python
GROQ_MODELS = [
    {"model": "llama-3.3-70b-versatile", ...},                    # 404
    {"model": "openai/gpt-oss-120b", ...},                        # alive
    {"model": "meta-llama/llama-4-scout-17b-16e-instruct", ...},  # 404
]
GROQ_MODEL = GROQ_MODELS[0]["model"]     # the dead one
```

Querying the Groq account's model list: **`llama-3.3-70b-versatile` and
`meta-llama/llama-4-scout-17b-16e-instruct` no longer exist.** Groq has
decommissioned both. Of the models the account can reach, only
`openai/gpt-oss-120b` is in the pool.

## Why the fallback chain does not save it

`engine/llm.py::complete()` handles exactly two failure modes:

```python
except RateLimitError:
    tracker.mark_blocked(60); continue
except APIStatusError as e:
    if e.status_code == 429:
        tracker.mark_blocked(60); continue
    raise                     # <-- a 404 lands here
```

A decommissioned model returns **404**, not 429, so it **re-raises instead of
falling back**. The pool round-robins across three trackers; two of the three
raise immediately.

### Measured, not inferred

Six consecutive `pool.complete()` calls:

```
call 1: OK via openai/gpt-oss-120b
call 2: FAILED NotFoundError 404 - meta-llama/llama-4-scout-17b-16e-instruct
call 3: FAILED NotFoundError 404 - llama-3.3-70b-versatile
call 4: OK via openai/gpt-oss-120b
call 5: FAILED NotFoundError 404 - meta-llama/llama-4-scout-17b-16e-instruct
call 6: FAILED NotFoundError 404 - llama-3.3-70b-versatile

2 succeeded / 4 failed  (67% failure rate)
```

## Reasoning mode is worse — it fails 100% of the time

`engine/reasoning_mode.py::_get_agent_model()` calls
`pool.get_best_model_name()`, which returns:

```
get_best_model_name() -> llama-3.3-70b-versatile
```

The agent is constructed around a model that does not exist, with no
round-robin to rescue it. Every reasoning-mode request fails.

---

## Impact

| surface | effect |
|---|---|
| `fast_search`, `fast_coverage`, study plan, revision | ~2 in 3 requests raise |
| **reasoning mode** | **fails every time** |
| Retry behaviour | none — 404 is not treated as retryable |
| User-visible | an error, not a degraded answer |

This also silently constrained this session: every LLM experiment had to pin
`openai/gpt-oss-120b` directly, so the grounding results describe that model
rather than the intended pool.

## Proposed production change — NOT applied

The minimal, lowest-risk fix is two independent changes:

**1. Remove the dead models from `GROQ_MODELS`.** Only `openai/gpt-oss-120b`
from the current list is reachable. The account can also reach
`openai/gpt-oss-20b`, `qwen/qwen3.6-27b`, `qwen/qwen3.8-27b` and
`groq/compound` — choosing replacements is a quality decision, not a mechanical
one, so it needs a judgement I should not make unilaterally.

**2. Make the fallback chain treat 404 as fallback-worthy**, in
`engine/llm.py::complete()`:

```python
except APIStatusError as e:
    if e.status_code in (404, 429):
        tracker.mark_blocked(...)   # 404 should block for much longer than 60s
        continue
    raise
```

Without (2) the same outage recurs the next time a provider retires a model,
and it fails loudly at request time rather than degrading. Fixing (2) alone
would restore service today, since it would route every request to the one
live model.

## Why this was not applied

Production behaviour is frozen for this session and the model list is
explicitly named as something not to change. But the standing instruction to
avoid unapproved changes is about *risk*, and leaving a 67% failure rate in
place is its own risk — so this is flagged at the top of the checkpoint rather
than buried.

**Recommended: apply both changes, (2) first.** It is a three-line change with
a clear test.

## How promotion would be validated

1. A unit test asserting that a 404 from one model causes fallback to the next
   rather than propagating — using a stub client, so no network.
2. A readiness check that each configured model id is present in the provider's
   model list, surfaced through the existing `routes/health.py` probe. That
   converts a silent production failure into a startup-visible one.
3. Regression: the full suite.

## Threats to validity

- One Groq account and one point in time; availability is provider-side and
  could change again, which is precisely the argument for check (2).
- The rate-limit behaviour observed separately (free tier 429s at 2 concurrent
  requests) is a different constraint and is not addressed by this fix.
