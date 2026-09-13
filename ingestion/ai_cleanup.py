"""
ai_cleanup.py — Use Ollama (Llama3) to clean up and format extracted text.

Takes raw/noisy extracted content and returns well-structured text
ready for markdown assembly.

STRICT RULES enforced via prompt:
  - ZERO fabrication: output only what the input contains
  - Fix OCR errors only when obvious
  - Preserve original structure
"""

import re
import requests

from ingestion.config import OLLAMA_BASE_URL, OLLAMA_MODEL


_PREAMBLE_PATTERNS = [
    re.compile(r"^Here\s+is\s+the\s+cleaned\s+text[:\s]*\n?", re.IGNORECASE),
    re.compile(r"^Cleaned\s+text[:\s]*\n?", re.IGNORECASE),
    re.compile(r"^Here\s+are\s+the\s+cleaned[:\s]*\n?", re.IGNORECASE),
    # Llama3 sometimes echoes the instruction block back before the content,
    # which inflated one measured page from 2017 to 2747 characters. Anchored
    # to the start and to the final rule line so it can only ever remove the
    # echoed rules, never page content.
    re.compile(r"^.{0,1500}?Output ONLY the cleaned text\.[^\n]*\n+",
               re.IGNORECASE | re.DOTALL),
]
# A postscript pattern must only ever remove the model's own sign-off.
# The previous r"\n\s*\(?\s*Note:.*$" with DOTALL matched the FIRST line
# beginning "Note:" and deleted everything from there to the end of the
# string.  "Note:" is ordinary lecture content, so on a page whose notes sit
# mid-slide this silently destroyed the rest of the page — one measured
# example lost 867 of 1316 characters, including an entire "Little oh
# notation" section.  The model had returned the content correctly; the
# damage was done here, after the response.
#
# Sign-offs are now recognised only when they are the FINAL line and refer to
# the model's own process.  No DOTALL, so nothing can span the document.
_AI_SELF_REFERENCE = (
    r"(?:\bI['’]?\s*(?:ve|have|has|did|am|was)?\s*"
    r"(?:followed|removed|kept|made|added|cleaned|not)\b"
    r"|\bmy\b|\bas\s+(?:requested|instructed|per)\b|\brules?\b|\binstructions?\b"
    r"|\bcleaned\s+text\b|\boriginal\s+text\b|\bno\s+changes?\b|\bplaceholder\b"
    r"|\bI\s)"
)

_POSTSCRIPT_PATTERNS = [
    # "(Note: I have not added any content.)" as the closing line.
    re.compile(
        rf"\n\s*\(?\s*Note:(?=[^\n]*{_AI_SELF_REFERENCE})[^\n]*\)?\s*$",
        re.IGNORECASE,
    ),
    # "---\nI've followed all the rules..." trailing block.
    re.compile(r"\n\s*-{3,}\s*\n\s*\(?\s*I'?v?e?\s+followed.*$",
               re.IGNORECASE | re.DOTALL),
    # A trailing "[empty page]" marker echoed after real content (rule 8 of
    # the prompt leaking into the output).
    re.compile(r"\n\s*-{0,3}\s*\[empty page\]\s*$", re.IGNORECASE),
]

# Stripping removes a sign-off, never a chunk of the page.  A sign-off is a
# roughly fixed size regardless of page length, so the guard is primarily an
# absolute cap — a ratio alone would wrongly block a legitimate 99-character
# sign-off on a short page while still allowing a large removal on a long one.
# The ratio is kept as a second condition for pathologically short outputs.
_MAX_STRIP_CHARS = 400
_MIN_STRIP_RETENTION = 0.40
# The ratio is only meaningful once the page is long enough: on a very short
# page a fixed-size sign-off is legitimately a large share of the text.
_RATIO_GUARD_MIN_CHARS = 300

# The model may legitimately drop OCR garbage, but it should never return a
# small fraction of the source.  Below this share, fall back to the original
# native text rather than accept a truncated page.
_MIN_SOURCE_RETENTION = 0.50


def _strip_ai_preamble(text: str) -> str:
    """Remove AI-generated preamble and sign-off, failing safe.

    Never returns substantially less than it was given: if the patterns
    would remove a large share of the output, the output is kept as-is.
    """
    for pat in _PREAMBLE_PATTERNS:
        text = pat.sub("", text, count=1)

    # Guard the postscripts against the baseline AFTER preamble removal: an
    # echoed instruction block is legitimately large, while a sign-off is not.
    original = text.strip()

    for pat in _POSTSCRIPT_PATTERNS:
        text = pat.sub("", text)
    text = text.strip()

    removed = len(original) - len(text)
    too_much = removed > _MAX_STRIP_CHARS
    if len(original) >= _RATIO_GUARD_MIN_CHARS:
        too_much = too_much or len(text) < len(original) * _MIN_STRIP_RETENTION

    if original and too_much:
        print(f"[AI] Post-processing would have removed "
              f"{removed} of {len(original)} chars - too much for a sign-off, "
              f"keeping the model output instead.")
        return original
    return text

CLEANUP_PROMPT = """You are a strict transcription cleaner. You receive raw text extracted from a lecture slide.

ABSOLUTE RULES — VIOLATING ANY RULE IS FAILURE:
1. Output ONLY text that exists in the input. Do NOT invent, expand, or add ANY content.
2. Do NOT add explanations, notes, commentary, placeholders like "[Insert ...]", or examples.
3. Do NOT add "Note:", "Formula:", or any section that is not in the original.
4. Fix obvious OCR typos (e.g., "vl" → "v1", "lNT" → "INT") but NEVER guess meaning.
5. Remove garbage tokens: random hex strings, repeated symbols (*****, ====), stray characters.
6. Keep bullet points, headings, and structure from the original.
7. If the input is mostly a table, format it as a markdown table.
8. If the input is empty or only garbage, output exactly: [empty page]
9. Output ONLY the cleaned text. No preamble, no sign-off.

Raw text from slide:
---
{raw_text}
---

Cleaned text:"""


def cleanup_text(raw_text: str) -> str:
    """
    Send raw text to Ollama Llama3 for cleanup.
    Returns cleaned text. Falls back to raw text on failure.
    """
    if not raw_text.strip():
        return ""

    prompt = CLEANUP_PROMPT.format(raw_text=raw_text)

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 2048,
                },
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        cleaned = data.get("response", "").strip()

        # Reject if AI returned nothing useful
        if not cleaned or cleaned == "[empty page]":
            return raw_text

        # Detect a generation that was cut off rather than finished.  Ollama
        # reports "length" when num_predict was hit mid-answer; accepting that
        # output would silently store a half page.
        if data.get("done_reason") == "length":
            print(f"[AI] Generation hit the token limit "
                  f"({data.get('eval_count')} tokens) - keeping raw text.")
            return raw_text

        # Strip common AI preamble/postscript that Llama3 adds
        cleaned = _strip_ai_preamble(cleaned)

        # Fail safe: cleaning removes noise, it does not summarise.  If the
        # result is a small fraction of the source, something went wrong and
        # the original text is the safer thing to keep.
        if len(cleaned) < len(raw_text.strip()) * _MIN_SOURCE_RETENTION:
            print(f"[AI] Cleaned output is {len(cleaned)} chars against "
                  f"{len(raw_text.strip())} of source - keeping raw text.")
            return raw_text

        return cleaned

    except requests.exceptions.ConnectionError:
        print("[AI] Ollama not reachable — returning raw text.")
        return raw_text
    except Exception as e:
        print(f"[AI] Cleanup failed: {e} — returning raw text.")
        return raw_text
