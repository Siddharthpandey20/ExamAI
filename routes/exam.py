"""
routes/exam.py — Phase 8: Exam Intelligence endpoints.

GET  /priorities/{subject}   — Priority tier dashboard (High / Medium / Low)
POST /study-plan             — AI-generated study plan from importance data
POST /revision               — Time-constrained revision schedule
GET  /pyq-report/{subject}   — PYQ → slide mapping report
GET  /weak-spots/{subject}   — Weak spots (high PYQ freq, low coverage)
GET  /readiness/{subject}    — Exam readiness composite score
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from agents import trace
from dotenv import load_dotenv

from indexing.database import get_db_dep
from indexing.models import Subject
from engine.tools import (
    get_priority_slides,
    get_pyq_report,
    get_weak_spots,
    get_subject_overview,
)
from engine.fast_mode import fast_study_plan, fast_revision
from engine.reasoning_mode import run_reasoning

log = logging.getLogger(__name__)
router = APIRouter()
load_dotenv()

# ── Request schemas ──────────────────────────────────────────────────────

class StudyPlanRequest(BaseModel):
    subject: str
    mode: str = "fast"


class RevisionRequest(BaseModel):
    subject: str
    hours: float = Field(gt=0, le=24)
    mode: str = "fast"


# ── Helpers ──────────────────────────────────────────────────────────────

def _require_subject(name: str, db: Session) -> Subject:
    subj = db.query(Subject).filter(Subject.name == name.upper()).first()
    if not subj:
        raise HTTPException(404, f"Subject '{name}' not found.")
    return subj


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/")
def root():
    return {"status": "ok", "router": "exam"}

@router.get("/priorities/{subject}")
def priority_dashboard(subject: str, db: Session = Depends(get_db_dep)):
    """
    Classify all embedded slides into priority tiers.

    Thresholds (driven by importance_score):
      **High**  >= 0.4  — exam-critical, PYQ-heavy
      **Medium** >= 0.15
      **Low**   <  0.15
    """
    _require_subject(subject, db)
    subject = subject.strip().upper()

    tiers = get_priority_slides(subject, db)

    return {
        "subject": subject,
        "high": tiers["high"],
        "medium": tiers["medium"],
        "low": tiers["low"],
        "stats": {
            "high_count": len(tiers["high"]),
            "medium_count": len(tiers["medium"]),
            "low_count": len(tiers["low"]),
            "total": sum(len(t) for t in tiers.values()),
        },
    }


@router.post("/study-plan")
async def study_plan(
    body: StudyPlanRequest,
    force: bool = Query(False, description="Bypass cache and force a fresh LLM response"),
    db: Session = Depends(get_db_dep),
):
    """
    Generate a priority-ranked study plan.

    *mode*:
      - **fast** — single Groq call with pre-fetched priority + PYQ data
      - **reasoning** — AI agent that queries tools autonomously
    """
    with trace(f"study_plan:{body.subject}:{body.mode}"):
        _require_subject(body.subject, db)
        subject = body.subject.strip().upper()

        if body.mode == "reasoning":
            return await run_reasoning(
                f"Generate a comprehensive study plan for {subject}. "
                "Organise by priority, include specific slide references, and "
                "highlight topics most likely to appear in the exam.",
                subject,
                force=force,
            )
        return await fast_study_plan(subject, force=force)


@router.post("/revision")
async def revision_plan(
    body: RevisionRequest,
    force: bool = Query(False, description="Bypass cache and force a fresh LLM response"),
    db: Session = Depends(get_db_dep),
):
    """
    Generate a time-constrained revision schedule.

    *mode*:
      - **fast** — single Groq call with priority + numerical problem data
      - **reasoning** — AI agent that queries tools and builds a detailed plan
    """
    with trace(f"revision_plan:{body.subject}:{body.hours}h:{body.mode}"):
        _require_subject(body.subject, db)
        subject = body.subject.strip().upper()

        if body.mode == "reasoning":
            return await run_reasoning(
                f"I have {body.hours} hours before my {subject} exam. "
                "Create an optimised revision schedule with specific slides to "
                "study, time allocations per topic, and a quick review section.",
                subject,
                force=force,
            )
        return await fast_revision(subject, body.hours, force=force)


@router.get("/pyq-report/{subject}")
def pyq_report(subject: str, db: Session = Depends(get_db_dep)):
    """
    PYQ coverage report: which past-year questions map to which slides.

    Each question shows its matched slides with similarity scores,
    allowing students to see exactly what material is exam-relevant.
    """
    _require_subject(subject, db)
    subject = subject.strip().upper()
    return get_pyq_report(subject, db)


@router.get("/weak-spots/{subject}")
def weak_spots(subject: str, db: Session = Depends(get_db_dep)):
    """
    Find weak spots: chapters with high PYQ hit frequency but
    potentially low slide coverage. These are topics that need
    extra attention before the exam.
    """
    _require_subject(subject, db)
    subject = subject.strip().upper()

    spots = get_weak_spots(subject, db)
    return {
        "subject": subject,
        "weak_spots": spots,
        "total": len(spots),
    }


@router.get("/readiness/{subject}")
def exam_readiness(subject: str, db: Session = Depends(get_db_dep)):
    """
    Exam readiness composite score (0.0 – 1.0).

    Factors:
      - Material coverage (slides indexed / total)
      - PYQ alignment (have PYQ data been mapped?)
      - High-priority ratio (fraction of important slides)
      - Weak-spot penalty (unresolved critical gaps)

    Also returns actionable recommendations.
    """
    _require_subject(subject, db)
    subject = subject.strip().upper()

    overview = get_subject_overview(subject, db)
    tiers = get_priority_slides(subject, db)
    weak = get_weak_spots(subject, db)

    total = overview["total_slides"]
    embedded = overview["embedded_slides"]
    pyq_qs = overview["pyq_questions"]

    material_cov = embedded / total if total > 0 else 0
    pyq_align = 1.0 if pyq_qs > 0 else 0.0
    hp_ratio = len(tiers["high"]) / total if total > 0 else 0
    critical_weak = [w for w in weak if w["priority"] == "high"]
    weak_penalty = min(len(critical_weak) * 0.1, 0.3)

    score = round(
        min(
            0.3 * material_cov
            + 0.3 * pyq_align
            + 0.2 * hp_ratio
            + 0.2 * (1.0 - weak_penalty),
            1.0,
        ),
        2,
    )

    if score >= 0.7:
        verdict = "Well Prepared"
    elif score >= 0.4:
        verdict = "Needs More Work"
    else:
        verdict = "Not Ready"

    recommendations: list[str] = []
    if len(tiers["high"]) > 0:
        recommendations.append(
            f"Focus on {len(tiers['high'])} high-priority slides first"
        )
    if critical_weak:
        recommendations.append(
            f"Address {len(critical_weak)} critical weak spots with high PYQ frequency"
        )
    if pyq_qs == 0:
        recommendations.append(
            "Upload past-year question papers to unlock PYQ-driven insights"
        )

    return {
        "subject": subject,
        "readiness_score": score,
        "verdict": verdict,
        "breakdown": {
            "material_coverage": round(material_cov, 2),
            "pyq_alignment": pyq_align,
            "high_priority_ratio": round(hp_ratio, 2),
            "weak_spot_penalty": round(weak_penalty, 2),
        },
        "stats": overview,
        "recommendations": recommendations,
    }
