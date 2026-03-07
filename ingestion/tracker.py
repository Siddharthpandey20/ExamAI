"""
tracker.py — Tracks which files have already been ingested.

Uses a simple JSON file (processed.json) storing filename → timestamp.
The anchor checks this before processing to avoid duplicate work.
"""

import json
import os
from datetime import datetime, timezone

from ingestion.config import TRACKER_FILE


def _load() -> dict:
    if not os.path.exists(TRACKER_FILE):
        return {}
    with open(TRACKER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict):
    os.makedirs(os.path.dirname(TRACKER_FILE), exist_ok=True)
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def is_processed(filepath: str) -> bool:
    """Return True if this file has already been ingested."""
    key = os.path.basename(filepath)
    return key in _load()


def mark_processed(filepath: str):
    """Record that this file has been successfully ingested."""
    data = _load()
    data[os.path.basename(filepath)] = datetime.now(timezone.utc).isoformat()
    _save(data)


def get_all_processed() -> dict:
    """Return the full tracker dictionary."""
    return _load()
