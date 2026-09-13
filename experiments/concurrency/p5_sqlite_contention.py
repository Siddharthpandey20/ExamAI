"""
P5 — SQLite write contention under concurrency.

Question: is SQLite a real limit on ingestion concurrency, or is the existing
WAL + busy_timeout + micro-transaction design already sufficient?

Uses a THROWAWAY database with the production schema and the exact PRAGMA
configuration from indexing/database.py. The real examai.db is never opened.

The write pattern mirrors production: many short transactions, as
jobs/tasks.py does per question and per progress tick, rather than one long
transaction.

Usage:  python experiments/concurrency/p5_sqlite_contention.py
Writes: experiments/benchmarks/p5_sqlite_contention.json
"""

import json
import statistics
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from sqlalchemy import create_engine, event                    # noqa: E402
from sqlalchemy.orm import sessionmaker                        # noqa: E402
from sqlalchemy.pool import NullPool                           # noqa: E402

from indexing.models import Base, Document, Slide, PYQQuestion, PYQMatch  # noqa: E402

OUT = REPO / "experiments" / "benchmarks" / "p5_sqlite_contention.json"
WRITERS = [1, 2, 3, 4, 6, 8]
TXNS_PER_WRITER = 40


def make_engine(path, wal=True):
    """Same configuration production uses."""
    eng = create_engine(f"sqlite:///{path}", echo=False, pool_pre_ping=True,
                        connect_args={"check_same_thread": False, "timeout": 30},
                        poolclass=NullPool)

    @event.listens_for(eng, "connect")
    def _pragmas(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute(f"PRAGMA journal_mode={'WAL' if wal else 'DELETE'}")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    return eng


def seed(Factory):
    s = Factory()
    d = Document(filename="x.md", file_hash="h", status="processed", subject="CN")
    s.add(d)
    s.flush()
    for p in range(1, 51):
        s.add(Slide(doc_id=d.id, page_number=p, subject="CN", summary=f"s{p}",
                    concepts="tcp", raw_text=f"body {p}", is_embedded=True))
    s.commit()
    s.close()


def writer(Factory, worker_id, n_txns, latencies, errors, lock):
    """One short transaction per iteration, as production does."""
    for i in range(n_txns):
        t = time.perf_counter()
        try:
            s = Factory()
            try:
                q = PYQQuestion(question_text=f"w{worker_id} q{i}",
                                source_file="p.pdf", subject="CN")
                s.add(q)
                s.flush()
                for sid in (1, 2, 3):
                    s.add(PYQMatch(pyq_id=q.id, slide_id=sid, similarity_score=0.03))
                    sl = s.query(Slide).filter(Slide.id == sid).first()
                    if sl:
                        sl.pyq_hit_count = (sl.pyq_hit_count or 0) + 1
                s.commit()
            finally:
                s.close()
            with lock:
                latencies.append((time.perf_counter() - t) * 1000)
        except Exception as exc:
            with lock:
                key = "locked" if "locked" in str(exc).lower() else type(exc).__name__
                errors[key] = errors.get(key, 0) + 1


def run_level(n_writers, wal=True):
    tmp = Path(tempfile.mkdtemp()) / "contention.db"
    eng = make_engine(tmp, wal=wal)
    Base.metadata.create_all(eng)
    Factory = sessionmaker(bind=eng)
    seed(Factory)

    latencies, errors, lock = [], {}, threading.Lock()
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=n_writers) as pool:
        list(pool.map(lambda w: writer(Factory, w, TXNS_PER_WRITER,
                                       latencies, errors, lock), range(n_writers)))
    wall = time.perf_counter() - start

    eng.dispose()
    total = n_writers * TXNS_PER_WRITER
    lat = sorted(latencies)
    return {
        "writers": n_writers,
        "journal": "WAL" if wal else "DELETE",
        "transactions": total,
        "succeeded": len(lat),
        "failed": total - len(lat),
        "errors": errors,
        "wall_sec": round(wall, 2),
        "txn_per_sec": round(len(lat) / wall, 1) if wall else 0,
        "p50_ms": round(statistics.median(lat), 2) if lat else None,
        "p95_ms": round(lat[int(len(lat) * 0.95)], 2) if lat else None,
        "max_ms": round(lat[-1], 2) if lat else None,
    }


def main():
    print(f"P5 — SQLite write contention, {TXNS_PER_WRITER} short "
          f"transactions per writer, throwaway database\n")
    rows = []
    hdr = (f"{'W':>2s} {'mode':>6s} {'txns':>5s} {'wall_s':>7s} {'txn/s':>7s} "
           f"{'p50_ms':>7s} {'p95_ms':>7s} {'max_ms':>7s} {'fail':>5s}")
    print(hdr)
    print("-" * len(hdr))
    for w in WRITERS:
        r = run_level(w, wal=True)
        rows.append(r)
        print(f"{r['writers']:>2d} {r['journal']:>6s} {r['transactions']:>5d} "
              f"{r['wall_sec']:>7.2f} {r['txn_per_sec']:>7.1f} {r['p50_ms']:>7.2f} "
              f"{r['p95_ms']:>7.2f} {r['max_ms']:>7.2f} {r['failed']:>5d}")
        if r["errors"]:
            print(f"     errors: {r['errors']}")

    print("\n--- same load without WAL, to show what WAL is buying ---")
    for w in (1, 4, 8):
        r = run_level(w, wal=False)
        rows.append(r)
        print(f"{r['writers']:>2d} {r['journal']:>6s} {r['transactions']:>5d} "
              f"{r['wall_sec']:>7.2f} {r['txn_per_sec']:>7.1f} {r['p50_ms']:>7.2f} "
              f"{r['p95_ms']:>7.2f} {r['max_ms']:>7.2f} {r['failed']:>5d}")
        if r["errors"]:
            print(f"     errors: {r['errors']}")

    wal_rows = [r for r in rows if r["journal"] == "WAL"]
    best = max(wal_rows, key=lambda r: r["txn_per_sec"])
    base = wal_rows[0]["txn_per_sec"]
    print(f"\npeak WAL throughput at {best['writers']} writers "
          f"({best['txn_per_sec']} txn/s, {best['txn_per_sec']/base:.2f}x over 1 writer)")
    total_fail = sum(r["failed"] for r in wal_rows)
    print(f"total WAL failures across all levels: {total_fail}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
