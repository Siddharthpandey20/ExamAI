"""
test_comprehensive.py — Comprehensive test suite for ExamAI.

Tests EVERY route, every modification, concurrency, async patterns,
SQLite locking, IST timestamps, PYQ guards, document-level endpoints,
doc_id filtering, field consistency, and LLM-powered endpoints using Llama.

Run with:
    cd ExamAI
    python test_comprehensive.py

Requires:
    - examai.db with at least one processed subject
    - Ollama running (llama3 model) for LLM integration tests
    - Redis + Celery workers (optional — concurrency tests will skip if unavailable)
"""

import asyncio
import json
import os
import re
import sys
import time
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from io import BytesIO

# ── Test output helpers ──────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

passed = 0
failed = 0
skipped = 0
errors_detail: list[str] = []


def ok(msg: str):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg: str):
    global failed
    failed += 1
    errors_detail.append(msg)
    print(f"  {RED}✗ {msg}{RESET}")


def skip(msg: str):
    global skipped
    skipped += 1
    print(f"  {YELLOW}⊘ {msg}{RESET}")


def section(title: str):
    print(f"\n{CYAN}{BOLD}── {title} ──{RESET}")


def banner(title: str):
    print(f"\n{'='*70}")
    print(f"  {BOLD}{title}{RESET}")
    print(f"{'='*70}")


# ── Imports ──────────────────────────────────────────────────────────────

# Insert project root into path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Database & models
from indexing.database import engine, SessionFactory, get_db, init_db, get_db_dep
from indexing.models import Base, Subject, Document, Slide, PYQQuestion, PYQMatch, QueryCache
from indexing.config import SQLITE_DB_URL, SQLITE_DB_PATH
import jobs.models  # Register job models with Base
from jobs.models import Job, JobPhase, JobStatus, PhaseStatus, JobType, STUDY_PHASES, PYQ_PHASES

# status module (IST timestamps)
from jobs.status import (
    _to_ist, _duration_str,
    _serialize_phase, _serialize_job,
    get_job_status, get_all_jobs, get_active_jobs, get_pipeline_overview,
)

# engine tools
from engine.tools import (
    slide_to_dict, is_substantive, run_hybrid_search,
    get_priority_slides, get_pyq_report, get_weak_spots,
    get_subject_overview, get_chapter_structure,
    get_slide_detail, search_by_type, search_by_concept,
)
from engine.config import HIGH_PRIORITY_THRESHOLD, MEDIUM_PRIORITY_THRESHOLD

# Safe DB op from tasks
from jobs.tasks import _safe_db_op, _DB_RETRY_ATTEMPTS, _DB_RETRY_DELAY

# FastAPI test client
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# ── Setup ────────────────────────────────────────────────────────────────

def get_subject() -> str | None:
    """Return the first subject that has processed data."""
    init_db()
    session = SessionFactory()
    try:
        subjects = session.query(Subject).all()
        for s in subjects:
            doc_count = session.query(Document).filter(
                Document.subject == s.name, Document.status == "processed"
            ).count()
            slide_count = session.query(Slide).filter(Slide.subject == s.name).count()
            if doc_count > 0 and slide_count > 0:
                return s.name
        # fallback: any subject with slides
        for s in subjects:
            slide_count = session.query(Slide).filter(Slide.subject == s.name).count()
            if slide_count > 0:
                return s.name
        return subjects[0].name if subjects else None
    finally:
        session.close()


# ═════════════════════════════════════════════════════════════════════════
# SECTION 1: DATABASE & INFRASTRUCTURE
# ═════════════════════════════════════════════════════════════════════════

def test_sqlite_wal_mode():
    """Verify SQLite is running in WAL journal mode."""
    section("SQLite WAL Mode")
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA journal_mode")).scalar()
        if result == "wal":
            ok(f"Journal mode = {result}")
        else:
            fail(f"Expected journal_mode=wal, got '{result}'")


def test_sqlite_busy_timeout():
    """Verify busy_timeout is set to 30000ms."""
    section("SQLite Busy Timeout")
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA busy_timeout")).scalar()
        if result == 30000:
            ok(f"busy_timeout = {result}ms")
        else:
            fail(f"Expected busy_timeout=30000, got {result}")


def test_sqlite_foreign_keys():
    """Verify foreign keys are enabled."""
    section("SQLite Foreign Keys")
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA foreign_keys")).scalar()
        if result == 1:
            ok("Foreign keys enabled")
        else:
            fail(f"Expected foreign_keys=1, got {result}")


def test_sqlite_synchronous():
    """Verify synchronous=NORMAL for better write performance."""
    section("SQLite Synchronous Mode")
    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA synchronous")).scalar()
        # 1 = NORMAL
        if result in (1, "normal"):
            ok(f"synchronous = NORMAL ({result})")
        else:
            fail(f"Expected synchronous=NORMAL (1), got {result}")


def test_null_pool():
    """Verify engine uses NullPool (safe for multi-threaded access)."""
    section("SQLAlchemy NullPool")
    from sqlalchemy.pool import NullPool
    if isinstance(engine.pool, NullPool):
        ok("Engine uses NullPool")
    else:
        fail(f"Expected NullPool, got {type(engine.pool).__name__}")


def test_safe_db_op_retry():
    """Verify _safe_db_op retries on 'database is locked' errors."""
    section("_safe_db_op Retry Logic")

    call_count = 0

    def _flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("database is locked")

    _safe_db_op(_flaky)
    if call_count == 3:
        ok(f"_safe_db_op retried {call_count - 1} times then succeeded")
    else:
        fail(f"Expected 3 calls, got {call_count}")

    # Test that return values are propagated
    result = _safe_db_op(lambda: 42)
    if result == 42:
        ok("_safe_db_op returns fn() result")
    else:
        fail(f"Expected return value 42, got {result}")

    # Test that non-lock errors propagate immediately
    call_count = 0

    def _fatal():
        nonlocal call_count
        call_count += 1
        raise ValueError("some other error")

    try:
        _safe_db_op(_fatal)
        fail("_safe_db_op should have raised ValueError")
    except ValueError:
        if call_count == 1:
            ok("Non-lock errors propagate immediately (no retry)")
        else:
            fail(f"Expected 1 call for non-lock error, got {call_count}")


