"""
routes/jobs.py — Job status endpoints + SSE streaming.

GET  /api/jobs                  — list all jobs
GET  /api/jobs/active           — list active (pending/processing) jobs
GET  /api/jobs/overview         — pipeline dashboard view
GET  /api/jobs/{job_id}         — single job detail
GET  /api/jobs/{job_id}/stream  — SSE stream for real-time status updates
"""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from jobs.status import (
    get_job_status,
    get_all_jobs,
    get_active_jobs,
    get_pipeline_overview,
)

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("")
def list_jobs():
    """List all jobs, newest first."""
    return get_all_jobs()


@router.get("/active")
def list_active_jobs():
    """List only pending or processing jobs."""
    return get_active_jobs()


@router.get("/overview")
def pipeline_overview():
    """Flat dashboard: one row per file with status and progress."""
    return get_pipeline_overview()


@router.get("/{job_id}")
def job_detail(job_id: int):
    """Get detailed status of a single job including all phase details."""
    status = get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job #{job_id} not found.")
    return status


@router.get("/{job_id}/stream")
async def job_stream(job_id: int):
    """
    Server-Sent Events (SSE) stream for real-time job status updates.

    The client connects and receives status updates every 2 seconds.
    The stream ends when the job reaches a terminal state (completed/failed).

    Usage (JavaScript):
        const es = new EventSource("/api/jobs/123/stream");
        es.onmessage = (e) => { console.log(JSON.parse(e.data)); };
        es.addEventListener("complete", () => es.close());
    """
    # Verify job exists
    status = get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Job #{job_id} not found.")

    async def event_generator():
        """Yield SSE events until job reaches terminal state."""
        last_data = None

        while True:
            current = get_job_status(job_id)
            if not current:
                yield _sse_event({"error": "Job not found"}, event="error")
                break

            # Only send if data changed
            current_json = json.dumps(current, sort_keys=True)
            if current_json != last_data:
                last_data = current_json
                yield _sse_event(current, event="status")

            # Terminal states — send final event and close
            if current["status"] in ("completed", "failed"):
                yield _sse_event(current, event="complete")
                break

            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(data: dict, event: str = "message") -> str:
    """Format a dict as an SSE event string."""
    payload = json.dumps(data)
    return f"event: {event}\ndata: {payload}\n\n"
