"""
models.py — Job tracking models for the async pipeline.

Tables live in the same SQLite database as indexing (examai.db).
Inherits from the same SQLAlchemy Base so init_db() picks them up.

Tables:
  jobs        — one row per submitted file
  job_phases  — one row per pipeline phase per job
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from indexing.models import Base


# ── Enums ────────────────────────────────────────────────────────────────

class JobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PhaseStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class JobType(str, enum.Enum):
    STUDY_MATERIAL = "study_material"
    PYQ = "pyq"


# Phase definitions per job type
STUDY_PHASES = ["ingest", "structure", "index"]
PYQ_PHASES = ["ingest_pyq", "extract", "map"]


# ── Models ───────────────────────────────────────────────────────────────

class Job(Base):
    __tablename__ = "jobs"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    filename        = Column(String, nullable=False)
    filepath        = Column(String, nullable=False)
    job_type        = Column(String, nullable=False, default=JobType.STUDY_MATERIAL.value)
    status          = Column(String, nullable=False, default=JobStatus.PENDING.value)
    current_phase   = Column(String, nullable=True)
    celery_chain_id = Column(String, nullable=True)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    error_message   = Column(Text, nullable=True)

    phases = relationship(
        "JobPhase",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobPhase.id",
    )

    def __repr__(self):
        return f"<Job id={self.id} file='{self.filename}' status='{self.status}'>"


class JobPhase(Base):
    __tablename__ = "job_phases"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    job_id          = Column(Integer, ForeignKey("jobs.id"), nullable=False, index=True)
    phase           = Column(String, nullable=False)
    status          = Column(String, nullable=False, default=PhaseStatus.PENDING.value)
    celery_task_id  = Column(String, nullable=True)
    started_at      = Column(DateTime, nullable=True)
    completed_at    = Column(DateTime, nullable=True)
    error_message   = Column(Text, nullable=True)

    job = relationship("Job", back_populates="phases")

    def __repr__(self):
        return f"<JobPhase job={self.job_id} phase='{self.phase}' status='{self.status}'>"
