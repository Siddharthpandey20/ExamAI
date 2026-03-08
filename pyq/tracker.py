"""
tracker.py — Track which PYQ files have already been processed.

Thread-safe JSON tracker. SQLite is the authoritative source of truth
for duplicate prevention; this tracker is a fast pre-filter.
"""

import json
import os
import logging
import threading

from pyq.config import TRACKER_FILE

log = logging.getLogger(__name__)

_lock = threading.Lock()


def _load_tracker() -> dict:
    """Load the tracker JSON file."""
    if not os.path.exists(TRACKER_FILE):
        return {}
    with open(TRACKER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_tracker(data: dict):
    """Save the tracker JSON file."""
    os.makedirs(os.path.dirname(TRACKER_FILE), exist_ok=True)
    with open(TRACKER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def is_processed(filepath: str) -> bool:
    """Check if a PYQ file has already been processed."""
    with _lock:
        data = _load_tracker()
        key = os.path.abspath(filepath)
        return key in data


def mark_processed(filepath: str, num_questions: int, num_matches: int):
    """Mark a PYQ file as processed with stats."""
    with _lock:
        data = _load_tracker()
        key = os.path.abspath(filepath)
        data[key] = {
            "questions_extracted": num_questions,
            "total_matches": num_matches,
        }
        _save_tracker(data)
    log.info(f"[Tracker] Marked '{os.path.basename(filepath)}' as processed")
