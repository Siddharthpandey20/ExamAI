"""
Tests for the Celery retry classification.

Retries are deliberately narrow. A blanket autoretry_for=(Exception,) would
re-run deterministic failures — a corrupt PDF, an unsupported file, an
exhausted daily quota — burning provider quota and delaying the error the
user needs to see.

The subtle part is _will_retry: the tasks call _fail_job() and re-raise, so
marking a job failed on an attempt that is about to be retried would leave a
successful retry showing as FAILED, since only index_task's _complete_job
ever clears that state.

No broker, no worker, no network.
"""

import pytest

import jobs.tasks as tasks
from jobs.tasks import TRANSIENT_ERRORS, RETRY_POLICY, _will_retry

TASK_NAMES = ["jobs.ingest", "jobs.structure", "jobs.index",
              "jobs.process_pyq", "jobs.remap_pyq"]


# ── Classification ───────────────────────────────────────────────────────

def test_transient_tuple_is_populated():
    assert TRANSIENT_ERRORS, "retry classification failed to build"


@pytest.mark.parametrize("exc_path", [
    "openai.APIConnectionError",
    "openai.APITimeoutError",        # subclass of APIConnectionError
    "openai.InternalServerError",
    "openai.RateLimitError",
    "requests.exceptions.ConnectionError",
    "requests.exceptions.Timeout",
    "redis.exceptions.ConnectionError",
    "redis.exceptions.TimeoutError",
    "sqlalchemy.exc.OperationalError",
])
def test_transient_errors_are_classified_retryable(exc_path):
    import importlib
    mod_name, _, cls_name = exc_path.rpartition(".")
    cls = getattr(importlib.import_module(mod_name), cls_name)
    assert issubclass(cls, TRANSIENT_ERRORS), f"{exc_path} should be retryable"


@pytest.mark.parametrize("exc_path", [
    "openai.AuthenticationError",
    "openai.BadRequestError",
    "openai.NotFoundError",
    "openai.PermissionDeniedError",
    "openai.UnprocessableEntityError",
])
def test_permanent_provider_errors_are_not_retried(exc_path):
    import importlib
    mod_name, _, cls_name = exc_path.rpartition(".")
    cls = getattr(importlib.import_module(mod_name), cls_name)
    assert not issubclass(cls, TRANSIENT_ERRORS), f"{exc_path} must NOT be retried"


@pytest.mark.parametrize("cls", [RuntimeError, ValueError, FileNotFoundError,
                                 KeyError, TypeError, ZeroDivisionError])
def test_deterministic_errors_are_not_retried(cls):
    assert not issubclass(cls, TRANSIENT_ERRORS)


def test_gemini_quota_exhaustion_is_not_retried():
    """Daily quota: minutes of backoff cannot help, and the message already
    tells the user to retry tomorrow."""
    from structuring.slide_agent import GeminiQuotaExhausted
    assert not issubclass(GeminiQuotaExhausted, TRANSIENT_ERRORS)


def test_no_blanket_exception_retry():
    assert Exception not in TRANSIENT_ERRORS
    assert BaseException not in TRANSIENT_ERRORS
    assert not issubclass(Exception, TRANSIENT_ERRORS)


# ── Policy shape ─────────────────────────────────────────────────────────

def test_policy_is_bounded_and_backed_off():
    assert RETRY_POLICY["max_retries"] == 3
    assert RETRY_POLICY["retry_backoff"] is True
    assert RETRY_POLICY["retry_jitter"] is True
    assert RETRY_POLICY["retry_backoff_max"] == 300


@pytest.mark.parametrize("name", TASK_NAMES)
def test_every_task_has_the_policy(name):
    task = tasks.app.tasks[name]
    assert task.max_retries == 3
    assert tuple(task.autoretry_for) == tuple(TRANSIENT_ERRORS)


@pytest.mark.parametrize("name", TASK_NAMES)
def test_crash_safety_settings_are_intact(name):
    """acks_late and reject_on_worker_lost handle worker death; retries are
    a separate concern and must not have disturbed them."""
    assert tasks.app.conf.task_acks_late is True
    assert tasks.app.conf.task_reject_on_worker_lost is True


# ── _will_retry: the _fail_job deferral ──────────────────────────────────

class _FakeRequest:
    def __init__(self, retries):
        self.retries = retries


class _FakeTask:
    def __init__(self, retries=0, max_retries=3):
        self.request = _FakeRequest(retries)
        self.max_retries = max_retries


def test_transient_error_with_retries_left_defers_failure():
    import openai
    exc = openai.APIConnectionError(request=None)
    assert _will_retry(_FakeTask(retries=0), exc) is True
    assert _will_retry(_FakeTask(retries=2), exc) is True


def test_transient_error_with_retries_exhausted_marks_failure():
    """On the final attempt the job must be recorded as failed."""
    import openai
    exc = openai.APIConnectionError(request=None)
    assert _will_retry(_FakeTask(retries=3), exc) is False
    assert _will_retry(_FakeTask(retries=9), exc) is False


def test_permanent_error_marks_failure_immediately():
    assert _will_retry(_FakeTask(retries=0), RuntimeError("no output")) is False
    assert _will_retry(_FakeTask(retries=0), ValueError("bad")) is False


def test_gemini_quota_marks_failure_immediately():
    from structuring.slide_agent import GeminiQuotaExhausted
    assert _will_retry(_FakeTask(retries=0), GeminiQuotaExhausted("quota")) is False


def test_will_retry_is_safe_outside_a_request_context():
    """Called from a plain function call rather than a worker."""
    import openai

    class _Broken:
        max_retries = 3

        @property
        def request(self):
            raise RuntimeError("no request context")

    assert _will_retry(_Broken(), openai.APIConnectionError(request=None)) is False


def test_will_retry_handles_none_max_retries():
    import openai
    t = _FakeTask(retries=0)
    t.max_retries = None
    assert _will_retry(t, openai.APIConnectionError(request=None)) is False


# ── Idempotency is the precondition for retrying at all ──────────────────

def test_retried_tasks_have_duplicate_guards():
    """Every retried task must refuse to duplicate work on re-execution.

    This is asserted structurally: if a guard is ever removed, retrying that
    task becomes unsafe and this test should fail loudly.
    """
    import inspect
    src = inspect.getsource(tasks)
    assert "is_processed(filepath)" in src, "ingest lost its tracker guard"
    assert "is_structured(filename)" in src, "structure lost its tracker guard"
    assert "get_unembedded_slides" in src, "index lost its embedded-state guard"
    assert "is_pyq_already_ingested" in src, "pyq lost its duplicate guard"
    assert "existing_pyq_id" in src, "remap lost its question-reuse guard"
