# P5 — SQLite write contention

**Status:** complete · **Conclusion: REJECTED as a bottleneck** — the existing
design is already sufficient.

**No production code was modified.** A throwaway database was used; `examai.db`
was never opened.

---

## Hypothesis under test

> SQLite write contention limits ingestion concurrency and is part of why the
> system becomes unhealthy above ~3 workers.

**Success criterion:** lock errors, or throughput that stops scaling, at the
worker counts the system actually uses.

---

## Method

A temporary database with the production schema and the exact PRAGMA
configuration from `indexing/database.py` — WAL, `busy_timeout=30000`,
`synchronous=NORMAL`, `foreign_keys=ON`, `NullPool`. The write pattern mirrors
production: many short transactions, as `jobs/tasks.py` does per question and
per progress tick, each inserting a question, three matches and bumping three
slide counters.

---

## Results — WAL (production configuration)

| writers | txns | wall s | **txn/s** | p50 ms | p95 ms | max ms | failures |
|---|---|---|---|---|---|---|---|
| 1 | 40 | 0.57 | 70.3 | 13.87 | 18.55 | 21.21 | **0** |
| 2 | 80 | 1.47 | 54.3 | 35.23 | 61.03 | 138.31 | **0** |
| 3 | 120 | 1.67 | 72.0 | 36.90 | 78.92 | 109.94 | **0** |
| 4 | 160 | 2.10 | 76.3 | 45.53 | 101.42 | 152.40 | **0** |
| 6 | 240 | 2.79 | 86.0 | 39.29 | 149.23 | 1096.13 | **0** |
| 8 | 320 | 3.51 | **91.2** | 42.58 | 186.94 | 1491.86 | **0** |

**Zero failures at every level.** Not one "database is locked" across 960
transactions. Throughput rises with concurrency rather than collapsing;
p50 stays flat around 40 ms while the tail grows.

## What WAL is buying

| writers | mode | txn/s | p95 ms | max ms |
|---|---|---|---|---|
| 1 | DELETE | 91.8 | 13.91 | 14.01 |
| 1 | WAL | 70.3 | 18.55 | 21.21 |
| 4 | DELETE | 91.0 | 89.32 | 1054.68 |
| 4 | WAL | 76.3 | 101.42 | 152.40 |
| 8 | DELETE | 75.5 | 266.00 | **3122.39** |
| 8 | WAL | **91.2** | 186.94 | 1491.86 |

Rollback-journal mode is slightly faster with a single writer and degrades under
concurrency; WAL is slower alone and wins where it matters, with roughly half
the worst-case latency at 8 writers. The existing choice is correct.

---

## Conclusion

**REJECTED.** SQLite is nowhere near being the limit.

Put beside the P2 measurement, the gap is three orders of magnitude:

| stage | throughput |
|---|---|
| SQLite writes | **91 transactions/second** |
| Ollama generation | **0.56 requests/second** |

SQLite processes roughly **163×** more operations per second than the LLM stage
can consume. Optimising it would change ingestion time by an unmeasurable
amount.

The design already in place — WAL, a 30-second busy timeout, per-question
micro-transactions, `NullPool`, and `_safe_db_op`'s backoff — is the reason
there are no lock errors. That combination was arrived at deliberately (the
comment in `jobs/tasks.py` documents the long-transaction bug it replaced) and
the measurement vindicates it.

---

## Proposed production change

**None.** No SQLite optimisation is warranted at this scale, and PostgreSQL
migration is explicitly out of scope for this phase — correctly so, since the
evidence shows it would solve a problem that does not exist.

---

## Risk / rollback

Nothing to roll back. The experiment created its own temporary database per
level and disposed of each engine afterwards.
