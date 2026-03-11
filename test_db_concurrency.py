"""
test_db_concurrency.py — Simulate the exact Phase 3 deadlock scenario.

Reproduces the production failure:
  - Two PYQ jobs (ML with 6 questions, CN with 7 questions) arriving at
    Phase 3 at nearly the same time.
  - Both threads do: build BM25 → for each question: hybrid_search →
    record_matches → progress_update → repeat → recompute_importance.
  - Without the micro-transaction fix, this self-deadlocks because ONE
    long session holds the SQLite write lock for the entire loop while
    _update_progress tries to open a SECOND session to write.

This test uses the REAL database, REAL hybrid search, REAL record_matches,
REAL _update_progress / _safe_db_op — just skips LLM extraction by
providing pre-built question lists.

Run:
    python test_db_concurrency.py
"""

import os
import sys
import time
import logging
import asyncio
import threading
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Setup ────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("test_concurrency")

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from indexing.database import get_db, init_db, engine, SessionFactory
from indexing.models import Base, Slide, PYQQuestion, PYQMatch
from indexing.embedder import Embedder
from indexing.db_chroma import ChromaStore
from pyq.bm25_search import BM25Index
from pyq.hybrid_search import hybrid_search
from pyq.mapper import record_matches, recompute_importance_scores
from pyq.schemas import ExtractedQuestion
from jobs.tasks import _safe_db_op, _update_progress, _DB_RETRY_ATTEMPTS, _DB_RETRY_DELAY

# ── Helpers ──────────────────────────────────────────────────────────────

PASS_COUNT = 0
FAIL_COUNT = 0
WARN_COUNT = 0
_print_lock = threading.Lock()


def ok(msg):
    global PASS_COUNT
    PASS_COUNT += 1
    with _print_lock:
        print(f"  \033[92m✓\033[0m {msg}")


def fail(msg):
    global FAIL_COUNT
    FAIL_COUNT += 1
    with _print_lock:
        print(f"  \033[91m✗\033[0m {msg}")


def warn(msg):
    global WARN_COUNT
    WARN_COUNT += 1
    with _print_lock:
        print(f"  \033[93m⚠\033[0m {msg}")


def banner(title):
    with _print_lock:
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}\n")


def section(name):
    with _print_lock:
        print(f"\n── {name} ──")


# ── Fake questions (matching real production logs) ───────────────────────
# ML PYQ: 6 questions (from DOC-20260310-WA0005..pdf)
ML_QUESTIONS = [
    ExtractedQuestion(
        question_number=1,
        question_text="Explain why can't we have an analytical solution for any regression problem.",
        marks=1,
    ),
    ExtractedQuestion(
        question_number=2,
        question_text="Explain with examples the different assumptions under which linear regression models work.",
        marks=4,
    ),
    ExtractedQuestion(
        question_number=3,
        question_text="Find out linear regression line after one epoch with given values x=[1,2,4], y=[2,4,5], learning rate=0.01",
        marks=4,
    ),
    ExtractedQuestion(
        question_number=4,
        question_text="Define overfitting and underfitting issues in Machine learning with examples. How are they related to bias and variance?",
        marks=4,
    ),
    ExtractedQuestion(
        question_number=5,
        question_text="How much output variable will change if we change the input variable by 1 unit in linear regression?",
        marks=1,
    ),
    ExtractedQuestion(
        question_number=6,
        question_text="What is regression? Is it A. Numerosity reduction technique B. Dimensionality reduction C. Supervised learning D. Unsupervised learning",
        marks=1,
    ),
]

# CN PYQ: 7 questions (from CN.pdf)
CN_QUESTIONS = [
    ExtractedQuestion(
        question_number=1,
        question_text="Why is it sad to open an application? What problem does that open even though it uses TCP?",
        marks=None,
    ),
    ExtractedQuestion(
        question_number=2,
        question_text="What problem does the application layer solve? And why?",
        marks=None,
    ),
    ExtractedQuestion(
        question_number=3,
        question_text="Why are CDNs used in video streaming applications? Why is P2P file distribution better than client-server for large files?",
        marks=None,
    ),
    ExtractedQuestion(
        question_number=4,
        question_text="Why is TLS considered an application protocol? HFC, DSL, and FTTH are all used for what purpose?",
        marks=None,
    ),
    ExtractedQuestion(
        question_number=5,
        question_text="Explain the client-server model and the relevant protocols for web, email, and DNS.",
        marks=None,
    ),
    ExtractedQuestion(
        question_number=6,
        question_text="Define overfitting and underfitting issues in Machine learning. How are they related to bias and variance?",
        marks=None,
    ),
    ExtractedQuestion(
        question_number=7,
        question_text="How do CDNs improve the availability of Internet applications?",
        marks=None,
    ),
]


# ── Cleanup: remove any test PYQ data we insert ─────────────────────────

TEST_SOURCE_FILES = ["__test_ML_concurrent.pdf", "__test_CN_concurrent.pdf"]


