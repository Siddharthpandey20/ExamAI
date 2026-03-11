"""
config.py — Configuration for the async job infrastructure.

Redis is required as the Celery message broker and result backend.
Start Redis before launching the worker:
  Docker:   docker run -d -p 6379:6379 redis:alpine
  WSL:      sudo apt install redis-server && redis-server
  Windows:  install Memurai (https://www.memurai.com/)

Concurrency notes:
  - 'threads' pool allows parallel task execution but shares SQLite.
  - SQLite WAL + busy_timeout=30s + NullPool + micro-transactions handles this safely.
  - Each DB write uses a SHORT session (open→write→commit→close) to avoid holding
    the SQLite write lock for extended periods.
  - If you still see lock issues, set EXAMAI_WORKER_POOL=solo for serial execution.
"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Redis ────────────────────────────────────────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ── Worker ───────────────────────────────────────────────────────────────
# 'threads' gives parallel task execution on Windows.
# Concurrency 2 avoids overwhelming SQLite with too many concurrent writers.
WORKER_CONCURRENCY = int(os.environ.get("EXAMAI_WORKER_CONCURRENCY", "2"))
WORKER_POOL = os.environ.get("EXAMAI_WORKER_POOL", "threads")
