"""
__main__.py — CLI entry point for the jobs module.

Usage:
    python -m jobs worker   [--concurrency=N] [--pool=threads|solo]
    python -m jobs submit   [--pyq] <file1> [file2] ...
    python -m jobs status   [job_id]
    python -m jobs overview
"""

import sys
import os
import subprocess
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)


# ── Commands ─────────────────────────────────────────────────────────────

def _cmd_worker(args):
    """Start the Celery worker process."""
    from jobs.config import WORKER_CONCURRENCY, WORKER_POOL

    concurrency = WORKER_CONCURRENCY
    pool = WORKER_POOL

    for arg in args:
        if arg.startswith("--concurrency="):
            concurrency = int(arg.split("=", 1)[1])
        elif arg.startswith("--pool="):
            pool = arg.split("=", 1)[1]

    cmd = [
        sys.executable, "-m", "celery",
        "-A", "jobs.celery_app",
        "worker",
        f"--pool={pool}",
        f"--concurrency={concurrency}",
        "--loglevel=info",
    ]

    print(f"Starting Celery worker (pool={pool}, concurrency={concurrency})...")
    print(f"  Command: {' '.join(cmd)}")
    print(f"  Press Ctrl+C to stop.\n")

    subprocess.run(cmd)


def _cmd_submit(args):
    """Submit files for background processing."""
    from jobs import submit_study_materials, submit_pyq_files

    is_pyq = "--pyq" in args
    filepaths = [a for a in args if not a.startswith("--")]

    if not filepaths:
        print("Usage: python -m jobs submit [--pyq] <file1> [file2] ...")
        return

    filepaths = [os.path.abspath(f) for f in filepaths]

    valid = []
    for fp in filepaths:
        if os.path.isfile(fp):
            valid.append(fp)
        else:
            print(f"  [WARN] File not found: {fp}")

    if not valid:
        print("No valid files to submit.")
        return

    if is_pyq:
        job_ids = submit_pyq_files(valid)
    else:
        job_ids = submit_study_materials(valid)

    kind = "PYQ" if is_pyq else "study material"
    print(f"\nSubmitted {len(job_ids)} {kind} job(s):")
    for jid in job_ids:
        print(f"  Job #{jid}")
    print("\nUse 'python -m jobs status' to track progress.")


def _cmd_status(args):
    """Show job status (all jobs or specific job detail)."""
    from jobs.status import get_job_status, get_all_jobs

    if args and args[0].isdigit():
        job_id = int(args[0])
        status = get_job_status(job_id)
        if not status:
            print(f"Job #{job_id} not found.")
            return
        _print_job_detail(status)
    else:
        jobs = get_all_jobs()
        if not jobs:
            print("No jobs found.")
            return
        _print_jobs_table(jobs)


def _cmd_overview(args):
    """Show pipeline progress dashboard."""
    from jobs.status import get_pipeline_overview

    overview = get_pipeline_overview()
    if not overview:
        print("No jobs found.")
        return

    print(f"\n{'ID':<5} {'Filename':<35} {'Type':<16} {'Status':<12} {'Phase':<15} {'Progress'}")
    print("-" * 95)
    for row in overview:
        print(
            f"{row['id']:<5} "
            f"{row['filename']:<35} "
            f"{row['job_type']:<16} "
            f"{row['status']:<12} "
            f"{(row['current_phase'] or '-'):<15} "
            f"{row['progress']}"
        )
    print()


# ── Display helpers ──────────────────────────────────────────────────────

def _print_jobs_table(jobs):
    """Summary table of all jobs."""
    print(f"\n{'ID':<5} {'Filename':<35} {'Type':<16} {'Status':<12} {'Phase':<15} {'Created'}")
    print("-" * 100)
    for j in jobs:
        created = j["created_at"][:19] if j["created_at"] else "-"
        print(
            f"{j['id']:<5} "
            f"{j['filename']:<35} "
            f"{j['job_type']:<16} "
            f"{j['status']:<12} "
            f"{(j['current_phase'] or '-'):<15} "
            f"{created}"
        )
    print(f"\nTotal: {len(jobs)} job(s)")


def _print_job_detail(job):
    """Detailed status of a single job."""
    print(f"\nJob #{job['id']}: {job['filename']}")
    print(f"  Type:    {job['job_type']}")
    print(f"  Status:  {job['status']}")
    print(f"  Created: {job['created_at']}")
    print(f"  Updated: {job['updated_at']}")
    if job["error"]:
        print(f"  Error:   {job['error']}")

    print(f"\n  Phases:")
    for p in job["phases"]:
        icon = {
            "pending": "[ ]",
            "running": "[~]",
            "completed": "[+]",
            "skipped": "[>]",
            "failed": "[X]",
        }.get(p["status"], "[?]")

        duration = f" ({p['duration_sec']}s)" if p.get("duration_sec") else ""
        error = f" -- {p['error']}" if p.get("error") else ""

        print(f"    {icon} {p['phase']:<15} {p['status']:<12}{duration}{error}")
    print()


# ── Entry point ──────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("ExamAI Job Manager")
        print()
        print("Commands:")
        print("  python -m jobs worker   [--concurrency=N] [--pool=threads|solo]")
        print("  python -m jobs submit   [--pyq] <file1> [file2] ...")
        print("  python -m jobs status   [job_id]")
        print("  python -m jobs overview")
        return

    cmd = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "worker": _cmd_worker,
        "submit": _cmd_submit,
        "status": _cmd_status,
        "overview": _cmd_overview,
    }

    handler = commands.get(cmd)
    if handler:
        handler(args)
    else:
        print(f"Unknown command: {cmd}")
        print("Available: worker, submit, status, overview")


if __name__ == "__main__":
    main()
