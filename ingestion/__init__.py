"""
Ingestion Module — ExamPrep AI

Anchor file for the central system.
Scans the uploads/ folder, identifies unprocessed files, and runs the
ingestion pipeline on each. Produces per-file markdown in knowledge/.

Usage:
    # From central system:
    from ingestion import run_ingestion
    results = run_ingestion()

    # Standalone:
    python -m ingestion
"""

import os
import glob

from ingestion.config import UPLOAD_DIR, SUPPORTED_EXTENSIONS, KNOWLEDGE_DIR
from ingestion.tracker import is_processed, mark_processed
from ingestion.pipeline import run_pipeline


def _find_pending_files() -> list[str]:
    """Return list of files in uploads/ that haven't been processed yet."""
    all_files = []
    for ext in SUPPORTED_EXTENSIONS:
        pattern = os.path.join(UPLOAD_DIR, f"*{ext}")
        all_files.extend(glob.glob(pattern))

    pending = [f for f in sorted(all_files) if not is_processed(f)]
    return pending


def run_ingestion(source: str | None = None) -> list[str]:
    """
    Main entry point for the central system.

    Parameters
    ----------
    source : str or None
        - Path to a single file  → ingest just that file
        - None                   → ingest all pending files in uploads/

    Returns
    -------
    list[str]
        Paths to generated markdown files in knowledge/.
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

    # Determine files to process
    if source and os.path.isfile(source):
        files = [os.path.abspath(source)]
    else:
        files = _find_pending_files()

    if not files:
        print("[INFO] No new files to ingest.")
        return []

    print(f"[INFO] {len(files)} file(s) pending ingestion.\n")
    results = []

    for filepath in files:
        fname = os.path.basename(filepath)
        print(f"{'='*60}")
        print(f"[START] {fname}")
        print(f"{'='*60}")

        md_path = run_pipeline(filepath)

        if md_path:
            mark_processed(filepath)
            results.append(md_path)
            print(f"[OK] {fname} -> {md_path}\n")
        else:
            print(f"[FAIL] {fname} — skipping.\n")

    print(f"[SUMMARY] {len(results)}/{len(files)} file(s) ingested successfully.")
    return results


# Allow `python -m ingestion` to run directly
if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else None
    run_ingestion(target)