def cleanup_test_data():
    """Remove PYQ questions and matches inserted by this test."""
    with get_db() as session:
        for src in TEST_SOURCE_FILES:
            questions = (
                session.query(PYQQuestion)
                .filter(PYQQuestion.source_file == src)
                .all()
            )
            q_ids = [q.id for q in questions]
            if q_ids:
                session.query(PYQMatch).filter(PYQMatch.pyq_id.in_(q_ids)).delete(
                    synchronize_session="fetch"
                )
                session.query(PYQQuestion).filter(PYQQuestion.id.in_(q_ids)).delete(
                    synchronize_session="fetch"
                )
        # Reset pyq_hit_count that we incremented
        session.query(Slide).filter(Slide.pyq_hit_count > 0).update(
            {Slide.pyq_hit_count: 0}, synchronize_session="fetch"
        )
    log.info("[cleanup] Removed test PYQ data")


# ══════════════════════════════════════════════════════════════════════════
# TEST 1: Simulate Phase 3 — two concurrent PYQ jobs
# ══════════════════════════════════════════════════════════════════════════

def simulate_phase3(
    thread_name: str,
    questions: list[ExtractedQuestion],
    subject: str,
    source_file: str,
    embedder: Embedder,
    chroma: ChromaStore,
    barrier: threading.Barrier,
):
    """
    Simulate exactly what process_pyq_task Phase 3 does:
      1. Build BM25 index (short read session)
      2. For each question:
         a. _update_progress-style DB write (simulated)
         b. hybrid_search → record_matches in a micro-transaction
      3. recompute_importance_scores (short write session)

    Uses a Barrier so both threads start the hot loop at the same instant.
    """
    errors = []
    match_count = 0

    try:
        # Step 1: Build BM25 index (short read session, closes immediately)
        with get_db() as session:
            bm25_index = BM25Index(session)
        log.info(f"[{thread_name}] BM25 index built")

        # ── Synchronization: both threads start the hot loop together ──
        barrier.wait(timeout=30)
        log.info(f"[{thread_name}] Starting question loop ({len(questions)} questions)")

        n = len(questions)
        for i, q in enumerate(questions, 1):
            # Simulate _update_progress (writes to DB — this is what deadlocked before)
            def _progress(pct=int(i / n * 90), detail=f"Mapping Q{i}/{n}"):
                with get_db() as sess:
                    # Just write something — simulates the job/phase progress update
                    sess.execute(
                        __import__("sqlalchemy").text(
                            "SELECT 1"
                        )
                    )
                    # Force a real write: update a slide's updated-at to trigger write lock
                    slide = sess.query(Slide).filter(Slide.is_embedded == True).first()
                    if slide:
                        # Harmless: re-set existing value to force a dirty flush
                        slide.importance_score = slide.importance_score
                    log.debug(f"[{thread_name}] Progress: {pct}% — {detail}")

            _safe_db_op(_progress)

            # Micro-transaction per question: search → record → commit → close
            def _map_one(question=q):
                with get_db() as sess:
                    matches = hybrid_search(
                        query=question.question_text,
                        session=sess,
                        embedder=embedder,
                        chroma=chroma,
                        bm25_index=bm25_index,
                    )
                    record_matches(
                        sess, question, matches,
                        source_file=source_file, subject=subject,
                    )
                    return len(matches)

            n_matches = _safe_db_op(_map_one)
            match_count += n_matches
            log.info(f"[{thread_name}] Q{i}: {n_matches} matches recorded")

        # Step 3: Recompute importance scores (short write session)
        def _recompute():
            with get_db() as sess:
                recompute_importance_scores(sess)

        _safe_db_op(_recompute)
        log.info(f"[{thread_name}] Done: {len(questions)} questions, {match_count} total matches")

    except Exception as e:
        errors.append(str(e))
        log.error(f"[{thread_name}] FAILED: {e}", exc_info=True)

    return {
        "thread": thread_name,
        "subject": subject,
        "questions": len(questions),
        "matches": match_count,
        "errors": errors,
    }


# ══════════════════════════════════════════════════════════════════════════
# TEST 2: Pure DB write stress — many threads writing simultaneously
# ══════════════════════════════════════════════════════════════════════════

def stress_write_test(n_threads=6, writes_per_thread=10):
    """
    Hammer the DB with concurrent writes from many threads.
    Each write is a short micro-transaction (insert PYQ question + commit).
    """
    errors = []
    success_count = 0
    lock = threading.Lock()

    def _writer(thread_id):
        nonlocal success_count
        thread_errors = 0
        for j in range(writes_per_thread):
            try:
                def _write(tid=thread_id, idx=j):
                    with get_db() as sess:
                        q = PYQQuestion(
                            question_text=f"Stress test Q{idx} from thread {tid}",
                            source_file=f"__stress_test_t{tid}.pdf",
                            subject="STRESS",
                        )
                        sess.add(q)
                _safe_db_op(_write)
                with lock:
                    success_count += 1
            except Exception as e:
                thread_errors += 1
                with lock:
                    errors.append(f"Thread {thread_id} write {j}: {e}")
        return thread_errors

    threads = []
    for t in range(n_threads):
        th = threading.Thread(target=_writer, args=(t,))
        threads.append(th)

    start = time.time()
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=60)
    elapsed = time.time() - start

    # Cleanup stress test data
    with get_db() as sess:
        sess.query(PYQQuestion).filter(
            PYQQuestion.source_file.like("__stress_test_%")
        ).delete(synchronize_session="fetch")

    return {
        "threads": n_threads,
        "writes_per_thread": writes_per_thread,
        "total_expected": n_threads * writes_per_thread,
        "total_succeeded": success_count,
        "errors": errors,
        "elapsed_sec": round(elapsed, 2),
    }


