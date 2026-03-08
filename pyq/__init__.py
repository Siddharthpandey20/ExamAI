"""
PYQ Module — ExamPrep AI

Anchor file for the central system.
Scans pyq_uploads/ for PYQ documents, extracts questions via Llama 3,
runs hybrid search (dense + sparse + RRF) to map questions to slides,
and updates scoring in both SQLite and ChromaDB.

Usage:
    # From central system:
    from pyq import run_pyq
    results = run_pyq()

    # Standalone:
    python -m pyq
    python -m pyq path/to/paper.pdf
    python -m pyq --force
"""

from pyq.pipeline import run_pyq_pipeline


def run_pyq(filepath: str | None = None, force: bool = False) -> list[dict]:
    """
    Main entry point for the central system.

    Parameters
    ----------
    filepath : str or None
        Path to a single PYQ file, or None to process all in pyq_uploads/.
    force : bool
        Re-process even if already tracked.

    Returns
    -------
    list[dict]
        One result dict per file: {filename, status, questions, matches}
    """
    return run_pyq_pipeline(filepath=filepath, force=force)
