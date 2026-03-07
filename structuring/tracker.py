"""
tracker.py — Tracks which knowledge markdown files have been structured.

Uses structured.json to avoid re-processing files that already have
structured output.
"""

import json
import os
from datetime import datetime, timezone

from structuring.config import TRACKER_FILE


def _load() -> dict:
    if not os.path.exists(TRACKER_FILE):
        return {}
    with open(TRACKER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    os.makedirs(os.path.dirname(TRACKER_FILE), exist_ok=True)
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def is_structured(filename: str) -> bool:
    """Return True if this knowledge file has already been structured."""
    return filename in _load()


def mark_structured(filename: str, output_path: str):
    """Record that a file has been successfully structured."""
    data = _load()
    data[filename] = {
        "structured_at": datetime.now(timezone.utc).isoformat(),
        "output": output_path,
    }
    _save(data)


def get_all_structured() -> dict:
    """Return the full tracker dictionary."""
    return _load()