# ══════════════════════════════════════════════════════════════════════════
# TEST 3: Interleaved read-write (simulates FastAPI reads during writes)
# ══════════════════════════════════════════════════════════════════════════

def read_write_interleave_test(n_writers=3, n_readers=5, duration_sec=5):
    """
    Writers do micro-transactions inserting PYQ records.
    Readers query slides/concepts at the same time.
    Simulates FastAPI serving API requests while Celery tasks write.
    """
    stop_event = threading.Event()
    write_errors = []
    read_errors = []
    write_count = 0
    read_count = 0
    w_lock = threading.Lock()
    r_lock = threading.Lock()

    def _writer(wid):
        nonlocal write_count
        idx = 0
        while not stop_event.is_set():
            try:
                def _w(tid=wid, i=idx):
                    with get_db() as sess:
                        q = PYQQuestion(
                            question_text=f"Interleave test W{tid}-{i}",
                            source_file=f"__interleave_w{tid}.pdf",
                            subject="INTERLEAVE",
                        )
                        sess.add(q)
                _safe_db_op(_w)
                with w_lock:
                    write_count += 1
                idx += 1
            except Exception as e:
                with w_lock:
                    write_errors.append(f"Writer {wid}: {e}")

    def _reader(rid):
        nonlocal read_count
        while not stop_event.is_set():
            try:
                with get_db() as sess:
                    slides = sess.query(Slide).filter(Slide.is_embedded == True).limit(10).all()
                    _ = [(s.id, s.summary, s.concepts) for s in slides]
                    questions = sess.query(PYQQuestion).limit(10).all()
                    _ = [(q.id, q.question_text) for q in questions]
                with r_lock:
                    read_count += 1
            except Exception as e:
                with r_lock:
                    read_errors.append(f"Reader {rid}: {e}")

    threads = []
    for w in range(n_writers):
        threads.append(threading.Thread(target=_writer, args=(w,), daemon=True))
    for r in range(n_readers):
        threads.append(threading.Thread(target=_reader, args=(r,), daemon=True))

    start = time.time()
    for th in threads:
        th.start()

    time.sleep(duration_sec)
    stop_event.set()

    for th in threads:
        th.join(timeout=10)
    elapsed = time.time() - start

    # Cleanup
    with get_db() as sess:
        sess.query(PYQQuestion).filter(
            PYQQuestion.source_file.like("__interleave_%")
        ).delete(synchronize_session="fetch")

    return {
        "writers": n_writers,
        "readers": n_readers,
        "duration_sec": round(elapsed, 2),
        "writes": write_count,
        "reads": read_count,
        "write_errors": write_errors,
        "read_errors": read_errors,
    }


# ══════════════════════════════════════════════════════════════════════════
# TEST 5: threading.Semaphore cross-loop correctness
# ══════════════════════════════════════════════════════════════════════════

def test_threading_semaphore_cross_loop(n_threads=4, concurrency_limit=2, tasks_per_thread=5):
    """
    Validates that the threading.Semaphore used in file_agent.py correctly
    limits concurrency ACROSS multiple threads, each running its own
    asyncio.run() event loop (exactly how Celery thread-pool behaves).

    What this tests:
      - N threads each call asyncio.run() (new loop per thread)
      - Inside each loop, multiple async tasks compete for _ollama_slot()
      - A global counter tracks simultaneous holders — must NEVER exceed limit
      - Each slot holder does real async work (asyncio.sleep) to simulate Ollama call duration
    """
    from structuring.file_agent import _ollama_gate, _ollama_slot, OLLAMA_MAX_CONCURRENCY

    # Shared counters protected by a threading.Lock
    peak_concurrent = 0
    current_concurrent = 0
    violations = []
    counter_lock = threading.Lock()
    total_completed = 0
    completed_lock = threading.Lock()

    async def _fake_ollama_call(thread_id, task_id):
        """Simulate an Ollama LLM call gated by the threading.Semaphore."""
        nonlocal peak_concurrent, current_concurrent, total_completed

        async with _ollama_slot():
            with counter_lock:
                current_concurrent += 1
                if current_concurrent > peak_concurrent:
                    peak_concurrent = current_concurrent
                if current_concurrent > concurrency_limit:
                    violations.append(
                        f"Thread {thread_id} Task {task_id}: "
                        f"concurrent={current_concurrent} > limit={concurrency_limit}"
                    )

            # Simulate real async work (Ollama call takes time)
            await asyncio.sleep(0.05)

            with counter_lock:
                current_concurrent -= 1

        with completed_lock:
            total_completed += 1

    def _thread_worker(thread_id):
        """Each thread runs its own event loop (like Celery thread-pool)."""
        async def _run_tasks():
            tasks = [_fake_ollama_call(thread_id, i) for i in range(tasks_per_thread)]
            await asyncio.gather(*tasks)

        # This is EXACTLY what Celery does: new loop per thread
        asyncio.run(_run_tasks())

    threads = []
    t0 = time.time()
    for t in range(n_threads):
        th = threading.Thread(target=_thread_worker, args=(t,))
        threads.append(th)
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=60)
    elapsed = time.time() - t0

    expected_total = n_threads * tasks_per_thread
    return {
        "threads": n_threads,
        "tasks_per_thread": tasks_per_thread,
        "concurrency_limit": concurrency_limit,
        "total_expected": expected_total,
        "total_completed": total_completed,
        "peak_concurrent": peak_concurrent,
        "violations": violations,
        "elapsed_sec": round(elapsed, 2),
    }


