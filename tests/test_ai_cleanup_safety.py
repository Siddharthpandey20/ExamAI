"""
Regression tests for AI cleanup post-processing safety.

The cleanup step must never silently destroy source content. Three real
failure modes were measured against the corpus and are locked in here:

  1. `\\n\\s*\\(?\\s*Note:.*$` with DOTALL matched the FIRST line beginning
     "Note:" and deleted everything to the end of the string. "Note:" is
     ordinary lecture text, so a page whose notes sit mid-slide lost
     everything after them — one page lost 867 of 1316 characters including
     an entire "Little oh notation" section. The model had returned the
     content correctly; post-processing destroyed it.

  2. Llama3 sometimes echoes the instruction block back before the content,
     which inflated one page from 2017 to 2747 characters.

  3. Llama3 sometimes appends a bare "[empty page]" marker after real
     content, leaking rule 8 of the prompt into the output.

Ollama is mocked, so these run anywhere with no network or model.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ingestion.ai_cleanup as ac  # noqa: E402
from ingestion.ai_cleanup import _strip_ai_preamble, cleanup_text  # noqa: E402


# ── 1. The destructive-truncation regression ─────────────────────────────

LECTURE_PAGE = """Theta Notation:

It is denoted by O, a method of representing running time between bounds.

Ex1: f(n) = 3n + 2 => f(n) = Theta(n)

Note:  f(n) = a_m n^m + ... + a_1 n + a_0, then f(n) = Theta(n^m)

Note: Theta notation is more precise than both the O and Omega notations.

Little oh notation: The little oh notation is denoted by o and is defined
as f(n) = o(g(n)) iff the limit as n approaches infinity is 0.

Ex: place the following functions according to their order of growth."""


def test_midpage_note_lines_are_never_stripped():
    """The exact regression: content after a 'Note:' line must survive."""
    out = _strip_ai_preamble(LECTURE_PAGE)
    assert "Little oh notation" in out, "content after 'Note:' was destroyed"
    assert "order of growth" in out
    assert out.strip() == LECTURE_PAGE.strip()


def test_retention_on_a_note_heavy_page_is_total():
    out = _strip_ai_preamble(LECTURE_PAGE)
    assert len(out) >= len(LECTURE_PAGE.strip()) * 0.99


@pytest.mark.parametrize("note", [
    "Note: the diagram above shows the memory layout.",
    "Note: this applies only to non-negative functions.",
    "Note:  f(n) = a_m n^m, then f(n) = Theta(n^m)",
])
def test_ordinary_trailing_notes_are_kept(note):
    """A trailing 'Note:' that is lecture content must not be removed."""
    text = f"Some slide content.\n\n{note}"
    assert _strip_ai_preamble(text).endswith(note)


# ── 2. Genuine AI sign-offs are still removed ────────────────────────────

@pytest.mark.parametrize("signoff", [
    "Note: No changes were made to the original text, and all formatting was preserved.",
    "Note: I have followed all the rules and added nothing.",
    "Note: I removed the garbage tokens as requested.",
    "(Note: my output preserves the original structure.)",
])
def test_ai_signoffs_are_stripped(signoff):
    body = "Register r13 is the stack pointer.\n\nRegister r15 is the program counter."
    out = _strip_ai_preamble(f"{body}\n\n{signoff}")
    assert out.strip() == body.strip()


def test_trailing_empty_page_marker_is_stripped():
    body = "Real slide content about paging."
    assert _strip_ai_preamble(f"{body}\n\n---\n\n[empty page]").strip() == body


def test_followed_the_rules_block_is_stripped():
    body = "Slide content."
    out = _strip_ai_preamble(f"{body}\n\n---\n\nI've followed all of the rules above.")
    assert out.strip() == body


# ── 3. Echoed instruction block is removed ───────────────────────────────

def test_echoed_instruction_block_is_stripped():
    echoed = (
        "You are a strict transcription cleaner.\n"
        "7. If the input is mostly a table, format it as a markdown table.\n"
        "8. If the input is empty or only garbage, output exactly: [empty page]\n"
        "9. Output ONLY the cleaned text. No preamble, no sign-off.\n\n"
    )
    body = "The goal of analysis of algorithms is to measure time complexity."
    out = _strip_ai_preamble(echoed + body)
    assert out.strip() == body
    assert "Output ONLY the cleaned text" not in out


def test_preamble_variants_still_work():
    for pre in ("Here is the cleaned text:\n", "Cleaned text:\n", "Here are the cleaned:\n"):
        assert _strip_ai_preamble(pre + "Body text.").strip() == "Body text."


# ── 4. The guard: post-processing may never eat the page ─────────────────

def test_guard_keeps_output_when_stripping_would_remove_too_much(monkeypatch):
    """A pattern that over-reaches must be ignored, not obeyed."""
    import re
    monkeypatch.setattr(ac, "_POSTSCRIPT_PATTERNS",
                        [re.compile(r"\n.*$", re.DOTALL)])
    text = "Line one of the page.\n" + ("content line\n" * 60)
    out = _strip_ai_preamble(text)
    assert out.strip() == text.strip(), "guard did not block an over-reaching pattern"


def test_guard_allows_a_normal_signoff_on_a_short_page():
    """A ~99 char sign-off on a ~550 char page is a large FRACTION but fine."""
    body = "x" * 450
    signoff = "Note: No changes were made to the original text, formatting preserved."
    out = _strip_ai_preamble(f"{body}\n\n{signoff}")
    assert out.strip() == body


# ── 5. cleanup_text fail-safes (Ollama mocked) ───────────────────────────

class _Resp:
    def __init__(self, payload):
        self._p = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self._p


def _mock_ollama(monkeypatch, payload):
    monkeypatch.setattr(ac.requests, "post", lambda *a, **k: _Resp(payload))


def test_truncated_generation_falls_back_to_raw(monkeypatch):
    """done_reason == 'length' means the answer was cut off mid-page."""
    src = "Full page of lecture content. " * 20
    _mock_ollama(monkeypatch, {"response": "Full page of lec",
                               "done_reason": "length", "eval_count": 2048})
    assert cleanup_text(src) == src


def test_suspiciously_short_output_falls_back_to_raw(monkeypatch):
    src = "Full page of lecture content. " * 20
    _mock_ollama(monkeypatch, {"response": "tiny", "done_reason": "stop"})
    assert cleanup_text(src) == src


def test_normal_output_is_returned(monkeypatch):
    src = "Full page of lecture content. " * 20
    cleaned = "Full page of lecture content. " * 19
    _mock_ollama(monkeypatch, {"response": cleaned, "done_reason": "stop"})
    assert cleanup_text(src).strip() == cleaned.strip()


def test_empty_page_response_falls_back_to_raw(monkeypatch):
    src = "Some content."
    _mock_ollama(monkeypatch, {"response": "[empty page]", "done_reason": "stop"})
    assert cleanup_text(src) == src


def test_connection_error_still_falls_back_to_raw(monkeypatch):
    src = "Some content that must survive an outage."

    def boom(*a, **k):
        raise ac.requests.exceptions.ConnectionError("no ollama")

    monkeypatch.setattr(ac.requests, "post", boom)
    assert cleanup_text(src) == src


def test_blank_input_short_circuits():
    assert cleanup_text("   ") == ""
