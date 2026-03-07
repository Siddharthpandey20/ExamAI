"""
__main__.py — CLI entry point for the structuring module.

Usage:
    python -m structuring                        # Process all pending knowledge files
    python -m structuring knowledge/3.md         # Process a specific file
"""

import sys
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

from structuring import run_structuring


async def main():
    source = sys.argv[1] if len(sys.argv) > 1 else None
    results = await run_structuring(source)

    if results:
        print("\nStructured files:")
        for r in results:
            print(f"  {r}")


if __name__ == "__main__":
    asyncio.run(main())