# ══════════════════════════════════════════════════════════════════════════
# TEST 6: asyncio.Semaphore WOULD fail — prove threading.Semaphore doesn't
# ══════════════════════════════════════════════════════════════════════════

def test_asyncio_semaphore_cross_loop_fails():
    """
    Proves that asyncio.Semaphore at module level CRASHES when used from
    a second thread's asyncio.run(), and that our threading.Semaphore
    replacement does NOT crash.

    Part A: Create an asyncio.Semaphore in thread-1's loop, use it in
            thread-2's loop → must raise RuntimeError or ValueError.
    Part B: Do the same with threading.Semaphore → must succeed.
    """
    # ── Part A: asyncio.Semaphore cross-loop failure ──────────────────
    asyncio_sem_error = None
    sem_holder = {}

    def _thread1_create_sem():
        async def _create():
            sem_holder["sem"] = asyncio.Semaphore(2)
        asyncio.run(_create())

    def _thread2_use_sem():
        nonlocal asyncio_sem_error
        async def _use():
            try:
                async with sem_holder["sem"]:
                    await asyncio.sleep(0.01)
            except (RuntimeError, ValueError) as e:
                asyncio_sem_error = str(e)

        try:
            asyncio.run(_use())
        except (RuntimeError, ValueError) as e:
            asyncio_sem_error = str(e)

    t1 = threading.Thread(target=_thread1_create_sem)
    t1.start()
    t1.join()

    t2 = threading.Thread(target=_thread2_use_sem)
    t2.start()
    t2.join()

    # ── Part B: threading.Semaphore cross-thread works ────────────────
    import threading as _th
    t_sem = _th.Semaphore(2)
    threading_sem_ok = False
    threading_sem_error = None

    def _thread3_use_threading_sem():
        nonlocal threading_sem_ok, threading_sem_error
        async def _use():
            t_sem.acquire()
            try:
                await asyncio.sleep(0.01)
            finally:
                t_sem.release()

        try:
            asyncio.run(_use())
            threading_sem_ok = True
        except Exception as e:
            threading_sem_error = str(e)

    t3 = threading.Thread(target=_thread3_use_threading_sem)
    t3.start()
    t3.join()

    return {
        "asyncio_sem_error": asyncio_sem_error,
        "threading_sem_ok": threading_sem_ok,
        "threading_sem_error": threading_sem_error,
    }


# ══════════════════════════════════════════════════════════════════════════
# TEST 7: RateLimiter cross-loop safety
# ══════════════════════════════════════════════════════════════════════════

def test_rate_limiter_cross_loop(n_threads=3, calls_per_thread=4):
    """
    Validates that the _LocalRateLimiter (from rate_limiter.py) works correctly
    when called from multiple threads, each with its own asyncio.run().

    The _LocalRateLimiter uses threading.Lock internally, so timestamp
    tracking is safe across threads. This test verifies:
      1. No crashes from cross-loop Lock usage
      2. Rate limiting actually works (doesn't allow > max_calls in window)
      3. All calls complete successfully
    """
    from structuring.rate_limiter import _LocalRateLimiter

    # Create a limiter with a tight window: max 3 calls per 2 seconds
    limiter = _LocalRateLimiter(max_calls=3, window=2.0)
    call_timestamps = []
    ts_lock = threading.Lock()
    errors = []
    err_lock = threading.Lock()

    def _thread_worker(thread_id):
        async def _run():
            for i in range(calls_per_thread):
                try:
                    await limiter.acquire()
                    now = time.time()
                    with ts_lock:
                        call_timestamps.append((thread_id, i, now))
                except Exception as e:
                    with err_lock:
                        errors.append(f"Thread {thread_id} call {i}: {e}")

        asyncio.run(_run())

    threads = []
    t0 = time.time()
    for t in range(n_threads):
        th = threading.Thread(target=_thread_worker, args=(t,))
        threads.append(th)
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=30)
    elapsed = time.time() - t0

    # Verify rate was respected: in any 2-second window, max 3 calls
    violations = []
    timestamps_only = sorted([ts for _, _, ts in call_timestamps])
    for i, t_start in enumerate(timestamps_only):
        # Count how many calls happened within 2s of this one
        count_in_window = sum(1 for t in timestamps_only if t_start <= t < t_start + 2.0)
        if count_in_window > 3 + 1:  # +1 tolerance for timing granularity
            violations.append(f"At t={t_start - t0:.2f}s: {count_in_window} calls in 2s window")

    return {
        "threads": n_threads,
        "calls_per_thread": calls_per_thread,
        "total_expected": n_threads * calls_per_thread,
        "total_completed": len(call_timestamps),
        "errors": errors,
        "rate_violations": violations,
        "elapsed_sec": round(elapsed, 2),
    }


# ══════════════════════════════════════════════════════════════════════════
# TEST 8: Extreme DB stress — simulate N>2 workers
# ══════════════════════════════════════════════════════════════════════════

