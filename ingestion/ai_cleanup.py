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
]
_POSTSCRIPT_PATTERNS = [
    re.compile(r"\n\s*\(?\s*Note:.*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"\n\s*---\s*\n\s*\(?\s*I'?v?e?\s+followed.*$", re.IGNORECASE | re.DOTALL),
]


def _strip_ai_preamble(text: str) -> str:
    """Remove common AI-generated preamble and postscript."""
    for pat in _PREAMBLE_PATTERNS:
        text = pat.sub("", text, count=1)
    for pat in _POSTSCRIPT_PATTERNS:
        text = pat.sub("", text)
    return text.strip()

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

        # Strip common AI preamble/postscript that Llama3 adds
        cleaned = _strip_ai_preamble(cleaned)

        return cleaned

    except requests.exceptions.ConnectionError:
        print("[AI] Ollama not reachable — returning raw text.")
        return raw_text
    except Exception as e:
        print(f"[AI] Cleanup failed: {e} — returning raw text.")
        return raw_text
