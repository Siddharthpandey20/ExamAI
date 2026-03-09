"""
__main__.py — Entry point for the indexing pipeline.

Usage:
    python -m indexing                     # index all knowledge/*.md files
    python -m indexing knowledge/3.md      # index a specific file
    python -m indexing --force             # re-index even if cached
"""

import sys
import logging

from indexing.pipeline import run_indexing

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

    # Extract --subject NAME
    subject = ""
    if "--subject" in args:
        idx = args.index("--subject")
        if idx + 1 < len(args):
            subject = args[idx + 1].upper()
            args.pop(idx + 1)
            args.pop(idx)
        else:
            print("ERROR: --subject requires a value")
            sys.exit(1)

    filepath = args[0] if args else None

    results = run_indexing(filepath=filepath, force=force, subject=subject)

    # Print summary table
    print("\n" + "=" * 60)
    print("INDEXING RESULTS")
    print("=" * 60)
    for r in results:
        status = r["status"].upper()
        count = r["slides_indexed"]
        cached = " (cached)" if r["cached"] else ""
        print(f"  {r['filename']:<45} {status:<12} {count} slides{cached}")
    print("=" * 60)


if __name__ == "__main__":
    main()