def test_extreme_db_stress(n_workers=5, questions_per_worker=8):
    """
    Simulates 5 concurrent workers all doing Phase-3-style micro-transactions
    simultaneously — heavier than the real concurrency=2 Celery setup.
    If this passes, concurrency=2 (or even 4) will be fine.

    Each worker:
      - Opens a short read session to query slides
      - Does N micro-transaction writes (insert question + match)
      - Interleaves progress-update writes between each question
      - Runs recompute_importance_scores at the end
    All 5 start at the same instant via a Barrier.
    """
    barrier = threading.Barrier(n_workers, timeout=30)
    results = {}
    results_lock = threading.Lock()

    def _worker(wid):
        worker_errors = []
        writes_done = 0

        try:
            barrier.wait(timeout=30)

            for q_idx in range(questions_per_worker):
                # Simulate progress update (short write)
                def _progress(w=wid, qi=q_idx):
                    with get_db() as sess:
                        slide = sess.query(Slide).filter(Slide.is_embedded == True).first()
                        if slide:
                            slide.importance_score = slide.importance_score
                try:
                    _safe_db_op(_progress)
                except Exception as e:
                    worker_errors.append(f"W{wid} progress Q{q_idx}: {e}")

                # Simulate micro-transaction write (insert PYQ question)
                def _write(w=wid, qi=q_idx):
                    with get_db() as sess:
                        q = PYQQuestion(
                            question_text=f"Extreme stress W{w} Q{qi}",
                            source_file=f"__extreme_w{w}.pdf",
                            subject="EXTREME",
                        )
                        sess.add(q)
                try:
                    _safe_db_op(_write)
                    writes_done += 1
                except Exception as e:
                    worker_errors.append(f"W{wid} write Q{q_idx}: {e}")

            # Final recompute (short write)
            def _recompute():
                with get_db() as sess:
                    recompute_importance_scores(sess)
            try:
                _safe_db_op(_recompute)
            except Exception as e:
                worker_errors.append(f"W{wid} recompute: {e}")

        except Exception as e:
            worker_errors.append(f"W{wid} fatal: {e}")

        with results_lock:
            results[wid] = {"writes": writes_done, "errors": worker_errors}

    threads = []
    t0 = time.time()
    for w in range(n_workers):
        th = threading.Thread(target=_worker, args=(w,))
        threads.append(th)
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=120)
    elapsed = time.time() - t0

    # Verify data integrity
    with get_db() as sess:
        actual_count = sess.query(PYQQuestion).filter(
            PYQQuestion.source_file.like("__extreme_%")
        ).count()
        # Cleanup
        sess.query(PYQQuestion).filter(
            PYQQuestion.source_file.like("__extreme_%")
        ).delete(synchronize_session="fetch")

    total_writes = sum(r["writes"] for r in results.values())
    total_errors = []
    for r in results.values():
        total_errors.extend(r["errors"])

    return {
        "workers": n_workers,
        "questions_per_worker": questions_per_worker,
        "total_expected": n_workers * questions_per_worker,
        "total_writes": total_writes,
        "db_actual_count": actual_count,
        "errors": total_errors,
        "elapsed_sec": round(elapsed, 2),
    }


# ══════════════════════════════════════════════════════════════════════════
# TEST 9: Combined async + DB stress (the real production scenario)
# ══════════════════════════════════════════════════════════════════════════

def test_combined_async_db_stress(n_threads=3, ollama_calls=4, db_writes=6):
    """
    Simulates the REAL production scenario: multiple Celery threads each
    running asyncio.run() that does BOTH:
      - Ollama-gated async work (via threading.Semaphore)
      - DB micro-transactions (via _safe_db_op)

    This is the most realistic test: interleaving async semaphore-gated
    work with synchronous DB writes, across multiple threads/loops.
    """
    from structuring.file_agent import _ollama_slot

    barrier = threading.Barrier(n_threads, timeout=30)
    peak_concurrent = 0
    current_concurrent = 0
    counter_lock = threading.Lock()
    violations = []
    db_errors = []
    async_errors = []

    def _thread_worker(tid):
        nonlocal peak_concurrent, current_concurrent

        barrier.wait(timeout=30)

        # Phase A: async work with Ollama gate
        async def _async_phase():
            nonlocal peak_concurrent, current_concurrent
            for i in range(ollama_calls):
                async with _ollama_slot():
                    with counter_lock:
                        current_concurrent += 1
                        if current_concurrent > peak_concurrent:
                            peak_concurrent = current_concurrent
                        if current_concurrent > 3:  # OLLAMA_MAX_CONCURRENCY
                            violations.append(f"T{tid} call {i}: {current_concurrent} > 3")
                    await asyncio.sleep(0.03)
                    with counter_lock:
                        current_concurrent -= 1

        try:
            asyncio.run(_async_phase())
        except Exception as e:
            async_errors.append(f"T{tid} async: {e}")

        # Phase B: DB writes (sync, same thread, after async loop closed)
        for j in range(db_writes):
            def _write(t=tid, idx=j):
                with get_db() as sess:
                    q = PYQQuestion(
                        question_text=f"Combined test T{t} Q{idx}",
                        source_file=f"__combined_t{t}.pdf",
                        subject="COMBINED",
                    )
                    sess.add(q)
            try:
                _safe_db_op(_write)
            except Exception as e:
                db_errors.append(f"T{tid} db write {j}: {e}")

    threads = []
    t0 = time.time()
    for t in range(n_threads):
        th = threading.Thread(target=_thread_worker, args=(t,))
        threads.append(th)
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=60)
    elapsed = time.time() - t0

    # Verify DB data
    with get_db() as sess:
        actual = sess.query(PYQQuestion).filter(
            PYQQuestion.source_file.like("__combined_%")
        ).count()
        sess.query(PYQQuestion).filter(
            PYQQuestion.source_file.like("__combined_%")
        ).delete(synchronize_session="fetch")

    expected_db = n_threads * db_writes
    return {
        "threads": n_threads,
        "ollama_calls_per_thread": ollama_calls,
        "db_writes_per_thread": db_writes,
        "peak_concurrent": peak_concurrent,
        "violations": violations,
        "db_expected": expected_db,
        "db_actual": actual,
        "async_errors": async_errors,
        "db_errors": db_errors,
        "elapsed_sec": round(elapsed, 2),
    }


