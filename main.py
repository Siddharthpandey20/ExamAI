"""
main.py — FastAPI application entry point for ExamPrep AI.

Run with:
    fastapi dev main.py
    # or
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from indexing.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    # Startup — ensure DB tables exist (including new Subject table)
    import jobs.models  # noqa: F401 — register job models with Base
    init_db()
    log.info("Database initialized")
    yield
    # Shutdown — nothing to clean up


app = FastAPI(
    title="ExamPrep AI",
    description="Agentic system for converting chaotic study material into exam-optimized knowledge.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow all origins during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────────────
from routes.subjects import router as subjects_router
from routes.uploads import router as uploads_router
from routes.jobs import router as jobs_router
from routes.search import router as search_router
from routes.exam import router as exam_router
from routes.documents import router as documents_router

app.include_router(subjects_router, prefix="/api/subjects", tags=["Subjects"])
app.include_router(uploads_router, prefix="/api/upload", tags=["Upload"])
app.include_router(jobs_router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(search_router, prefix="/api/search", tags=["Search"])
app.include_router(exam_router, prefix="/api/exam", tags=["Exam Intelligence"])
app.include_router(documents_router, prefix="/api/documents", tags=["Documents"])

@app.get("/api/health")
def health_check():
    return {"status": "ok"}
