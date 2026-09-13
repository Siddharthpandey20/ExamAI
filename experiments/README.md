# experiments/

Isolated experimental area. Nothing here is imported by production code.

Rules in force for this phase:
  - no production code, configuration, schema or historical data is modified
  - every experiment records a baseline before it measures anything
  - a conclusion is SUPPORTED / REJECTED / INCONCLUSIVE against a stated
    success criterion, never a qualitative impression
  - a proven experiment produces a promotion checkpoint in reports/ and stops
    there; promotion into production is a separate, approved step

Layout:
  rag/          retrieval and answer-quality experiments
  ingestion/    ingestion pipeline profiling
  concurrency/  Ollama, Celery, SQLite and Chroma contention
  benchmarks/   raw measurement output (JSON)
  reports/      experiment reports and promotion checkpoints
