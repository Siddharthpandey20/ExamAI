"""
Tests for the readiness probe.

Liveness and readiness answer different questions. /api/health returns a
static ok, which is right for "the process is up" but says nothing about
whether SQLite, Redis or ChromaDB are reachable — so a container could pass
its health check while every request fails.

Dependencies are stubbed, so these run with nothing installed or running.
"""

import pytest
from fastapi.testclient import TestClient

import main
import routes.health as health


@pytest.fixture()
def client():
    with TestClient(main.app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(autouse=True)
def all_dependencies_healthy(monkeypatch):
    monkeypatch.setattr(health, "_check_database", lambda: "reachable")
    monkeypatch.setattr(health, "_check_redis", lambda: "reachable")
    monkeypatch.setattr(health, "_check_chroma", lambda: "690 vectors")


# ── Liveness stays exactly as it was ─────────────────────────────────────

def test_liveness_is_unchanged(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ── Readiness, healthy ───────────────────────────────────────────────────

def test_ready_when_all_dependencies_are_up(client):
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert set(body["checks"]) == {"database", "redis", "chroma"}
    assert all(c["ok"] for c in body["checks"].values())


def test_every_check_reports_status_detail_and_timing(client):
    body = client.get("/api/health/ready").json()
    for name, check in body["checks"].items():
        assert set(check) == {"ok", "detail", "ms"}, name
        assert isinstance(check["ms"], (int, float))
        assert check["ms"] >= 0


# ── Readiness, degraded ──────────────────────────────────────────────────

@pytest.mark.parametrize("failing", ["_check_database", "_check_redis", "_check_chroma"])
def test_a_single_failed_dependency_makes_the_service_not_ready(client, monkeypatch, failing):
    def boom():
        raise ConnectionError("dependency down")

    monkeypatch.setattr(health, failing, boom)
    r = client.get("/api/health/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not ready"
    name = failing.replace("_check_", "")
    assert body["checks"][name]["ok"] is False
    # The other two must still be reported, not short-circuited.
    assert len(body["checks"]) == 3


def test_all_dependencies_down_is_still_a_structured_response(client, monkeypatch):
    def boom():
        raise ConnectionError("down")

    for probe in ("_check_database", "_check_redis", "_check_chroma"):
        monkeypatch.setattr(health, probe, boom)
    r = client.get("/api/health/ready")
    assert r.status_code == 503
    assert all(c["ok"] is False for c in r.json()["checks"].values())


def test_a_probe_that_raises_does_not_crash_the_endpoint(client, monkeypatch):
    monkeypatch.setattr(health, "_check_redis",
                        lambda: (_ for _ in ()).throw(RuntimeError("unexpected")))
    r = client.get("/api/health/ready")
    assert r.status_code == 503


# ── No secret leakage ────────────────────────────────────────────────────

def test_failure_detail_does_not_leak_connection_details(client, monkeypatch):
    """A probe failure must not echo the URL, which can carry a password."""
    secret = "redis://:sup3rsecret@10.0.0.5:6379/0"

    def boom():
        raise ConnectionError(f"could not connect to {secret}")

    monkeypatch.setattr(health, "_check_redis", boom)
    body = client.get("/api/health/ready").text
    assert "sup3rsecret" not in body
    assert "10.0.0.5" not in body
    assert "ConnectionError" in body      # the class is useful and safe


# ── The embedder is reported, not gated ──────────────────────────────────

def test_embedder_is_reported_but_does_not_gate_readiness(client, monkeypatch):
    """It loads lazily by design; forcing it would make the probe take a
    minute and block startup."""
    monkeypatch.setattr(health, "_embedder_state", lambda: "not loaded (lazy)")
    r = client.get("/api/health/ready")
    assert r.status_code == 200
    assert r.json()["embedder"] == "not loaded (lazy)"


def test_slow_probe_is_treated_as_failing(client, monkeypatch):
    """A readiness endpoint that blocks is worse than one reporting failure."""
    import time

    def slow():
        time.sleep(0.01)
        return "reachable"

    monkeypatch.setattr(health, "_check_redis", slow)
    monkeypatch.setattr(health, "PROBE_TIMEOUT_SECONDS", 0)
    r = client.get("/api/health/ready")
    assert r.status_code == 503
    assert "slow" in r.json()["checks"]["redis"]["detail"]