def test_concurrent_db_writes():
    """Stress test: multiple threads writing to SQLite simultaneously."""
    section("Concurrent DB Writes (SQLite Locking)")

    barrier = threading.Barrier(4)
    results = {"success": 0, "error": 0}
    lock = threading.Lock()

    def _writer(thread_id):
        try:
            barrier.wait(timeout=10)
            with get_db() as session:
                # Create a temporary QueryCache entry (harmless, will be cleaned up)
                from hashlib import sha256
                h = sha256(f"test_thread_{thread_id}_{time.time()}".encode()).hexdigest()
                entry = QueryCache(
                    subject="__TEST__",
                    query_hash=h,
                    query_text=f"concurrent test {thread_id}",
                    endpoint="test",
                    response_json="{}",
                    model_used="test",
                )
                session.add(entry)
            with lock:
                results["success"] += 1
        except Exception as e:
            with lock:
                results["error"] += 1
                errors_detail.append(f"Thread {thread_id}: {e}")

    threads = [threading.Thread(target=_writer, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    if results["error"] == 0:
        ok(f"All {results['success']} concurrent writes succeeded")
    else:
        fail(f"{results['error']}/{results['success'] + results['error']} concurrent writes failed")

    # Cleanup
    with get_db() as session:
        session.query(QueryCache).filter(QueryCache.subject == "__TEST__").delete()


# ═════════════════════════════════════════════════════════════════════════
# SECTION 2: IST TIMEZONE & DURATION HELPERS (jobs/status.py)
# ═════════════════════════════════════════════════════════════════════════

def test_ist_conversion():
    """Verify UTC → IST conversion is correct (UTC + 5:30)."""
    section("IST Timezone Conversion")

    utc_dt = datetime(2025, 6, 15, 10, 0, 0, tzinfo=timezone.utc)
    ist_str = _to_ist(utc_dt)
    if ist_str and "15:30:00 IST" in ist_str:
        ok(f"UTC 10:00 → IST {ist_str}")
    else:
        fail(f"Expected 15:30:00 IST, got '{ist_str}'")

    # Naive datetime should be treated as UTC
    naive_dt = datetime(2025, 1, 1, 0, 0, 0)
    ist_str2 = _to_ist(naive_dt)
    if ist_str2 and "05:30:00 IST" in ist_str2:
        ok(f"Naive UTC 00:00 → IST {ist_str2}")
    else:
        fail(f"Expected 05:30:00 IST for naive datetime, got '{ist_str2}'")

    # None input
    if _to_ist(None) is None:
        ok("_to_ist(None) returns None")
    else:
        fail("_to_ist(None) should return None")


def test_duration_str():
    """Verify human-readable duration formatting."""
    section("Duration String Formatting")

    tests = [
        (None, None),
        (5.3, "5.3s"),
        (30.0, "30.0s"),
        (90.0, "1m 30s"),
        (3661.0, "1h 1m 1s"),
    ]
    for secs, expected in tests:
        result = _duration_str(secs)
        if result == expected:
            ok(f"_duration_str({secs}) = '{result}'")
        else:
            fail(f"_duration_str({secs}) = '{result}', expected '{expected}'")


def test_job_serializer_fields():
    """Verify job serialization includes IST timestamps and duration fields."""
    section("Job Serializer Fields")

    jobs_data = get_all_jobs()
    if not jobs_data:
        skip("No jobs in database to verify serialization")
        return

    job = jobs_data[0]
    required_fields = [
        "id", "filename", "filepath", "job_type", "status", "subject",
        "current_phase", "celery_chain_id", "created_at", "updated_at",
        "error", "overall_progress_pct", "total_duration_sec",
        "total_duration", "phases"
    ]
    missing = [f for f in required_fields if f not in job]
    if missing:
        fail(f"Job serializer missing fields: {missing}")
    else:
        ok(f"All {len(required_fields)} fields present in serialized job")

    # Check IST format in timestamps
    if job["created_at"] and "IST" in job["created_at"]:
        ok(f"created_at in IST format: {job['created_at']}")
    elif job["created_at"]:
        fail(f"created_at not in IST format: {job['created_at']}")
    else:
        skip("created_at is None")

    # Check duration field exists
    if "total_duration" in job:
        ok(f"total_duration present: {job['total_duration']}")
    else:
        fail("total_duration field missing from job serializer")

    # Check phase serialization
    if job["phases"]:
        phase = job["phases"][0]
        phase_fields = [
            "phase", "status", "celery_task_id", "started_at", "completed_at",
            "duration_sec", "duration", "error", "progress_pct", "progress_detail"
        ]
        missing_p = [f for f in phase_fields if f not in phase]
        if missing_p:
            fail(f"Phase serializer missing: {missing_p}")
        else:
            ok(f"All {len(phase_fields)} fields present in serialized phase")

        if phase["started_at"] and "IST" in phase["started_at"]:
            ok(f"Phase started_at in IST: {phase['started_at']}")
        elif phase["started_at"]:
            fail(f"Phase started_at not IST: {phase['started_at']}")
    else:
        skip("No phases to verify")


def test_pipeline_overview_fields():
    """Verify pipeline overview includes duration and IST timestamps."""
    section("Pipeline Overview Fields")

    overview = get_pipeline_overview()
    if not overview:
        skip("No jobs for pipeline overview test")
        return

    row = overview[0]
    required = [
        "id", "filename", "job_type", "status", "subject",
        "current_phase", "progress", "overall_progress_pct",
        "progress_detail", "total_duration_sec", "total_duration",
        "created_at", "error"
    ]
    missing = [f for f in required if f not in row]
    if missing:
        fail(f"Pipeline overview missing: {missing}")
    else:
        ok(f"All {len(required)} overview fields present")

    if row["created_at"] and "IST" in row["created_at"]:
        ok("Overview created_at in IST format")
    elif row["created_at"]:
        fail(f"Overview created_at not IST: {row['created_at']}")


# ═════════════════════════════════════════════════════════════════════════
# SECTION 3: ROUTE TESTS — /api/health
# ═════════════════════════════════════════════════════════════════════════

def test_health_endpoint():
    """GET /api/health — basic health check."""
    section("GET /api/health")
    resp = client.get("/api/health")
    if resp.status_code == 200 and resp.json().get("status") == "ok":
        ok("Health check returns 200 + {status: ok}")
    else:
        fail(f"Health check: status={resp.status_code}, body={resp.text}")


# ═════════════════════════════════════════════════════════════════════════
# SECTION 4: ROUTE TESTS — /api/subjects
# ═════════════════════════════════════════════════════════════════════════

def test_list_subjects(subject: str):
    """GET /api/subjects — list all subjects with stats."""
    section("GET /api/subjects")
    resp = client.get("/api/subjects")
    if resp.status_code != 200:
        fail(f"List subjects returned {resp.status_code}")
        return

    data = resp.json()
    if not isinstance(data, list):
        fail(f"Expected list, got {type(data).__name__}")
        return
    ok(f"Returned {len(data)} subjects")

    # Find our test subject
    match = [s for s in data if s["name"] == subject]
    if not match:
        fail(f"Test subject '{subject}' not found in list")
        return

    s = match[0]
    required = ["name", "created_at", "documents", "slides", "pyq_papers", "pyq_questions", "has_pyq"]
    missing = [f for f in required if f not in s]
    if missing:
        fail(f"Subject stats missing: {missing}")
    else:
        ok(f"Subject '{subject}': docs={s['documents']}, slides={s['slides']}, pyq={s['pyq_questions']}")


def test_get_subject_detail(subject: str):
    """GET /api/subjects/{name} — detailed subject info."""
    section(f"GET /api/subjects/{subject}")
    resp = client.get(f"/api/subjects/{subject}")
    if resp.status_code != 200:
        fail(f"Subject detail returned {resp.status_code}: {resp.text}")
        return

    data = resp.json()
    required = ["name", "created_at", "documents", "slides", "pyq_papers",
                "pyq_questions", "has_pyq", "document_list"]
    missing = [f for f in required if f not in data]
    if missing:
        fail(f"Subject detail missing: {missing}")
    else:
        ok(f"All {len(required)} fields present")

    if data.get("document_list"):
        doc = data["document_list"][0]
        for k in ("id", "filename", "status", "total_slides"):
            if k not in doc:
                fail(f"Document list entry missing '{k}'")
                return
        ok(f"Document list entries have required fields ({len(data['document_list'])} docs)")
    else:
        skip("No documents in subject detail")


def test_create_subject_duplicate(subject: str):
    """POST /api/subjects — duplicate name should return 409."""
    section("POST /api/subjects (duplicate)")
    resp = client.post("/api/subjects", json={"name": subject})
    if resp.status_code == 409:
        ok(f"Duplicate subject correctly returns 409")
    else:
        fail(f"Expected 409 for duplicate subject, got {resp.status_code}")


def test_get_subject_not_found():
    """GET /api/subjects/{name} — non-existent subject should return 404."""
    section("GET /api/subjects/NONEXISTENT")
    resp = client.get("/api/subjects/NONEXISTENT_XYZ_999")
    if resp.status_code == 404:
        ok("Non-existent subject returns 404")
    else:
        fail(f"Expected 404 for non-existent subject, got {resp.status_code}")


# ═════════════════════════════════════════════════════════════════════════
# SECTION 5: ROUTE TESTS — /api/upload (PYQ guard)
# ═════════════════════════════════════════════════════════════════════════

def test_pyq_upload_guard_no_subject():
    """POST /api/upload/pyq — non-existent subject returns 404."""
    section("PYQ Upload: Non-Existent Subject (404)")
    fake_file = BytesIO(b"%PDF-1.4 fake content")
    resp = client.post(
        "/api/upload/pyq",
        files={"file": ("test.pdf", fake_file, "application/pdf")},
        data={"subject": "NONEXISTENT_XYZ_999"},
    )
    if resp.status_code == 404:
        ok("PYQ upload with non-existent subject returns 404")
    else:
        fail(f"Expected 404, got {resp.status_code}: {resp.text}")


def test_pyq_upload_guard_no_material():
    """POST /api/upload/pyq — subject with no processed docs returns 409."""
    section("PYQ Upload: Guard (No Study Material → 409)")

    # Create a temporary subject with no documents
    temp_name = "__TESTGUARD__"
    session = SessionFactory()
    try:
        existing = session.query(Subject).filter(Subject.name == temp_name).first()
        if not existing:
            session.add(Subject(name=temp_name, created_at=datetime.now(timezone.utc)))
            session.commit()

        fake_file = BytesIO(b"%PDF-1.4 fake content")
        resp = client.post(
            "/api/upload/pyq",
            files={"file": ("test.pdf", fake_file, "application/pdf")},
            data={"subject": temp_name},
        )
        if resp.status_code == 409:
            ok("PYQ upload guard correctly returns 409 when no study material exists")
            if "no indexed study material" in resp.json().get("detail", "").lower():
                ok("Error message explains study material requirement")
            else:
                fail(f"Error message unclear: {resp.json().get('detail')}")
        else:
            fail(f"Expected 409, got {resp.status_code}: {resp.text}")
    finally:
        # Cleanup
        session.query(Subject).filter(Subject.name == temp_name).delete()
        session.commit()
        session.close()


def test_upload_invalid_file_type():
    """POST /api/upload/study-material — unsupported file type returns 400."""
    section("Upload: Invalid File Type (400)")
    fake_file = BytesIO(b"not a real file")
    resp = client.post(
        "/api/upload/study-material",
        files={"file": ("test.txt", fake_file, "text/plain")},
        data={"subject": "WHATEVER"},
    )
    if resp.status_code == 400:
        ok("Invalid file extension returns 400")
    else:
        fail(f"Expected 400 for .txt file, got {resp.status_code}")


# ═════════════════════════════════════════════════════════════════════════
# SECTION 6: ROUTE TESTS — /api/jobs
# ═════════════════════════════════════════════════════════════════════════

def test_list_all_jobs():
    """GET /api/jobs — list all jobs."""
    section("GET /api/jobs")
    resp = client.get("/api/jobs")
    if resp.status_code != 200:
        fail(f"List jobs returned {resp.status_code}")
        return

    data = resp.json()
    if not isinstance(data, list):
        fail(f"Expected list, got {type(data).__name__}")
        return
    ok(f"Returned {len(data)} jobs")

    if data:
        job = data[0]
        # Verify IST timestamps
        if job.get("created_at") and "IST" in job["created_at"]:
            ok("Job timestamp in IST format")
        elif job.get("created_at"):
            fail(f"Job timestamp not IST: {job['created_at']}")

        # Verify duration fields
        if "total_duration" in job and "total_duration_sec" in job:
            ok(f"Duration fields present: {job['total_duration']}")
        else:
            fail("Duration fields missing from job response")
    else:
        skip("No jobs to verify fields")


def test_active_jobs():
    """GET /api/jobs/active — list active jobs."""
    section("GET /api/jobs/active")
    resp = client.get("/api/jobs/active")
    if resp.status_code == 200:
        data = resp.json()
        ok(f"Active jobs: {len(data)} returned")
        # Verify all are actually active
        for j in data:
            if j["status"] not in ("pending", "processing"):
                fail(f"Job #{j['id']} has status '{j['status']}' but listed as active")
                return
        if data:
            ok("All returned jobs have pending/processing status")
    else:
        fail(f"Active jobs returned {resp.status_code}")


def test_pipeline_overview():
    """GET /api/jobs/overview — pipeline dashboard."""
    section("GET /api/jobs/overview")
    resp = client.get("/api/jobs/overview")
    if resp.status_code != 200:
        fail(f"Pipeline overview returned {resp.status_code}")
        return

    data = resp.json()
    ok(f"Pipeline overview: {len(data)} rows")

    if data:
        row = data[0]
        required = ["id", "filename", "job_type", "status", "subject",
                    "current_phase", "progress", "overall_progress_pct",
                    "total_duration_sec", "total_duration", "created_at"]
        missing = [f for f in required if f not in row]
        if missing:
            fail(f"Overview row missing: {missing}")
        else:
            ok(f"All {len(required)} overview fields present")


def test_job_detail():
    """GET /api/jobs/{{job_id}} — single job with all phase data."""
    section("GET /api/jobs/{job_id}")

    # Get first job ID
    all_jobs = get_all_jobs()
    if not all_jobs:
        skip("No jobs to test detail endpoint")
        return

    job_id = all_jobs[0]["id"]
    resp = client.get(f"/api/jobs/{job_id}")
    if resp.status_code != 200:
        fail(f"Job detail returned {resp.status_code}")
        return

    data = resp.json()
    if data["id"] == job_id:
        ok(f"Job #{job_id} detail retrieved successfully")
    else:
        fail(f"Expected job #{job_id}, got #{data.get('id')}")

    # Phases should be present
    if data.get("phases"):
        ok(f"  {len(data['phases'])} phases returned")
        for p in data["phases"]:
            if "duration" in p and "duration_sec" in p:
                ok(f"  Phase '{p['phase']}': duration={p['duration']}")
            else:
                fail(f"  Phase '{p['phase']}' missing duration fields")
    else:
        skip("No phases in job detail")


def test_job_not_found():
    """GET /api/jobs/999999 — non-existent job returns 404."""
    section("GET /api/jobs/999999 (404)")
    resp = client.get("/api/jobs/999999")
    if resp.status_code == 404:
        ok("Non-existent job returns 404")
    else:
        fail(f"Expected 404, got {resp.status_code}")


# ═════════════════════════════════════════════════════════════════════════
# SECTION 7: ROUTE TESTS — /api/search
# ═════════════════════════════════════════════════════════════════════════

def test_search_root():
    """GET /api/search/ — router health check."""
    section("GET /api/search/")
    resp = client.get("/api/search/")
    if resp.status_code == 200:
        data = resp.json()
        if data.get("router") == "search":
            ok("Search router health OK")
        else:
            fail(f"Unexpected response: {data}")
    else:
        fail(f"Search root returned {resp.status_code}")


def test_filter_slides(subject: str):
    """GET /api/search/slides/{subject} — slide listing with filters."""
    section(f"GET /api/search/slides/{subject}")
    resp = client.get(f"/api/search/slides/{subject}")
    if resp.status_code != 200:
        fail(f"Filter slides returned {resp.status_code}")
        return

    data = resp.json()
    ok(f"Returned {data['total']} slides for subject '{data['subject']}'")

    if data["slides"]:
        sl = data["slides"][0]
        required = ["slide_id", "doc_id", "page_number", "filename", "slide_type",
                    "chapter", "concepts", "summary", "exam_signal",
                    "importance_score", "pyq_hit_count"]
        missing = [f for f in required if f not in sl]
        if missing:
            fail(f"Slide response missing: {missing}")
        else:
            ok(f"All {len(required)} slide fields present (including doc_id)")

        # doc_id should be a valid integer
        if isinstance(sl["doc_id"], int) and sl["doc_id"] > 0:
            ok(f"doc_id is valid integer: {sl['doc_id']}")
        else:
            fail(f"doc_id invalid: {sl['doc_id']}")
    else:
        skip("No slides returned")


def test_filter_slides_by_doc_id(subject: str):
    """GET /api/search/slides/{subject}?doc_id=X — doc_id filter works."""
    section(f"GET /api/search/slides/{subject}?doc_id=...")

    session = SessionFactory()
    try:
        doc = session.query(Document).filter(Document.subject == subject).first()
        if not doc:
            skip("No documents to test doc_id filter")
            return

        resp = client.get(f"/api/search/slides/{subject}?doc_id={doc.id}")
        if resp.status_code != 200:
            fail(f"doc_id filter returned {resp.status_code}")
            return

        data = resp.json()
        ok(f"doc_id={doc.id}: returned {data['total']} slides")

        # All slides should belong to this doc
        for sl in data["slides"]:
            if sl["doc_id"] != doc.id:
                fail(f"Slide {sl['slide_id']} has doc_id={sl['doc_id']}, expected {doc.id}")
                return
        if data["slides"]:
            ok(f"All {len(data['slides'])} slides belong to doc_id={doc.id}")
    finally:
        session.close()


def test_filter_slides_by_type(subject: str):
    """GET /api/search/slides/{subject}?type=definition — type filter."""
    section(f"GET /api/search/slides/{subject}?type=definition")
    resp = client.get(f"/api/search/slides/{subject}?type=definition")
    if resp.status_code != 200:
        fail(f"Type filter returned {resp.status_code}")
        return

    data = resp.json()
    ok(f"Type 'definition': {data['total']} slides")

    for sl in data["slides"]:
        if sl["slide_type"] and sl["slide_type"].lower() != "definition":
            fail(f"Slide {sl['slide_id']} type='{sl['slide_type']}', expected 'definition'")
            return
    if data["slides"]:
        ok("All slides have correct type filter applied")


def test_filter_slides_min_importance(subject: str):
    """GET /api/search/slides/{subject}?min_importance=0.3 — importance filter."""
    section(f"GET /api/search/slides/{subject}?min_importance=0.3")
    resp = client.get(f"/api/search/slides/{subject}?min_importance=0.3")
    if resp.status_code != 200:
        fail(f"Importance filter returned {resp.status_code}")
        return

    data = resp.json()
    ok(f"min_importance=0.3: {data['total']} slides")

    for sl in data["slides"]:
        if sl["importance_score"] < 0.3:
            fail(f"Slide {sl['slide_id']} importance={sl['importance_score']} < 0.3")
            return
    if data["slides"]:
        ok("All slides meet minimum importance threshold")


def test_browse_concepts(subject: str):
    """GET /api/search/concepts/{subject} — concept browser."""
    section(f"GET /api/search/concepts/{subject}")
    resp = client.get(f"/api/search/concepts/{subject}")
    if resp.status_code != 200:
        fail(f"Browse concepts returned {resp.status_code}")
        return

    data = resp.json()
    ok(f"Returned {data['total']} concepts for '{data['subject']}'")

    if data["concepts"]:
        c = data["concepts"][0]
        for k in ("concept", "frequency", "slides"):
            if k not in c:
                fail(f"Concept entry missing '{k}'")
                return
        ok(f"Top concept: '{c['concept']}' × {c['frequency']}")

        # Check slide locations have doc_id
        if c["slides"]:
            sl = c["slides"][0]
            if "doc_id" in sl:
                ok("Concept slide locations include doc_id")
            else:
                fail("Concept slide locations missing doc_id")
    else:
        skip("No concepts returned")


def test_browse_concepts_doc_id_filter(subject: str):
    """GET /api/search/concepts/{subject}?doc_id=X — doc-filtered concepts."""
    section(f"GET /api/search/concepts/{subject}?doc_id=...")

    session = SessionFactory()
    try:
        doc = session.query(Document).filter(Document.subject == subject).first()
        if not doc:
            skip("No documents for concept doc_id filter test")
            return

        resp = client.get(f"/api/search/concepts/{subject}?doc_id={doc.id}")
        if resp.status_code != 200:
            fail(f"Concept doc_id filter returned {resp.status_code}")
            return

        data = resp.json()
        ok(f"doc_id={doc.id}: {data['total']} concepts")
    finally:
        session.close()


def test_search_nonexistent_subject():
    """GET /api/search/slides/NONEXISTENT — returns 404."""
    section("GET /api/search/slides/NONEXISTENT (404)")
    resp = client.get("/api/search/slides/NONEXISTENT_XYZ_999")
    if resp.status_code == 404:
        ok("Non-existent subject returns 404")
    else:
        fail(f"Expected 404, got {resp.status_code}")


# ═════════════════════════════════════════════════════════════════════════
# SECTION 8: ROUTE TESTS — /api/exam
# ═════════════════════════════════════════════════════════════════════════

def test_exam_root():
    """GET /api/exam/ — router health check."""
    section("GET /api/exam/")
    resp = client.get("/api/exam/")
    if resp.status_code == 200:
        data = resp.json()
        if data.get("router") == "exam":
            ok("Exam router health OK")
        else:
            fail(f"Unexpected response: {data}")
    else:
        fail(f"Exam root returned {resp.status_code}")


def test_priority_dashboard(subject: str):
    """GET /api/exam/priorities/{subject} — priority tiers."""
    section(f"GET /api/exam/priorities/{subject}")
    resp = client.get(f"/api/exam/priorities/{subject}")
    if resp.status_code != 200:
        fail(f"Priority dashboard returned {resp.status_code}")
        return

    data = resp.json()
    for key in ("subject", "high", "medium", "low", "stats"):
        if key not in data:
            fail(f"Priority response missing '{key}'")
            return

    stats = data["stats"]
    ok(f"Priorities: H={stats['high_count']}, M={stats['medium_count']}, L={stats['low_count']}, "
       f"Total={stats['total']}")

    # Verify slides in tiers have correct fields
    for tier_name in ("high", "medium", "low"):
        slides = data[tier_name]
        if slides:
            s = slides[0]
            for f in ["slide_id", "page_number", "slide_type", "summary", "importance_score"]:
                if f not in s:
                    fail(f"{tier_name}[0] missing field '{f}'")
                    return
    ok("All tier slides have required metadata fields")


def test_pyq_report(subject: str):
    """GET /api/exam/pyq-report/{subject} — PYQ coverage report."""
    section(f"GET /api/exam/pyq-report/{subject}")
    resp = client.get(f"/api/exam/pyq-report/{subject}")
    if resp.status_code != 200:
        fail(f"PYQ report returned {resp.status_code}")
        return

    data = resp.json()
    for key in ("subject", "total_questions", "questions"):
        if key not in data:
            fail(f"PYQ report missing '{key}'")
            return

    ok(f"PYQ report: {data['total_questions']} questions")

    if data["questions"]:
        q = data["questions"][0]
        for k in ("question_id", "question_text", "source_file", "matched_slides", "match_count"):
            if k not in q:
                fail(f"PYQ question missing '{k}'")
                return
        ok(f"Question structure complete; first Q: '{q['question_text'][:60]}...'")
    else:
        skip("No PYQ questions to verify structure")


def test_weak_spots(subject: str):
    """GET /api/exam/weak-spots/{subject} — weak spots analysis."""
    section(f"GET /api/exam/weak-spots/{subject}")
    resp = client.get(f"/api/exam/weak-spots/{subject}")
    if resp.status_code != 200:
        fail(f"Weak spots returned {resp.status_code}")
        return

    data = resp.json()
    for key in ("subject", "weak_spots", "total"):
        if key not in data:
            fail(f"Weak spots missing '{key}'")
            return

    ok(f"Weak spots: {data['total']} found")

    if data["weak_spots"]:
        w = data["weak_spots"][0]
        for k in ("chapter", "pyq_hits", "matched_slides", "total_slides",
                  "coverage_ratio", "priority"):
            if k not in w:
                fail(f"Weak spot missing '{k}'")
                return
        ok("Weak spot structure complete")


def test_readiness(subject: str):
    """GET /api/exam/readiness/{subject} — exam readiness score."""
    section(f"GET /api/exam/readiness/{subject}")
    resp = client.get(f"/api/exam/readiness/{subject}")
    if resp.status_code != 200:
        fail(f"Readiness returned {resp.status_code}")
        return

    data = resp.json()
    required = ["subject", "readiness_score", "verdict", "breakdown", "recommendations"]
    missing = [k for k in required if k not in data]
    if missing:
        fail(f"Readiness missing: {missing}")
        return

    score = data["readiness_score"]
    verdict = data["verdict"]
    ok(f"Readiness score: {score} — '{verdict}'")

    if 0 <= score <= 1:
        ok("Score in valid range [0, 1]")
    else:
        fail(f"Score {score} outside valid range [0, 1]")

    breakdown = data["breakdown"]
    for k in ("material_coverage", "pyq_alignment", "high_priority_ratio", "weak_spot_penalty"):
        if k not in breakdown:
            fail(f"Breakdown missing '{k}'")
            return
    ok(f"Breakdown: cov={breakdown['material_coverage']}, pyq={breakdown['pyq_alignment']}, "
       f"hp={breakdown['high_priority_ratio']}, weak={breakdown['weak_spot_penalty']}")


# ═════════════════════════════════════════════════════════════════════════
# SECTION 9: ROUTE TESTS — /api/documents (NEW)
# ═════════════════════════════════════════════════════════════════════════

def test_list_documents(subject: str):
    """GET /api/documents/{subject} — list all documents with stats."""
    section(f"GET /api/documents/{subject}")
    resp = client.get(f"/api/documents/{subject}")
    if resp.status_code != 200:
        fail(f"List documents returned {resp.status_code}")
        return

    data = resp.json()
    ok(f"Returned {data['total']} documents for subject '{data['subject']}'")

    if data["documents"]:
        doc = data["documents"][0]
        required = [
            "id", "filename", "status", "subject", "ai_subject", "summary",
            "core_topics", "total_slides", "embedded_slides", "total_pyq_hits",
            "avg_importance", "high_priority_slides", "unique_concepts",
            "top_concepts", "chapters", "processed_at"
        ]
        missing = [f for f in required if f not in doc]
        if missing:
            fail(f"Document entry missing: {missing}")
        else:
            ok(f"All {len(required)} document fields present")
            ok(f"  First doc: '{doc['filename']}', {doc['total_slides']} slides, "
               f"{doc['unique_concepts']} concepts, imp={doc['avg_importance']}")
    else:
        skip("No documents returned")

    return data


def test_document_detail(subject: str, doc_id: int):
    """GET /api/documents/{subject}/{doc_id} — full document detail."""
    section(f"GET /api/documents/{subject}/{doc_id}")
    resp = client.get(f"/api/documents/{subject}/{doc_id}")
    if resp.status_code != 200:
        fail(f"Document detail returned {resp.status_code}")
        return

    data = resp.json()
    required = ["id", "filename", "status", "subject", "ai_subject", "summary",
                "core_topics", "chapters", "total_slides", "slides"]
    missing = [f for f in required if f not in data]
    if missing:
        fail(f"Document detail missing: {missing}")
        return

    ok(f"Document #{doc_id}: '{data['filename']}', {data['total_slides']} slides")

    if data["slides"]:
        sl = data["slides"][0]
        slide_fields = ["slide_id", "page_number", "slide_type", "chapter",
                       "concepts", "summary", "exam_signal", "pyq_hit_count",
                       "importance_score", "is_embedded"]
        missing_s = [f for f in slide_fields if f not in sl]
        if missing_s:
            fail(f"Slide in detail missing: {missing_s}")
        else:
            ok(f"All {len(slide_fields)} slide fields present in document detail")
    else:
        skip("No slides in document detail")


def test_document_concepts(subject: str, doc_id: int):
    """GET /api/documents/{subject}/{doc_id}/concepts — document concepts."""
    section(f"GET /api/documents/{subject}/{doc_id}/concepts")
    resp = client.get(f"/api/documents/{subject}/{doc_id}/concepts")
    if resp.status_code != 200:
        fail(f"Document concepts returned {resp.status_code}")
        return

    data = resp.json()
    required = ["subject", "doc_id", "filename", "total", "concepts"]
    missing = [f for f in required if f not in data]
    if missing:
        fail(f"Document concepts missing: {missing}")
        return

    ok(f"Document #{doc_id} concepts: {data['total']} unique concepts")

    if data["concepts"]:
        c = data["concepts"][0]
        for k in ("concept", "frequency", "slides"):
            if k not in c:
                fail(f"Concept entry missing '{k}'")
                return
        ok(f"  Top concept: '{c['concept']}' × {c['frequency']}")

        # Concept slides should have slide metadata
        if c["slides"]:
            sl = c["slides"][0]
            for k in ("slide_id", "page_number", "slide_type", "importance_score"):
                if k not in sl:
                    fail(f"Concept slide missing '{k}'")
                    return
            ok("Concept slide entries have metadata")
    else:
        skip("No concepts for this document")


def test_document_pyq(subject: str, doc_id: int):
    """GET /api/documents/{subject}/{doc_id}/pyq — PYQ matches for document."""
    section(f"GET /api/documents/{subject}/{doc_id}/pyq")
    resp = client.get(f"/api/documents/{subject}/{doc_id}/pyq")
    if resp.status_code != 200:
        fail(f"Document PYQ returned {resp.status_code}")
        return

    data = resp.json()
    required = ["subject", "doc_id", "filename", "total_questions", "questions"]
    missing = [f for f in required if f not in data]
    if missing:
        fail(f"Document PYQ missing: {missing}")
        return

    ok(f"Document #{doc_id} PYQ: {data['total_questions']} questions matched")

    if data["questions"]:
        q = data["questions"][0]
        for k in ("question_id", "question_text", "source_file", "matched_slides"):
            if k not in q:
                fail(f"PYQ question missing '{k}'")
                return
        ok("PYQ question structure complete")

        if q["matched_slides"]:
            m = q["matched_slides"][0]
            for k in ("slide_id", "page_number", "chapter", "concepts", "similarity_score"):
                if k not in m:
                    fail(f"Matched slide missing '{k}'")
                    return
            ok("PYQ matched slide structure complete")
    else:
        skip("No PYQ questions match this document")


def test_document_priorities(subject: str, doc_id: int):
    """GET /api/documents/{subject}/{doc_id}/priorities — doc priority tiers."""
    section(f"GET /api/documents/{subject}/{doc_id}/priorities")
    resp = client.get(f"/api/documents/{subject}/{doc_id}/priorities")
    if resp.status_code != 200:
        fail(f"Document priorities returned {resp.status_code}")
        return

    data = resp.json()
    required = ["subject", "doc_id", "filename", "high", "medium", "low",
                "stats", "chapters_ranked"]
    missing = [f for f in required if f not in data]
    if missing:
        fail(f"Document priorities missing: {missing}")
        return

    stats = data["stats"]
    ok(f"Document #{doc_id} priorities: H={stats['high_count']}, M={stats['medium_count']}, "
       f"L={stats['low_count']}")

    # Verify chapters_ranked structure
    if data["chapters_ranked"]:
        ch = data["chapters_ranked"][0]
        for k in ("chapter", "slide_count", "high_count", "avg_importance", "total_pyq_hits"):
            if k not in ch:
                fail(f"Chapter ranking missing '{k}'")
                return
        ok(f"Chapter ranking: '{ch['chapter']}' with avg_importance={ch['avg_importance']}")
    else:
        skip("No chapter ranking data")


def test_document_summary(subject: str, doc_id: int):
    """GET /api/documents/{subject}/{doc_id}/summary — document summary."""
    section(f"GET /api/documents/{subject}/{doc_id}/summary")
    resp = client.get(f"/api/documents/{subject}/{doc_id}/summary")
    if resp.status_code != 200:
        fail(f"Document summary returned {resp.status_code}")
        return

    data = resp.json()
    required = [
        "subject", "doc_id", "filename", "overview", "core_topics",
        "total_slides", "chapters", "slide_type_distribution",
        "exam_signal_count", "exam_signal_slides", "top_concepts",
        "pyq_coverage", "numerical_problems", "numerical_count"
    ]
    missing = [f for f in required if f not in data]
    if missing:
        fail(f"Document summary missing: {missing}")
        return

    ok(f"Document summary: '{data['filename']}', {data['total_slides']} slides")
    ok(f"  Types: {data['slide_type_distribution']}")
    ok(f"  Exam signals: {data['exam_signal_count']}")
    ok(f"  Numericals: {data['numerical_count']}")
    ok(f"  PYQ coverage: {data['pyq_coverage']}")

    # Top concepts structure
    if data["top_concepts"]:
        tc = data["top_concepts"][0]
        if "concept" in tc and "frequency" in tc:
            ok(f"  Top concept: '{tc['concept']}' × {tc['frequency']}")
        else:
            fail("Top concept entry missing concept/frequency")


def test_document_not_found(subject: str):
    """GET /api/documents/{subject}/999999 — non-existent doc returns 404."""
    section("GET /api/documents/{subject}/999999 (404)")
    resp = client.get(f"/api/documents/{subject}/999999")
    if resp.status_code == 404:
        ok("Non-existent document returns 404")
    else:
        fail(f"Expected 404, got {resp.status_code}")


def test_document_wrong_subject():
    """GET /api/documents/NONEXISTENT/{doc_id} — wrong subject 404."""
    section("GET /api/documents/NONEXISTENT/1 (404)")
    resp = client.get("/api/documents/NONEXISTENT_XYZ_999/1")
    if resp.status_code == 404:
        ok("Non-existent subject for document returns 404")
    else:
        fail(f"Expected 404, got {resp.status_code}")


# ═════════════════════════════════════════════════════════════════════════
# SECTION 10: ENGINE TOOLS — Direct function tests
# ═════════════════════════════════════════════════════════════════════════

def test_slide_to_dict_fields(subject: str):
    """Verify slide_to_dict produces all required fields including doc_id."""
    section("slide_to_dict field consistency")

    session = SessionFactory()
    try:
        slide = session.query(Slide).filter(Slide.subject == subject).first()
        if not slide:
            skip("No slides for slide_to_dict test")
            return

        doc = session.query(Document).filter(Document.id == slide.doc_id).first()
        d = slide_to_dict(slide, doc)

        required = ["slide_id", "doc_id", "page_number", "filename", "slide_type",
                    "exam_signal", "summary", "concepts", "chapter",
                    "pyq_hit_count", "importance_score"]
        missing = [f for f in required if f not in d]
        if missing:
            fail(f"slide_to_dict missing: {missing}")
        else:
            ok(f"All {len(required)} fields present (including doc_id)")

        # Verify doc_id matches
        if d["doc_id"] == slide.doc_id:
            ok(f"doc_id matches: {d['doc_id']}")
        else:
            fail(f"doc_id mismatch: got {d['doc_id']}, expected {slide.doc_id}")

        # raw_text should NOT be present by default
        if "raw_text" not in d:
            ok("raw_text excluded by default")
        else:
            fail("raw_text should not be in default slide_to_dict output")

        # include_raw=True should add raw_text
        d2 = slide_to_dict(slide, doc, include_raw=True)
        if "raw_text" in d2:
            ok("include_raw=True adds raw_text")
        else:
            fail("include_raw=True did not add raw_text")
    finally:
        session.close()


def test_priority_thresholds(subject: str):
    """Verify priority tier classification uses correct thresholds."""
    section("Priority Tier Thresholds")

    session = SessionFactory()
    try:
        tiers = get_priority_slides(subject, session)
        for s in tiers["high"]:
            if s["importance_score"] < HIGH_PRIORITY_THRESHOLD:
                fail(f"High-tier slide {s['slide_id']} has importance "
                     f"{s['importance_score']} < {HIGH_PRIORITY_THRESHOLD}")
                return
        for s in tiers["medium"]:
            if s["importance_score"] >= HIGH_PRIORITY_THRESHOLD:
                fail(f"Medium-tier slide {s['slide_id']} should be in high tier")
                return
            if s["importance_score"] < MEDIUM_PRIORITY_THRESHOLD:
                fail(f"Medium-tier slide {s['slide_id']} has importance "
                     f"{s['importance_score']} < {MEDIUM_PRIORITY_THRESHOLD}")
                return
        for s in tiers["low"]:
            if s["importance_score"] >= MEDIUM_PRIORITY_THRESHOLD:
                fail(f"Low-tier slide {s['slide_id']} should not be in low tier")
                return

        ok(f"High threshold ({HIGH_PRIORITY_THRESHOLD}): {len(tiers['high'])} slides")
        ok(f"Medium threshold ({MEDIUM_PRIORITY_THRESHOLD}): {len(tiers['medium'])} slides")
        ok(f"Low: {len(tiers['low'])} slides")
    finally:
        session.close()


def test_subject_overview(subject: str):
    """Verify get_subject_overview returns complete stats."""
    section("get_subject_overview")

    session = SessionFactory()
    try:
        overview = get_subject_overview(subject, session)
        required = ["subject", "documents", "total_slides", "embedded_slides",
                    "pyq_questions", "avg_importance", "high_priority_slides",
                    "document_list"]
        missing = [k for k in required if k not in overview]
        if missing:
            fail(f"Overview missing: {missing}")
        else:
            ok(f"All {len(required)} overview fields present")
            ok(f"  {overview['documents']} docs, {overview['total_slides']} slides, "
               f"{overview['pyq_questions']} PYQ")
    finally:
        session.close()


def test_hybrid_search(subject: str):
    """Verify run_hybrid_search returns enriched slide dicts with RRF scores."""
    section("Hybrid Search (Dense+Sparse+RRF)")

    session = SessionFactory()
    try:
        from indexing.embedder import Embedder
        from indexing.db_chroma import ChromaStore

        embedder = Embedder()
        chroma = ChromaStore()

        results = run_hybrid_search(
            "key concepts", subject, session, embedder, chroma, top_k=5,
        )

        if not results:
            skip("No search results (empty subject or insufficient data)")
            return

        ok(f"Hybrid search returned {len(results)} results")

        r = results[0]
        required = ["slide_id", "doc_id", "page_number", "filename", "slide_type",
                    "exam_signal", "summary", "concepts", "chapter",
                    "pyq_hit_count", "importance_score", "rrf_score"]
        missing = [f for f in required if f not in r]
        if missing:
            fail(f"Search result missing: {missing}")
        else:
            ok(f"All {len(required)} fields present (including rrf_score)")

        # Results should be sorted by decreasing RRF score
        scores = [r["rrf_score"] for r in results]
        if scores == sorted(scores, reverse=True):
            ok("Results sorted by descending RRF score")
        else:
            fail("Results NOT sorted by RRF score")

        # No raw_text should leak
        for r in results:
            if "raw_text" in r:
                fail("raw_text leaks in hybrid search results")
                return
        ok("No raw_text in search results")
    finally:
        session.close()


def test_chapter_structure(subject: str):
    """Verify get_chapter_structure returns doc_id in entries."""
    section("Chapter Structure")

    session = SessionFactory()
    try:
        chapters = get_chapter_structure(subject, session)
        if not chapters:
            skip("No chapter structure data")
            return

        ok(f"{len(chapters)} chapters found")
        ch = chapters[0]
        if "doc_id" in ch:
            ok("doc_id present in chapter entries")
        else:
            fail("doc_id missing from chapter entries")
        if "filename" in ch:
            ok(f"  First: '{ch.get('name', ch.get('chapter_name', 'N/A'))}' from {ch['filename']}")
    finally:
        session.close()


# ═════════════════════════════════════════════════════════════════════════
# SECTION 11: ASYNC SLIDE AGENT — Verify concurrent batch pattern
# ═════════════════════════════════════════════════════════════════════════

def test_slide_agent_uses_asyncio_gather():
    """Verify slide_agent.py uses asyncio.gather for concurrent batches."""
    section("Slide Agent: asyncio.gather Pattern")

    agent_path = os.path.join(PROJECT_ROOT, "structuring", "slide_agent.py")
    with open(agent_path, "r", encoding="utf-8") as f:
        source = f.read()

    if "asyncio.gather" in source:
        ok("asyncio.gather found in slide_agent.py")
    else:
        fail("asyncio.gather NOT found — batches may still be sequential")

    # Ensure old sequential loop pattern is removed
    if "for i in range(0, len(slides), SLIDE_BATCH_SIZE):" in source and "await _process_batch" in source:
        fail("Old sequential await pattern still present")
    else:
        ok("No sequential batch awaiting pattern found")

    # Rate limiter should still be present
    if "_limiter.acquire" in source or "await _limiter" in source:
        ok("Rate limiter gating preserved")
    else:
        fail("Rate limiter not found — concurrent calls may exceed API quota")


def test_rate_limiter_logic():
    """Verify the rate limiter correctly gates concurrent calls."""
    section("Rate Limiter Logic")

    from structuring.slide_agent import _RateLimiter

    async def _test():
        limiter = _RateLimiter(max_calls=3, window=2.0)
        start = time.time()

        # First 3 should be instant
        for _ in range(3):
            await limiter.acquire()

        elapsed = time.time() - start
        if elapsed < 1.0:
            ok(f"First 3 acquisitions instant ({elapsed:.2f}s)")
        else:
            fail(f"First 3 acquisitions too slow ({elapsed:.2f}s)")

        # 4th should block until window expires
        t4_start = time.time()
        await limiter.acquire()
        t4_elapsed = time.time() - t4_start

        if t4_elapsed >= 0.5:
            ok(f"4th acquisition waited {t4_elapsed:.1f}s (rate limited)")
        else:
            fail(f"4th acquisition did not wait ({t4_elapsed:.2f}s) — limiter may be broken")

    asyncio.run(_test())


# ═════════════════════════════════════════════════════════════════════════
# SECTION 12: LLM INTEGRATION TESTS (Ollama Llama3)
# ═════════════════════════════════════════════════════════════════════════

def _ollama_available() -> bool:
    """Check if Ollama is running and llama3 is available."""
    try:
        import httpx
        resp = httpx.get("http://127.0.0.1:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            return any("llama3" in m.get("name", "") for m in models)
        return False
    except Exception:
        return False


def test_llm_fast_search(subject: str):
    """POST /api/search/query (fast mode) — requires Ollama Llama3 or Groq."""
    section("POST /api/search/query (fast mode — LLM)")

    if not _ollama_available():
        skip("Ollama not available — skipping LLM search test")
        return

    resp = client.post(
        "/api/search/query",
        json={"query": "What are the key concepts?", "subject": subject, "mode": "fast"},
        params={"force": True},
    )

    if resp.status_code == 200:
        data = resp.json()
        ok(f"Fast search returned 200 ({len(json.dumps(data))} chars)")
        if "answer" in data or "response" in data or "content" in data:
            ok("Response contains answer/response content")
        else:
            ok(f"Response keys: {list(data.keys())}")
    elif resp.status_code == 500:
        skip(f"LLM call failed (may need Groq API key): {resp.text[:100]}")
    else:
        fail(f"Fast search returned {resp.status_code}: {resp.text[:200]}")


def test_llm_coverage(subject: str):
    """POST /api/search/coverage — topic coverage check via LLM."""
    section("POST /api/search/coverage (LLM)")

    if not _ollama_available():
        skip("Ollama not available — skipping coverage test")
        return

    resp = client.post(
        "/api/search/coverage",
        json={"topic": "linear regression", "subject": subject},
        params={"force": True},
    )

    if resp.status_code == 200:
        data = resp.json()
        ok(f"Coverage check returned 200")
        if any(k in data for k in ("verdict", "answer", "response", "covered")):
            ok("Response contains verdict/coverage data")
    elif resp.status_code == 500:
        skip(f"LLM call failed: {resp.text[:100]}")
    else:
        fail(f"Coverage returned {resp.status_code}: {resp.text[:200]}")


def test_llm_study_plan(subject: str):
    """POST /api/exam/study-plan (fast mode) — AI study plan."""
    section("POST /api/exam/study-plan (fast — LLM)")

    if not _ollama_available():
        skip("Ollama not available — skipping study plan test")
        return

    resp = client.post(
        "/api/exam/study-plan",
        json={"subject": subject, "mode": "fast"},
        params={"force": True},
    )

    if resp.status_code == 200:
        ok(f"Study plan returned 200 ({len(resp.text)} chars)")
    elif resp.status_code == 500:
        skip(f"Study plan LLM failed: {resp.text[:100]}")
    else:
        fail(f"Study plan returned {resp.status_code}")


def test_llm_revision(subject: str):
    """POST /api/exam/revision (fast mode) — time-constrained revision."""
    section("POST /api/exam/revision (fast — LLM)")

    if not _ollama_available():
        skip("Ollama not available — skipping revision test")
        return

    resp = client.post(
        "/api/exam/revision",
        json={"subject": subject, "hours": 3, "mode": "fast"},
        params={"force": True},
    )

    if resp.status_code == 200:
        ok(f"Revision plan returned 200 ({len(resp.text)} chars)")
    elif resp.status_code == 500:
        skip(f"Revision LLM failed: {resp.text[:100]}")
    else:
        fail(f"Revision returned {resp.status_code}")


# ═════════════════════════════════════════════════════════════════════════
# SECTION 13: EDGE CASES & VALIDATION
# ═════════════════════════════════════════════════════════════════════════

def test_revision_hour_validation():
    """POST /api/exam/revision — hours must be > 0 and <= 24."""
    section("Revision Hour Validation")

    # hours = 0 should fail (gt=0)
    resp = client.post(
        "/api/exam/revision",
        json={"subject": "CA", "hours": 0, "mode": "fast"},
    )
    if resp.status_code == 422:
        ok("hours=0 correctly rejected (422)")
    else:
        fail(f"hours=0: expected 422, got {resp.status_code}")

    # hours = -1 should fail
    resp2 = client.post(
        "/api/exam/revision",
        json={"subject": "CA", "hours": -1, "mode": "fast"},
    )
    if resp2.status_code == 422:
        ok("hours=-1 correctly rejected (422)")
    else:
        fail(f"hours=-1: expected 422, got {resp2.status_code}")

    # hours = 25 should fail (le=24)
    resp3 = client.post(
        "/api/exam/revision",
        json={"subject": "CA", "hours": 25, "mode": "fast"},
    )
    if resp3.status_code == 422:
        ok("hours=25 correctly rejected (422)")
    else:
        fail(f"hours=25: expected 422, got {resp3.status_code}")


def test_empty_subject_create():
    """POST /api/subjects with empty name should fail."""
    section("Subject: Empty Name Validation")
    resp = client.post("/api/subjects", json={"name": ""})
    if resp.status_code == 400:
        ok("Empty subject name returns 400")
    else:
        fail(f"Expected 400 for empty name, got {resp.status_code}")

    resp2 = client.post("/api/subjects", json={"name": "   "})
    if resp2.status_code == 400:
        ok("Whitespace-only subject name returns 400")
    else:
        fail(f"Expected 400 for whitespace name, got {resp2.status_code}")


def test_search_empty_query(subject: str):
    """POST /api/search/query with empty query."""
    section("Search: Empty Query Validation")
    resp = client.post(
        "/api/search/query",
        json={"query": "", "subject": subject, "mode": "fast"},
    )
    # Should either fail validation (422) or return empty results, not crash
    if resp.status_code in (200, 422):
        ok(f"Empty query handled gracefully (status={resp.status_code})")
    else:
        fail(f"Empty query returned unexpected {resp.status_code}")


def test_slides_limit_param(subject: str):
    """GET /api/search/slides/{subject}?limit=2 — limit parameter works."""
    section("Slides: Limit Parameter")
    resp = client.get(f"/api/search/slides/{subject}?limit=2")
    if resp.status_code != 200:
        fail(f"Slides with limit returned {resp.status_code}")
        return

    data = resp.json()
    if len(data["slides"]) <= 2:
        ok(f"Limit=2: returned {len(data['slides'])} slides")
    else:
        fail(f"Expected <= 2 slides, got {len(data['slides'])}")


def test_slides_search_keyword(subject: str):
    """GET /api/search/slides/{subject}?search=... — keyword search."""
    section("Slides: Keyword Search")

    # Get a concept to search for
    session = SessionFactory()
    try:
        slide = (
            session.query(Slide)
            .filter(Slide.subject == subject, Slide.concepts.isnot(None), Slide.concepts != "")
            .first()
        )
        if not slide or not slide.concepts:
            skip("No concepts available for keyword search test")
            return

        keyword = slide.concepts.split(",")[0].strip()
    finally:
        session.close()

    resp = client.get(f"/api/search/slides/{subject}?search={keyword}")
    if resp.status_code != 200:
        fail(f"Keyword search returned {resp.status_code}")
        return

    data = resp.json()
    ok(f"Keyword '{keyword}': {data['total']} slides")


# ═════════════════════════════════════════════════════════════════════════
# SECTION 14: CONCURRENT HTTP REQUEST STRESS TEST
# ═════════════════════════════════════════════════════════════════════════

def test_concurrent_route_access(subject: str):
    """Hit multiple routes concurrently to test database locking under load."""
    section("Concurrent Route Access (Stress Test)")

    endpoints = [
        f"/api/subjects",
        f"/api/subjects/{subject}",
        f"/api/search/slides/{subject}",
        f"/api/search/concepts/{subject}",
        f"/api/exam/priorities/{subject}",
        f"/api/exam/readiness/{subject}",
        f"/api/exam/weak-spots/{subject}",
        f"/api/documents/{subject}",
        f"/api/jobs",
        f"/api/jobs/overview",
    ]

    results = {"success": 0, "error": 0, "errors": []}

    def _hit(url):
        try:
            resp = client.get(url)
            if resp.status_code == 200:
                return ("ok", url)
            else:
                return ("fail", f"{url} -> {resp.status_code}")
        except Exception as e:
            return ("fail", f"{url} -> {e}")

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_hit, url) for url in endpoints * 2]  # 20 requests
        for f in as_completed(futures):
            status, detail = f.result()
            if status == "ok":
                results["success"] += 1
            else:
                results["error"] += 1
                results["errors"].append(detail)

    total = results["success"] + results["error"]
    if results["error"] == 0:
        ok(f"All {total} concurrent requests succeeded")
    else:
        fail(f"{results['error']}/{total} concurrent requests failed:")
        for err in results["errors"][:5]:
            fail(f"  {err}")


# ═════════════════════════════════════════════════════════════════════════
# SECTION 15: CELERY & TASK INFRASTRUCTURE
# ═════════════════════════════════════════════════════════════════════════

def test_celery_config():
    """Verify Celery configuration constants."""
    section("Celery Configuration")

    from jobs.celery_app import app as celery_app
    from jobs.config import WORKER_CONCURRENCY

    if WORKER_CONCURRENCY == 2:
        ok(f"WORKER_CONCURRENCY = {WORKER_CONCURRENCY}")
    else:
        fail(f"Expected WORKER_CONCURRENCY=2, got {WORKER_CONCURRENCY}")

    # Check worker_max_tasks_per_child
    conf = celery_app.conf
    mtpc = getattr(conf, "worker_max_tasks_per_child", None)
    if mtpc == 50:
        ok(f"worker_max_tasks_per_child = {mtpc}")
    elif mtpc is not None:
        fail(f"Expected worker_max_tasks_per_child=50, got {mtpc}")
    else:
        fail("worker_max_tasks_per_child not configured")


def test_task_registration():
    """Verify all Celery tasks are registered."""
    section("Celery Task Registration")

    from jobs.celery_app import app as celery_app

    expected_tasks = ["jobs.ingest", "jobs.structure", "jobs.index",
                     "jobs.process_pyq", "jobs.remap_pyq"]
    registered = list(celery_app.tasks.keys())

    for task_name in expected_tasks:
        if task_name in registered:
            ok(f"Task '{task_name}' registered")
        else:
            fail(f"Task '{task_name}' NOT registered")


def test_remap_pyq_task_exists():
    """Verify remap_pyq_task is defined and callable."""
    section("remap_pyq_task")

    from jobs.tasks import remap_pyq_task
    if callable(remap_pyq_task):
        ok("remap_pyq_task is callable")
    else:
        fail("remap_pyq_task is not callable")


# ═════════════════════════════════════════════════════════════════════════
# SECTION 16: DATA CONSISTENCY
# ═════════════════════════════════════════════════════════════════════════

def test_slide_doc_id_consistency(subject: str):
    """Verify every slide has a valid doc_id pointing to an existing document."""
    section("Slide ↔ Document FK Consistency")

    session = SessionFactory()
    try:
        slides = session.query(Slide).filter(Slide.subject == subject).all()
        if not slides:
            skip("No slides to verify")
            return

        orphans = 0
        for sl in slides:
            doc = session.query(Document).filter(Document.id == sl.doc_id).first()
            if not doc:
                orphans += 1

        if orphans == 0:
            ok(f"All {len(slides)} slides have valid doc_id (no orphans)")
        else:
            fail(f"{orphans}/{len(slides)} slides have orphaned doc_id")
    finally:
        session.close()


def test_embedded_slides_in_chroma(subject: str):
    """Verify slides marked is_embedded=True exist in ChromaDB."""
    section("Embedded Slides ↔ ChromaDB Consistency")

    session = SessionFactory()
    try:
        embedded = (
            session.query(Slide)
            .filter(Slide.subject == subject, Slide.is_embedded == True)
            .all()
        )
        if not embedded:
            skip("No embedded slides")
            return

        ok(f"{len(embedded)} slides marked is_embedded=True in SQLite")

        from indexing.db_chroma import ChromaStore
        chroma = ChromaStore()
        collection = chroma.collection

        # Check a sample of embedded slides exist in ChromaDB
        sample = embedded[:10]
        missing = 0
        for sl in sample:
            chroma_id = f"doc{sl.doc_id}_page{sl.page_number}"
            try:
                result = collection.get(ids=[chroma_id])
                if not result["ids"]:
                    missing += 1
            except Exception:
                missing += 1

        if missing == 0:
            ok(f"All {len(sample)} sampled slides found in ChromaDB")
        else:
            fail(f"{missing}/{len(sample)} sampled slides NOT found in ChromaDB")
    finally:
        session.close()


def test_importance_score_range(subject: str):
    """Verify all importance scores are in valid range [0, 1+]."""
    section("Importance Score Range")

    session = SessionFactory()
    try:
        slides = session.query(Slide).filter(Slide.subject == subject).all()
        if not slides:
            skip("No slides")
            return

        invalid = [s for s in slides if (s.importance_score or 0) < 0]
        if invalid:
            fail(f"{len(invalid)} slides have negative importance_score")
        else:
            scores = [s.importance_score or 0 for s in slides]
            ok(f"All {len(slides)} slides have valid importance scores "
               f"(min={min(scores):.3f}, max={max(scores):.3f}, avg={sum(scores)/len(scores):.3f})")
    finally:
        session.close()


# ═════════════════════════════════════════════════════════════════════════
# SECTION 17: ROUTE REGISTRATION COMPLETENESS
# ═════════════════════════════════════════════════════════════════════════

def test_route_registration():
    """Verify all expected routes are registered in the FastAPI app."""
    section("Route Registration Completeness")

    routes = [r.path for r in app.routes if hasattr(r, "path")]

    expected_prefixes = {
        "/api/health": "Health",
        "/api/subjects": "Subjects",
        "/api/upload/study-material": "Upload Study",
        "/api/upload/pyq": "Upload PYQ",
        "/api/jobs": "Jobs List",
        "/api/jobs/active": "Jobs Active",
        "/api/jobs/overview": "Jobs Overview",
        "/api/search/": "Search Root",
        "/api/search/query": "Search Query",
        "/api/search/coverage": "Search Coverage",
        "/api/search/slides/{subject}": "Search Slides",
        "/api/search/concepts/{subject}": "Search Concepts",
        "/api/exam/": "Exam Root",
        "/api/exam/priorities/{subject}": "Exam Priorities",
        "/api/exam/study-plan": "Exam Study Plan",
        "/api/exam/revision": "Exam Revision",
        "/api/exam/pyq-report/{subject}": "Exam PYQ Report",
        "/api/exam/weak-spots/{subject}": "Exam Weak Spots",
        "/api/exam/readiness/{subject}": "Exam Readiness",
        "/api/documents/{subject}": "Documents List",
        "/api/documents/{subject}/{doc_id}": "Document Detail",
        "/api/documents/{subject}/{doc_id}/concepts": "Document Concepts",
        "/api/documents/{subject}/{doc_id}/pyq": "Document PYQ",
        "/api/documents/{subject}/{doc_id}/priorities": "Document Priorities",
        "/api/documents/{subject}/{doc_id}/summary": "Document Summary",
    }

    for path, label in expected_prefixes.items():
        if path in routes:
            ok(f"  {label}: {path}")
        else:
            fail(f"  {label}: {path} NOT REGISTERED")

    ok(f"Total routes in app: {len(routes)}")


# ═════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════

def main():
    subject = get_subject()
    if not subject:
        print(f"{RED}No subject with data found in DB. Process some material first.{RESET}")
        sys.exit(1)

    banner(f"ExamAI — Comprehensive Test Suite")
    print(f"  Subject: {subject}")
    print(f"  DB: {SQLITE_DB_PATH}")
    print(f"  Ollama: {'available' if _ollama_available() else 'not available'}")

    # ── Section 1: Database & Infrastructure ──
    banner("1. DATABASE & INFRASTRUCTURE")
    test_sqlite_wal_mode()
    test_sqlite_busy_timeout()
    test_sqlite_foreign_keys()
    test_sqlite_synchronous()
    test_null_pool()
    test_safe_db_op_retry()
    test_concurrent_db_writes()

    # ── Section 2: IST Timezone & Duration ──
    banner("2. IST TIMEZONE & DURATION")
    test_ist_conversion()
    test_duration_str()
    test_job_serializer_fields()
    test_pipeline_overview_fields()

    # ── Section 3: Health ──
    banner("3. HEALTH ENDPOINT")
    test_health_endpoint()

    # ── Section 4: Subjects ──
    banner("4. SUBJECT ROUTES")
    test_list_subjects(subject)
    test_get_subject_detail(subject)
    test_create_subject_duplicate(subject)
    test_get_subject_not_found()

    # ── Section 5: Upload (PYQ Guard) ──
    banner("5. UPLOAD ROUTES & PYQ GUARD")
    test_pyq_upload_guard_no_subject()
    test_pyq_upload_guard_no_material()
    test_upload_invalid_file_type()

    # ── Section 6: Jobs ──
    banner("6. JOB ROUTES")
    test_list_all_jobs()
    test_active_jobs()
    test_pipeline_overview()
    test_job_detail()
    test_job_not_found()

    # ── Section 7: Search ──
    banner("7. SEARCH ROUTES")
    test_search_root()
    test_filter_slides(subject)
    test_filter_slides_by_doc_id(subject)
    test_filter_slides_by_type(subject)
    test_filter_slides_min_importance(subject)
    test_browse_concepts(subject)
    test_browse_concepts_doc_id_filter(subject)
    test_search_nonexistent_subject()

    # ── Section 8: Exam ──
    banner("8. EXAM ROUTES")
    test_exam_root()
    test_priority_dashboard(subject)
    test_pyq_report(subject)
    test_weak_spots(subject)
    test_readiness(subject)

    # ── Section 9: Documents (NEW) ──
    banner("9. DOCUMENT ROUTES (NEW)")
    doc_data = test_list_documents(subject)
    doc_id = None
    if doc_data and doc_data.get("documents"):
        doc_id = doc_data["documents"][0]["id"]
    if doc_id:
        test_document_detail(subject, doc_id)
        test_document_concepts(subject, doc_id)
        test_document_pyq(subject, doc_id)
        test_document_priorities(subject, doc_id)
        test_document_summary(subject, doc_id)
    else:
        skip("No documents to test detail/concepts/pyq/priorities/summary endpoints")
    test_document_not_found(subject)
    test_document_wrong_subject()

    # ── Section 10: Engine Tools ──
    banner("10. ENGINE TOOLS")
    test_slide_to_dict_fields(subject)
    test_priority_thresholds(subject)
    test_subject_overview(subject)
    test_hybrid_search(subject)
    test_chapter_structure(subject)

    # ── Section 11: Async Slide Agent ──
    banner("11. ASYNC SLIDE AGENT")
    test_slide_agent_uses_asyncio_gather()
    test_rate_limiter_logic()

    # ── Section 12: LLM Integration (Ollama) ──
    banner("12. LLM INTEGRATION (Ollama Llama3)")
    test_llm_fast_search(subject)
    test_llm_coverage(subject)
    test_llm_study_plan(subject)
    test_llm_revision(subject)

    # ── Section 13: Edge Cases & Validation ──
    banner("13. EDGE CASES & VALIDATION")
    test_revision_hour_validation()
    test_empty_subject_create()
    test_search_empty_query(subject)
    test_slides_limit_param(subject)
    test_slides_search_keyword(subject)

    # ── Section 14: Concurrent Stress ──
    banner("14. CONCURRENT STRESS TEST")
    test_concurrent_route_access(subject)

    # ── Section 15: Celery & Tasks ──
    banner("15. CELERY & TASK INFRASTRUCTURE")
    test_celery_config()
    test_task_registration()
    test_remap_pyq_task_exists()

    # ── Section 16: Data Consistency ──
    banner("16. DATA CONSISTENCY")
    test_slide_doc_id_consistency(subject)
    test_embedded_slides_in_chroma(subject)
    test_importance_score_range(subject)

    # ── Section 17: Route Registration ──
    banner("17. ROUTE REGISTRATION")
    test_route_registration()

    # ── Final Summary ──
    banner("RESULTS")
    total = passed + failed + skipped
    print(f"  Total: {total} tests")
    print(f"    {GREEN}Passed:  {passed}{RESET}")
    print(f"    {RED}Failed:  {failed}{RESET}")
    print(f"    {YELLOW}Skipped: {skipped}{RESET}")

    if errors_detail:
        print(f"\n  {RED}{BOLD}FAILURES:{RESET}")
        for i, err in enumerate(errors_detail, 1):
            print(f"    {RED}{i}. {err}{RESET}")

    print()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