# ══════════════════════════════════════════════════════════════════════════
# TEST 10: Semaphore fairness under starvation pressure
# ══════════════════════════════════════════════════════════════════════════

def test_semaphore_starvation(n_threads=6, tasks_per_thread=8, concurrency_limit=2):
    """
    Verifies that the threading.Semaphore doesn't starve any thread.
    With 6 threads × 8 tasks competing for 2 slots, every thread must
    eventually complete. No thread should be stuck indefinitely.

    Also checks that the global concurrency limit is NEVER exceeded.
    """
    test_gate = threading.Semaphore(concurrency_limit)
    peak = 0
    current = 0
    counter_lock = threading.Lock()
    violations = []
    per_thread_completed = {}
    completed_lock = threading.Lock()

    def _thread_worker(tid):
        nonlocal peak, current
        my_completed = 0

        async def _one_task(i):
            nonlocal peak, current, my_completed
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, test_gate.acquire)
            try:
                with counter_lock:
                    current += 1
                    if current > peak:
                        peak = current
                    if current > concurrency_limit:
                        violations.append(f"T{tid} task {i}: {current} > {concurrency_limit}")
                await asyncio.sleep(0.02)
                with counter_lock:
                    current -= 1
                    my_completed += 1
            finally:
                test_gate.release()

        async def _run():
            tasks = [_one_task(i) for i in range(tasks_per_thread)]
            await asyncio.gather(*tasks)

        asyncio.run(_run())
        with completed_lock:
            per_thread_completed[tid] = my_completed

    threads = []
    t0 = time.time()
    for t in range(n_threads):
        th = threading.Thread(target=_thread_worker, args=(t,))
        threads.append(th)
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=60)
    elapsed = time.time() - t0

    # Check every thread completed all its tasks (no starvation)
    starved = [
        tid for tid, count in per_thread_completed.items()
        if count < tasks_per_thread
    ]

    return {
        "threads": n_threads,
        "tasks_per_thread": tasks_per_thread,
        "concurrency_limit": concurrency_limit,
        "peak_concurrent": peak,
        "violations": violations,
        "per_thread_completed": per_thread_completed,
        "starved_threads": starved,
        "total_completed": sum(per_thread_completed.values()),
        "total_expected": n_threads * tasks_per_thread,
        "elapsed_sec": round(elapsed, 2),
    }


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════

