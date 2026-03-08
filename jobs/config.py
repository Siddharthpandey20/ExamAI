"""
config.py — Configuration for the async job infrastructure.

Redis is required as the Celery message broker and result backend.
Start Redis before launching the worker:
  Docker:   docker run -d -p 6379:6379 redis:alpine
  WSL:      sudo apt install redis-server && redis-server
  Windows:  install Memurai (https://www.memurai.com/)
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Redis ────────────────────────────────────────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ── Worker ───────────────────────────────────────────────────────────────
# 'threads' gives parallel task execution on Windows.
# 'solo' is the safest fallback (serial, one task at a time).
WORKER_CONCURRENCY = int(os.environ.get("EXAMAI_WORKER_CONCURRENCY", "3"))
WORKER_POOL = os.environ.get("EXAMAI_WORKER_POOL", "threads")
