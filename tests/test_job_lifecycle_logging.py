"""
Tests for job lifecycle logging.

The three study-chain tasks previously logged with no shared identifier, so a
single run could not be followed across ingest, structure and index, and
nothing recorded how long each phase took — which is what actually
identifies the slow stage of a 20-minute ingestion.

Logging must also never be able to fail a task, and must not leak secrets.
"""

import logging

import pytest

from jobs.models import PhaseStatus
from jobs.tasks import _log_phase_event


def _emit(caplog, **kwargs):
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="jobs.tasks"):
        _log_phase_event(**kwargs)
    return caplog.text


BASE = dict(job_id=42, phase="ingest", status=PhaseStatus.RUNNING.value,
            started_at=None, completed_at=None, filename="lecture.pdf")


# ── Correlation ──────────────────────────────────────────────────────────

def test_every_line_carries_the_job_id(caplog):
    text = _emit(caplog, **BASE)
    assert "job=42" in text


def test_line_carries_phase_and_status(caplog):
    text = _emit(caplog, **BASE)
    assert "phase=ingest" in text
    assert f"status={PhaseStatus.RUNNING.value}" in text


def test_line_carries_the_filename(caplog):
    assert "lecture.pdf" in _emit(caplog, **BASE)


def test_lines_are_greppable_by_a_single_tag(caplog):
    assert "[lifecycle]" in _emit(caplog, **BASE)


# ── Duration ─────────────────────────────────────────────────────────────

def test_duration_is_reported_on_a_terminal_transition(caplog):
    from datetime import datetime, timedelta, timezone
    start = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    text = _emit(caplog, **{**BASE,
                            "status": PhaseStatus.COMPLETED.value,
                            "started_at": start,
                            "completed_at": start + timedelta(seconds=93.4)})
    assert "duration_sec=93.4" in text


def test_no_duration_before_the_phase_finishes(caplog):
    text = _emit(caplog, **BASE)
    assert "duration_sec" not in text


# ── Severity ─────────────────────────────────────────────────────────────

def test_failures_are_logged_at_error_level(caplog):
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="jobs.tasks"):
        _log_phase_event(**{**BASE, "status": PhaseStatus.FAILED.value})
    assert any(r.levelno == logging.ERROR for r in caplog.records)


@pytest.mark.parametrize("status", [PhaseStatus.RUNNING.value,
                                    PhaseStatus.COMPLETED.value,
                                    PhaseStatus.SKIPPED.value])
def test_non_failures_are_logged_at_info_level(caplog, status):
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="jobs.tasks"):
        _log_phase_event(**{**BASE, "status": status})
    assert caplog.records
    assert all(r.levelno == logging.INFO for r in caplog.records)


# ── Robustness ───────────────────────────────────────────────────────────

def test_logging_never_raises(caplog):
    """A logging bug must not be able to fail a pipeline task."""
    class Exploding:
        def __repr__(self):
            raise RuntimeError("boom")
        def __format__(self, spec):
            raise RuntimeError("boom")

    with caplog.at_level(logging.INFO, logger="jobs.tasks"):
        _log_phase_event(job_id=Exploding(), phase="ingest", status="running",
                         started_at=None, completed_at=None, filename=None)


def test_missing_filename_is_tolerated(caplog):
    text = _emit(caplog, **{**BASE, "filename": None})
    assert "job=42" in text
    assert "file=" not in text


def test_mismatched_timestamps_do_not_raise(caplog):
    from datetime import datetime, timezone
    start = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    _emit(caplog, **{**BASE, "started_at": start, "completed_at": None})
    _emit(caplog, **{**BASE, "started_at": None, "completed_at": start})


def test_no_secrets_in_the_line(caplog):
    """Only ids, phases, status, filename and duration are emitted."""
    text = _emit(caplog, **{**BASE, "filename": "notes.pdf"})
    for leak in ("sk-", "gsk_", "AIza", "password", "redis://"):
        assert leak not in text