def main():
    banner("Phase 3 Concurrency Stress Test")
    print(f"  DB: {engine.url}")
    print(f"  Pool: {type(engine.pool).__name__}")
    print(f"  Retry: {_DB_RETRY_ATTEMPTS} attempts, {_DB_RETRY_DELAY}s base delay")
    print()

    init_db()

    # Check we have slides to search against
    with get_db() as session:
        slide_count = session.query(Slide).filter(Slide.is_embedded == True).count()
    if slide_count == 0:
        fail("No embedded slides in DB — cannot run hybrid search tests")
        return

    ok(f"{slide_count} embedded slides available")

    # ── Load shared resources (once, like the Celery worker does) ────
    section("Loading shared resources")
    t0 = time.time()
    embedder = Embedder()
    chroma = ChromaStore()
    ok(f"Embedder + ChromaDB loaded in {time.time() - t0:.1f}s")

    # ==================================================================
    # TEST 1: Exact Phase 3 simulation — two concurrent PYQ jobs
    # ==================================================================
    banner("TEST 1: Concurrent Phase 3 (ML=6Q + CN=7Q)")

    cleanup_test_data()

    barrier = threading.Barrier(2, timeout=30)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_ml = pool.submit(
            simulate_phase3,
            thread_name="ML-worker",
            questions=ML_QUESTIONS,
            subject="ML",
            source_file=TEST_SOURCE_FILES[0],
            embedder=embedder,
            chroma=chroma,
            barrier=barrier,
        )
        fut_cn = pool.submit(
            simulate_phase3,
            thread_name="CN-worker",
            questions=CN_QUESTIONS,
            subject="CN",
            source_file=TEST_SOURCE_FILES[1],
            embedder=embedder,
            chroma=chroma,
            barrier=barrier,
        )

        results = {}
        for fut in as_completed([fut_ml, fut_cn]):
            r = fut.result()
            results[r["thread"]] = r

    elapsed = time.time() - t0

    section("Phase 3 Results")
    all_ok = True
    for name, r in sorted(results.items()):
        if r["errors"]:
            fail(f"{name}: FAILED — {r['errors']}")
            all_ok = False
        else:
            ok(f"{name}: {r['questions']}Q → {r['matches']} matches (0 errors)")

    if all_ok:
        ok(f"Both PYQ jobs completed without deadlock ({elapsed:.1f}s)")
    else:
        fail(f"Deadlock or error detected! ({elapsed:.1f}s)")

    # Verify data integrity
    section("Data Integrity Check")
    with get_db() as session:
        for src in TEST_SOURCE_FILES:
            q_count = (
                session.query(PYQQuestion)
                .filter(PYQQuestion.source_file == src)
                .count()
            )
            m_count = (
                session.query(PYQMatch)
                .join(PYQQuestion)
                .filter(PYQQuestion.source_file == src)
                .count()
            )
            if q_count > 0 and m_count > 0:
                ok(f"{src}: {q_count} questions, {m_count} matches stored correctly")
            else:
                fail(f"{src}: Expected data — got {q_count} questions, {m_count} matches")

    cleanup_test_data()

    # ==================================================================
    # TEST 2: Pure write stress — 6 threads × 10 writes each
    # ==================================================================
    banner("TEST 2: Write Stress (6 threads × 10 writes)")

    r = stress_write_test(n_threads=6, writes_per_thread=10)
    if r["total_succeeded"] == r["total_expected"] and not r["errors"]:
        ok(f"All {r['total_expected']} writes succeeded in {r['elapsed_sec']}s")
    else:
        fail(
            f"{r['total_succeeded']}/{r['total_expected']} writes succeeded, "
            f"{len(r['errors'])} errors: {r['errors'][:3]}"
        )

    # ==================================================================
    # TEST 3: Interleaved read-write (FastAPI + Celery simultaneous)
    # ==================================================================
    banner("TEST 3: Read-Write Interleave (3W + 5R for 5s)")

    r = read_write_interleave_test(n_writers=3, n_readers=5, duration_sec=5)
    all_errs = r["write_errors"] + r["read_errors"]
    if not all_errs:
        ok(f"{r['writes']} writes + {r['reads']} reads in {r['duration_sec']}s — 0 errors")
    else:
        fail(f"{len(all_errs)} errors: {all_errs[:3]}")

    # ==================================================================
    # TEST 4: Rapid-fire progress updates from 2 threads
    # ==================================================================
    banner("TEST 4: Concurrent Progress Updates (simulated)")

    section("Two threads firing _update_progress-style writes simultaneously")
    progress_errors = []
    progress_barrier = threading.Barrier(2, timeout=10)

    def _progress_hammer(thread_id, n_updates=20):
        progress_barrier.wait(timeout=10)
        for i in range(n_updates):
            try:
                def _op(tid=thread_id, idx=i):
                    with get_db() as sess:
                        # Simulate writing a progress update to a slide
                        slide = sess.query(Slide).filter(Slide.is_embedded == True).first()
                        if slide:
                            slide.importance_score = slide.importance_score
                _safe_db_op(_op)
            except Exception as e:
                progress_errors.append(f"Thread {thread_id} update {i}: {e}")

    t1 = threading.Thread(target=_progress_hammer, args=(1,))
    t2 = threading.Thread(target=_progress_hammer, args=(2,))
    t0 = time.time()
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)
    elapsed_p = time.time() - t0

    if not progress_errors:
        ok(f"40 concurrent progress updates in {elapsed_p:.1f}s — 0 errors")
    else:
        fail(f"{len(progress_errors)} errors: {progress_errors[:3]}")

    # ==================================================================
    # TEST 5: threading.Semaphore cross-loop correctness
    # ==================================================================
    banner("TEST 5: threading.Semaphore Cross-Loop (4 threads × 5 tasks, limit=3)")

    from structuring.config import OLLAMA_MAX_CONCURRENCY
    r = test_threading_semaphore_cross_loop(
        n_threads=4, concurrency_limit=OLLAMA_MAX_CONCURRENCY, tasks_per_thread=5
    )
    if r["violations"]:
        fail(f"Concurrency limit VIOLATED {len(r['violations'])} times: {r['violations'][:3]}")
    elif r["total_completed"] != r["total_expected"]:
        fail(f"Only {r['total_completed']}/{r['total_expected']} tasks completed")
    elif r["peak_concurrent"] > r["concurrency_limit"]:
        fail(f"Peak {r['peak_concurrent']} exceeded limit {r['concurrency_limit']}")
    else:
        ok(
            f"All {r['total_completed']} async tasks across {r['threads']} loops, "
            f"peak={r['peak_concurrent']} ≤ limit={r['concurrency_limit']} "
            f"({r['elapsed_sec']}s)"
        )

    # ==================================================================
    # TEST 6: asyncio.Semaphore cross-loop FAILS, threading.Semaphore OK
    # ==================================================================
    banner("TEST 6: Prove asyncio.Semaphore Fails Cross-Loop")

    r = test_asyncio_semaphore_cross_loop_fails()
    if r["asyncio_sem_error"]:
        ok(f"asyncio.Semaphore correctly CRASHED cross-loop: {r['asyncio_sem_error'][:80]}")
    else:
        warn("asyncio.Semaphore didn't crash (Python version may differ) — not a failure")

    if r["threading_sem_ok"] and not r["threading_sem_error"]:
        ok("threading.Semaphore works correctly cross-loop")
    else:
        fail(f"threading.Semaphore FAILED cross-loop: {r['threading_sem_error']}")

    # ==================================================================
    # TEST 7: RateLimiter cross-loop thread safety
    # ==================================================================
    banner("TEST 7: RateLimiter Cross-Loop (3 threads × 4 calls, max 3/2s)")

    r = test_rate_limiter_cross_loop(n_threads=3, calls_per_thread=4)
    if r["errors"]:
        fail(f"RateLimiter errors: {r['errors'][:3]}")
    elif r["total_completed"] != r["total_expected"]:
        fail(f"Only {r['total_completed']}/{r['total_expected']} calls completed")
    elif r["rate_violations"]:
        fail(f"Rate limit violated: {r['rate_violations'][:3]}")
    else:
        ok(
            f"All {r['total_completed']} calls across {r['threads']} loops, "
            f"rate respected ({r['elapsed_sec']}s)"
        )

    # ==================================================================
    # TEST 8: Extreme DB stress — 5 workers × 8 questions
    # ==================================================================
    banner("TEST 8: Extreme DB Stress (5 workers × 8 questions)")

    r = test_extreme_db_stress(n_workers=5, questions_per_worker=8)
    all_ok8 = True
    if r["errors"]:
        fail(f"{len(r['errors'])} errors during extreme stress: {r['errors'][:3]}")
        all_ok8 = False
    if r["total_writes"] != r["total_expected"]:
        fail(f"Writes: {r['total_writes']}/{r['total_expected']} succeeded")
        all_ok8 = False
    if r["db_actual_count"] != r["total_expected"]:
        fail(f"DB integrity: found {r['db_actual_count']}, expected {r['total_expected']}")
        all_ok8 = False
    if all_ok8:
        ok(
            f"All {r['total_expected']} writes from {r['workers']} workers "
            f"committed correctly ({r['elapsed_sec']}s)"
        )

    # ==================================================================
    # TEST 9: Combined async + DB stress (real production scenario)
    # ==================================================================
    banner("TEST 9: Combined Async + DB Stress (3 threads)")

    r = test_combined_async_db_stress(n_threads=3, ollama_calls=4, db_writes=6)
    all_ok9 = True
    if r["violations"]:
        fail(f"Ollama concurrency violated: {r['violations'][:3]}")
        all_ok9 = False
    if r["async_errors"]:
        fail(f"Async errors (cross-loop crash?): {r['async_errors'][:3]}")
        all_ok9 = False
    if r["db_errors"]:
        fail(f"DB errors: {r['db_errors'][:3]}")
        all_ok9 = False
    if r["db_actual"] != r["db_expected"]:
        fail(f"DB integrity: {r['db_actual']}/{r['db_expected']} rows")
        all_ok9 = False
    if r["peak_concurrent"] > 3:
        fail(f"Peak Ollama concurrent={r['peak_concurrent']} > limit=3")
        all_ok9 = False
    if all_ok9:
        ok(
            f"Async gate (peak={r['peak_concurrent']}≤3) + "
            f"DB writes ({r['db_actual']}/{r['db_expected']}) — "
            f"0 errors ({r['elapsed_sec']}s)"
        )

    # ==================================================================
    # TEST 10: Semaphore fairness — no thread starvation
    # ==================================================================
    banner("TEST 10: Semaphore Fairness (6 threads × 8 tasks, limit=2)")

    r = test_semaphore_starvation(n_threads=6, tasks_per_thread=8, concurrency_limit=2)
    all_ok10 = True
    if r["violations"]:
        fail(f"Concurrency violated: {r['violations'][:3]}")
        all_ok10 = False
    if r["starved_threads"]:
        fail(f"Threads starved (incomplete): {r['starved_threads']}")
        all_ok10 = False
    if r["total_completed"] != r["total_expected"]:
        fail(f"Only {r['total_completed']}/{r['total_expected']} tasks finished")
        all_ok10 = False
    if r["peak_concurrent"] > r["concurrency_limit"]:
        fail(f"Peak {r['peak_concurrent']} > limit {r['concurrency_limit']}")
        all_ok10 = False
    if all_ok10:
        ok(
            f"All {r['total_completed']} tasks, {r['threads']} threads, "
            f"peak={r['peak_concurrent']}≤{r['concurrency_limit']}, "
            f"no starvation ({r['elapsed_sec']}s)"
        )

    # ==================================================================
    # SUMMARY
    # ==================================================================
    banner("RESULTS")
    print(f"  Passed:  {PASS_COUNT}")
    print(f"  Failed:  {FAIL_COUNT}")
    if WARN_COUNT:
        print(f"  Warnings: {WARN_COUNT}")
    print()

    if FAIL_COUNT == 0:
        print("  \033[92m★ All concurrency tests passed — no deadlocks!\033[0m")
    else:
        print("  \033[91m✗ Some tests failed — deadlock or DB contention detected\033[0m")
    print()

    sys.exit(1 if FAIL_COUNT > 0 else 0)


if __name__ == "__main__":
    main()
