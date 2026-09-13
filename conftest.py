"""
Root pytest configuration.

The ad-hoc test scripts at the repository root predate the tests/ suite. They
are driver scripts rather than pytest tests: they need a live uvicorn server,
Redis, Celery, Ollama and a populated corpus, and several take positional
arguments pytest would try to interpret as fixtures.

They are gitignored, so a clean clone never sees them and the suite in tests/
is the whole story. This list keeps `pytest .` correct on a developer machine
that still has them lying around.
"""

collect_ignore = [
    "test.py",
    "test_comprehensive.py",
    "test_db_concurrency.py",
    "test_db_inspect.py",
    "test_gemini.py",
    "test_routes.py",
    "try.py",
]
