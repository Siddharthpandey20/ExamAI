"""
__main__.py — Entry point for the PYQ pipeline.

Usage:
    python -m pyq                          # process all PYQ files in pyq_uploads/
    python -m pyq path/to/paper.pdf        # process a specific file
    python -m pyq --force                  # re-process even if already tracked
"""

import sys
import logging

from pyq.pipeline import run_pyq_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    args = sys.argv[1:]

    force = "--force" in args
    if force:
        args.remove("--force")

    filepath = args[0] if args else None

    results = run_pyq_pipeline(filepath=filepath, force=force)

    # Print summary table
    print("\n" + "=" * 60)
    print("PYQ PROCESSING RESULTS")
    print("=" * 60)
    for r in results:
        status = r["status"].upper()
        q_count = r["questions"]
        m_count = r["matches"]
        print(f"  {r['filename']:<40} {status:<10} {q_count} questions  {m_count} matches")
    print("=" * 60)

    total_q = sum(r["questions"] for r in results)
    total_m = sum(r["matches"] for r in results)
    print(f"  TOTAL: {total_q} questions extracted, {total_m} slide matches")


if __name__ == "__main__":
    main()
