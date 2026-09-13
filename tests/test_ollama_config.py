"""
Tests for OLLAMA_BASE_URL configuration.

The URL was hardcoded to 127.0.0.1 in all four config modules even though the
README documents it as an environment variable. Any deployment where Ollama
is not in the same network namespace — a container, another host — would
fail, and there was no way to point at it.

One value must work for every module despite two different API shapes:
ingestion calls the native /api/generate endpoint, while structuring, pyq and
engine use the OpenAI-compatible /v1 endpoint. The value is accepted with or
without /v1 and normalised per module.

Config modules are re-imported under a patched environment, so nothing here
depends on how the test process itself was started.
"""

import importlib
import os

import pytest

V1_MODULES = ["structuring.config", "pyq.config", "engine.config"]
NATIVE_MODULE = "ingestion.config"


def _reload(module_name, env_value):
    """Re-import a config module with OLLAMA_BASE_URL set (or unset)."""
    old = os.environ.get("OLLAMA_BASE_URL")
    try:
        if env_value is None:
            os.environ.pop("OLLAMA_BASE_URL", None)
        else:
            os.environ["OLLAMA_BASE_URL"] = env_value
        mod = importlib.import_module(module_name)
        return importlib.reload(mod).OLLAMA_BASE_URL
    finally:
        if old is None:
            os.environ.pop("OLLAMA_BASE_URL", None)
        else:
            os.environ["OLLAMA_BASE_URL"] = old
        importlib.reload(importlib.import_module(module_name))


# ── Defaults must not have changed ───────────────────────────────────────

@pytest.mark.parametrize("module", V1_MODULES)
def test_default_is_unchanged_for_v1_modules(module):
    assert _reload(module, None) == "http://127.0.0.1:11434/v1"


def test_default_is_unchanged_for_the_native_module():
    assert _reload(NATIVE_MODULE, None) == "http://127.0.0.1:11434"


# ── A containerised host works for every module ──────────────────────────

@pytest.mark.parametrize("module", V1_MODULES)
def test_v1_modules_accept_a_bare_host(module):
    assert _reload(module, "http://ollama:11434") == "http://ollama:11434/v1"


@pytest.mark.parametrize("module", V1_MODULES)
def test_v1_modules_accept_a_url_that_already_has_v1(module):
    """One env value must serve both API shapes without double-suffixing."""
    assert _reload(module, "http://ollama:11434/v1") == "http://ollama:11434/v1"


def test_native_module_strips_a_v1_suffix():
    """ingestion calls /api/generate, so /v1 must not survive."""
    assert _reload(NATIVE_MODULE, "http://ollama:11434/v1") == "http://ollama:11434"


def test_native_module_accepts_a_bare_host():
    assert _reload(NATIVE_MODULE, "http://ollama:11434") == "http://ollama:11434"


# ── Normalisation edge cases ─────────────────────────────────────────────

@pytest.mark.parametrize("module", V1_MODULES)
def test_trailing_slash_does_not_produce_a_double_slash(module):
    assert _reload(module, "http://ollama:11434/") == "http://ollama:11434/v1"


def test_trailing_slash_on_v1_is_normalised_for_native():
    assert _reload(NATIVE_MODULE, "http://ollama:11434/v1/") == "http://ollama:11434"


@pytest.mark.parametrize("module", V1_MODULES + [NATIVE_MODULE])
def test_no_module_ever_emits_a_doubled_v1(module):
    for value in ("http://h:1/v1", "http://h:1/v1/", "http://h:1", "http://h:1/"):
        assert "/v1/v1" not in _reload(module, value)


def test_a_remote_host_with_a_path_prefix_is_preserved():
    """A reverse proxy may expose Ollama under a sub-path."""
    assert _reload("engine.config", "https://gw.example/ollama") == "https://gw.example/ollama/v1"
    assert _reload(NATIVE_MODULE, "https://gw.example/ollama") == "https://gw.example/ollama"


# ── The endpoints the code actually builds ───────────────────────────────

def test_native_endpoint_is_well_formed():
    base = _reload(NATIVE_MODULE, "http://ollama:11434/v1")
    assert f"{base}/api/generate" == "http://ollama:11434/api/generate"
