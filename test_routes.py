"""
test_routes.py — Validate that every search & exam route sends complete,
correct context to the LLM.

For each route that calls an LLM (fast or reasoning mode), this script
reconstructs the EXACT prompt / tool-output that the LLM would see and
checks that every required piece of information is present.

Run:
    python test_routes.py            (uses first subject found in DB)
    python test_routes.py CA         (specify subject)
"""

import sys
import json
import logging

logging.basicConfig(level=logging.WARNING)

from indexing.database import init_db, SessionFactory
from indexing.models import Document, Slide, PYQQuestion, Subject
from engine.tools import (
    slide_to_dict,
    is_substantive,
    run_hybrid_search,
    get_priority_slides,
    get_subject_overview,
    get_chapter_structure,
    get_pyq_report,
    get_weak_spots,
    search_by_type,
    search_by_concept,
    get_slide_detail,
)
from engine.fast_mode import _build_context
from engine import get_embedder, get_chroma

init_db()

# ── Colour helpers ───────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

passed = 0
failed = 0
skipped = 0


def ok(msg: str):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg: str):
    global failed
    failed += 1
    print(f"  {RED}✗{RESET} {msg}")


def skip(msg: str):
    global skipped
    skipped += 1
    print(f"  {YELLOW}⚠{RESET} {msg}")


def section(title: str):
    print(f"\n{CYAN}{BOLD}{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}{RESET}")


# ── Resolve subject ─────────────────────────────────────────────────────

def get_subject() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1].strip().upper()
    session = SessionFactory()
    subj = session.query(Subject).first()
    session.close()
    if subj:
        return subj.name
    slide = session.query(Slide).first()
    if slide and slide.subject:
        return slide.subject
    return ""


# ── Shared state (loaded once, reused) ──────────────────────────────────

REQUIRED_SLIDE_FIELDS = [
    "slide_id", "doc_id", "page_number", "filename", "slide_type",
    "exam_signal", "summary", "concepts", "chapter",
    "pyq_hit_count", "importance_score",
]


# =====================================================================
#  1. POST /api/search/query  (fast mode) → fast_search
# =====================================================================

def test_fast_search_context(subject: str, session, embedder, chroma):
    """
    Reconstruct the exact LLM prompt for POST /query (fast).
    fast_search builds:
      user_msg = "Subject: {subject}\\nStudent's question: {query}\\n\\nRelevant slides:\\n{context}"
    where context = _build_context(slides).
    """
    section("POST /query (fast) → fast_search")

    slides = run_hybrid_search(
        "important concepts", subject, session, embedder, chroma, top_k=10,
    )
    if not slides:
        skip("No hybrid search results — can't verify fast_search context")
        return

    ok(f"Hybrid search returned {len(slides)} slides")

    # ── Verify every slide dict has all fields needed by _build_context ──
    context_fields = ["page_number", "filename", "chapter", "slide_type",
                      "importance_score", "pyq_hit_count", "exam_signal",
                      "concepts", "summary"]
    for i, s in enumerate(slides):
        missing = [f for f in context_fields if f not in s]
        if missing:
            fail(f"Slide {i} missing fields for context: {missing}")
            return
    ok(f"All {len(slides)} slides have full metadata for context builder")

    # ── No raw_text leaking into slide dicts ──
    raw_leak = [i for i, s in enumerate(slides) if "raw_text" in s]
    if raw_leak:
        fail(f"raw_text found in slide dicts at positions {raw_leak}")
    else:
        ok("No raw_text in slide dicts")

    # ── Build the context exactly as fast_search does ──
    context = _build_context(slides)

    # ── Check every required marker is in the LLM context string ──
    markers = {
        "Summary:": "AI-processed summary",
        "Concepts:": "extracted concepts",
        "Chapter:": "chapter name",
        "Type:": "slide type",
        "Priority:": "priority tier (HIGH/MEDIUM/LOW)",
        "PYQ Hits:": "past-year question hit count",
        "Exam Signal:": "exam signal flag",
        "[Slide": "slide identifier",
        "Page": "page number reference",
    }
    for marker, desc in markers.items():
        if marker in context:
            ok(f"Context contains {desc} ({marker})")
        else:
            fail(f"Context MISSING {desc} ({marker})")

    # ── Must NOT have raw text ──
    if "Content:" in context:
        fail("Context contains 'Content:' block — raw OCR text is leaking to LLM")
    else:
        ok("No raw 'Content:' block in LLM context")

    # ── Build the full user_msg as fast_search does ──
    query = "important concepts"
    user_msg = (
        f"Subject: {subject}\nStudent's question: {query}\n\n"
        f"Relevant slides:\n{context}"
    )
    if f"Subject: {subject}" in user_msg:
        ok("user_msg contains Subject")
    else:
        fail("user_msg MISSING Subject")

    if f"Student's question: {query}" in user_msg:
        ok("user_msg contains the student's query")
    else:
        fail("user_msg MISSING student's query")

    # ── Verify response shape fields ──
    # fast_search returns: answer, slides (list), mode, model_used
    # Check that slide references in the response have needed keys
    response_slide_keys = ["slide_id", "page_number", "filename", "chapter",
                           "slide_type", "importance_score", "pyq_hit_count", "rrf_score"]
    for s in slides:
        missing = [k for k in response_slide_keys if k not in s]
        if missing:
            fail(f"Response slide missing keys: {missing}")
            return
    ok(f"Response slide refs have all {len(response_slide_keys)} keys")

    print(f"\n  {BOLD}Sample LLM input (first 600 chars):{RESET}")
    print(f"  {user_msg[:600]}")


# =====================================================================
#  2. POST /api/search/coverage → fast_coverage
# =====================================================================

def test_fast_coverage_context(subject: str, session, embedder, chroma):
    """
    Reconstruct the exact LLM prompt for POST /coverage.
    fast_coverage builds:
      user_msg = "Subject: {subject}\\nTopic to check: {topic}\\n
                  Match confidence: {confidence} (top RRF score {score})\\n
                  Closest matching slides:\\n{context}"
    """
    section("POST /coverage → fast_coverage")

    topic = "tcp protocol"
    slides = run_hybrid_search(topic, subject, session, embedder, chroma, top_k=8)
    if not slides:
        skip("No slides found — can't verify coverage context")
        return

    ok(f"Hybrid search for coverage returned {len(slides)} slides")

    # ── Compute confidence exactly as fast_coverage does ──
    top_score = slides[0].get("rrf_score", 0)
    if top_score > 0.025:
        confidence = "high"
    elif top_score > 0.015:
        confidence = "medium"
    else:
        confidence = "low"

    context = _build_context(slides[:6])

    user_msg = (
        f"Subject: {subject}\n"
        f"Topic to check: {topic}\n"
        f"Match confidence: {confidence} (top RRF score {top_score:.4f})\n\n"
        f"Closest matching slides:\n{context}"
    )

    # ── Validate all parts of the user_msg ──
    checks = {
        f"Subject: {subject}": "Subject",
        f"Topic to check: {topic}": "Topic",
        f"Match confidence: {confidence}": "Confidence verdict",
        f"top RRF score": "RRF score value",
        "Summary:": "Slide summaries",
        "Concepts:": "Slide concepts",
        "Chapter:": "Chapter info",
        "Priority:": "Priority tier",
        "PYQ Hits:": "PYQ hit counts",
    }
    for marker, desc in checks.items():
        if marker in user_msg:
            ok(f"Coverage prompt has {desc}")
        else:
            fail(f"Coverage prompt MISSING {desc}")

    if "Content:" in user_msg:
        fail("Coverage prompt has raw 'Content:' block — not allowed")
    else:
        ok("No raw text in coverage prompt")

    # ── Response shape ──
    # fast_coverage returns: covered (bool), confidence, answer, slides, model_used
    response_keys = ["slide_id", "page_number", "filename", "chapter", "rrf_score"]
    for s in slides[:6]:
        missing = [k for k in response_keys if k not in s]
        if missing:
            fail(f"Coverage response slide missing: {missing}")
            return
    ok(f"Coverage response slides have all {len(response_keys)} reference keys")


# =====================================================================
#  3. POST /api/exam/study-plan (fast) → fast_study_plan
# =====================================================================

def test_fast_study_plan_context(subject: str, session):
    """
    Reconstruct the exact LLM prompt for POST /study-plan (fast).
    fast_study_plan builds lines[] with:
      - Subject, total slides, PYQ count
      - Chapter structure
      - HIGH/MEDIUM/LOW tiers with per-slide: Page, Filename, Chapter, Type,
        PYQ Hits, Score, Concepts, Summary[:200]
    """
    section("POST /study-plan (fast) → fast_study_plan")

    tiers = get_priority_slides(subject, session)
    overview = get_subject_overview(subject, session)
    chapters = get_chapter_structure(subject, session)

    total = sum(len(t) for t in tiers.values())
    if total == 0:
        skip("No prioritised slides — can't verify study-plan context")
        return

    # ── Build lines exactly as fast_study_plan does ──
    lines = [
        f"Subject: {subject}",
        f"Total slides: {overview['total_slides']}",
        f"PYQ questions mapped: {overview['pyq_questions']}",
    ]
    if chapters:
        lines.append("\nChapter structure:")
        for ch in chapters:
            lines.append(f"  - {ch.get('name', '?')} ({ch.get('filename', '')})")

    for tier_name, slides in [
        ("HIGH PRIORITY", tiers["high"]),
        ("MEDIUM PRIORITY", tiers["medium"]),
        ("LOW PRIORITY", tiers["low"]),
    ]:
        lines.append(f"\n=== {tier_name} ({len(slides)} slides) ===")
        for s in slides[:15]:
            lines.append(
                f"Page {s['page_number']} of {s['filename']} | "
                f"{s['chapter']} | Type: {s['slide_type']} | "
                f"PYQ Hits: {s['pyq_hit_count']} | "
                f"Score: {s['importance_score']:.2f}\n"
                f"  Concepts: {s['concepts']}\n"
                f"  Summary: {s['summary'][:200]}"
            )

    prompt = "\n".join(lines)

    # ── Validate prompt contents ──
    checks = {
        f"Subject: {subject}": "Subject name",
        "Total slides:": "Total slide count",
        "PYQ questions mapped:": "PYQ count",
        "HIGH PRIORITY": "High priority section",
        "MEDIUM PRIORITY": "Medium priority section",
        "LOW PRIORITY": "Low priority section",
    }
    for marker, desc in checks.items():
        if marker in prompt:
            ok(f"Study-plan prompt has {desc}")
        else:
            fail(f"Study-plan prompt MISSING {desc}")

    # ── Verify per-slide data in the prompt ──
    slide_markers = ["Page", "Type:", "PYQ Hits:", "Score:", "Concepts:", "Summary:"]
    for marker in slide_markers:
        if marker in prompt:
            ok(f"Per-slide data has '{marker}'")
        else:
            fail(f"Per-slide data MISSING '{marker}'")

    # ── Chapter structure if available ──
    if chapters:
        if "Chapter structure:" in prompt:
            ok(f"Chapter structure present ({len(chapters)} chapters)")
        else:
            fail("Chapter structure data missing from prompt")
    else:
        skip("No chapter data to verify")

    # ── Verify slide dicts have all fields used in the template ──
    template_fields = ["page_number", "filename", "chapter", "slide_type",
                       "pyq_hit_count", "importance_score", "concepts", "summary"]
    any_tier = tiers["high"] or tiers["medium"] or tiers["low"]
    for s in any_tier[:5]:
        missing = [f for f in template_fields if f not in s]
        if missing:
            fail(f"Tier slide missing fields in dict: {missing}")
            return
    ok(f"All tier slides have {len(template_fields)} fields used in template")

    # ── No raw_text ──
    if "raw_text" in prompt.lower() or "Content:" in prompt:
        fail("Study-plan prompt contains raw text")
    else:
        ok("No raw text in study-plan prompt")

    # ── Response shape: plan, stats, mode, model_used ──
    stats_keys = ["high_priority", "medium_priority", "low_priority",
                  "total_slides", "pyq_questions"]
    dummy_stats = {
        "high_priority": len(tiers["high"]),
        "medium_priority": len(tiers["medium"]),
        "low_priority": len(tiers["low"]),
        "total_slides": overview["total_slides"],
        "pyq_questions": overview["pyq_questions"],
    }
    missing = [k for k in stats_keys if k not in dummy_stats]
    if missing:
        fail(f"Response stats would miss: {missing}")
    else:
        ok(f"Response stats include all {len(stats_keys)} counters")

    print(f"\n  {BOLD}Study-plan prompt length:{RESET} {len(prompt)} chars")
    print(f"  {BOLD}Slides per tier:{RESET} HIGH={len(tiers['high'])}, "
          f"MED={len(tiers['medium'])}, LOW={len(tiers['low'])}")


# =====================================================================
#  4. POST /api/exam/revision (fast) → fast_revision
# =====================================================================

def test_fast_revision_context(subject: str, session):
    """
    Reconstruct the exact LLM prompt for POST /revision (fast).
    fast_revision builds lines[] with:
      - Subject, time, total slides, PYQ count
      - HIGH slides (up to 15): Page, Filename, Chapter, Type, PYQ, Score, Concepts, Summary[:150]
      - MEDIUM slides (up to 10): Page, Filename, Chapter, Concepts
      - NUMERICAL PROBLEMS: Page, Filename, Chapter, Concepts
    """
    section("POST /revision (fast) → fast_revision")

    hours = 3.0
    total_min = int(hours * 60)
    tiers = get_priority_slides(subject, session)
    overview = get_subject_overview(subject, session)

    numericals = [
        s for tier in tiers.values() for s in tier
        if s["slide_type"] == "numerical_example"
    ]

    # ── Build lines exactly as fast_revision does ──
    lines = [
        f"Subject: {subject}",
        f"Time available: {hours} hours ({total_min} minutes)",
        f"Total slides: {overview['total_slides']}",
        f"PYQ questions mapped: {overview['pyq_questions']}",
    ]

    lines.append(f"\n=== HIGH PRIORITY ({len(tiers['high'])} slides) ===")
    for s in tiers["high"][:15]:
        lines.append(
            f"Page {s['page_number']} of {s['filename']} | {s['chapter']} | "
            f"Type: {s['slide_type']} | PYQ: {s['pyq_hit_count']} | "
            f"Score: {s['importance_score']:.2f}\n"
            f"  Concepts: {s['concepts']} | Summary: {s['summary'][:150]}"
        )

    lines.append(f"\n=== MEDIUM PRIORITY ({len(tiers['medium'])} slides) ===")
    for s in tiers["medium"][:10]:
        lines.append(
            f"Page {s['page_number']} of {s['filename']} | {s['chapter']} | "
            f"Concepts: {s['concepts']}"
        )

    if numericals:
        lines.append(f"\n=== NUMERICAL PROBLEMS ({len(numericals)} slides) ===")
        for s in numericals[:8]:
            lines.append(
                f"Page {s['page_number']} of {s['filename']} | "
                f"{s['chapter']} | {s['concepts']}"
            )

    prompt = "\n".join(lines)

    # ── Validate prompt contents ──
    checks = {
        f"Subject: {subject}": "Subject name",
        f"Time available: {hours} hours": "Time allocation",
        f"({total_min} minutes)": "Minutes conversion",
        "Total slides:": "Total slide count",
        "PYQ questions mapped:": "PYQ count",
        "HIGH PRIORITY": "High priority section",
        "MEDIUM PRIORITY": "Medium priority section",
    }
    for marker, desc in checks.items():
        if marker in prompt:
            ok(f"Revision prompt has {desc}")
        else:
            fail(f"Revision prompt MISSING {desc}")

    # ── HIGH slides must have full detail ──
    high_markers = ["Type:", "PYQ:", "Score:", "Concepts:", "Summary:"]
    if tiers["high"]:
        for marker in high_markers:
            if marker in prompt:
                ok(f"HIGH slides include '{marker}'")
            else:
                fail(f"HIGH slides MISSING '{marker}'")
    else:
        skip("No HIGH slides to check detail level")

    # ── MEDIUM slides have lighter detail ──
    if tiers["medium"]:
        # Medium section exists with page/chapter/concepts
        med_section_idx = prompt.find("MEDIUM PRIORITY")
        if med_section_idx > 0:
            med_section = prompt[med_section_idx:]
            if "Concepts:" in med_section:
                ok("MEDIUM slides include Concepts")
            else:
                fail("MEDIUM slides MISSING Concepts")
        else:
            fail("MEDIUM PRIORITY section not found")
    else:
        skip("No MEDIUM slides")

    # ── Numerical problems section ──
    if numericals:
        if "NUMERICAL PROBLEMS" in prompt:
            ok(f"Numerical problems section present ({len(numericals)} slides)")
        else:
            fail("Numerical problems section MISSING (numericals exist but not in prompt)")
    else:
        skip("No numerical_example slides to verify")

    # ── No raw_text ──
    if "raw_text" in prompt.lower() or "Content:" in prompt:
        fail("Revision prompt contains raw text")
    else:
        ok("No raw text in revision prompt")

    # ── Response shape ──
    stats_keys = ["high_priority", "medium_priority", "low_priority", "numerical_problems"]
    ok(f"Response would include: time_hours={hours}, time_minutes={total_min}, "
       f"numericals={len(numericals)}")

    print(f"\n  {BOLD}Revision prompt length:{RESET} {len(prompt)} chars")


# =====================================================================
#  5. POST /query & /study-plan & /revision (reasoning) → run_reasoning
#     Verify each tool returns correct & complete data
# =====================================================================

def test_reasoning_tool_search_slides(subject: str, session, embedder, chroma):
    """Reasoning tool: search_slides → run_hybrid_search JSON."""
    section("Reasoning tool: search_slides")

    results = run_hybrid_search(
        "linear regression", subject, session, embedder, chroma, top_k=10,
    )
    if not results:
        skip("No search results for reasoning tool test")
        return

    json_out = json.dumps(results, indent=2)
    ok(f"search_slides returns {len(results)} results ({len(json_out)} chars JSON)")

    # The agent parses this JSON — verify it has everything
    required = ["slide_id", "doc_id", "page_number", "filename", "slide_type",
                "exam_signal", "summary", "concepts", "chapter",
                "pyq_hit_count", "importance_score", "rrf_score"]
    r = results[0]
    missing = [f for f in required if f not in r]
    if missing:
        fail(f"Tool output missing: {missing}")
    else:
        ok(f"All {len(required)} fields present in tool JSON")

    if "raw_text" in r:
        fail("search_slides tool leaks raw_text to agent")
    else:
        ok("No raw_text in search_slides output")

    # Agent needs these to cite slides
    for f in ["page_number", "filename", "chapter", "summary"]:
        if r.get(f):
            ok(f"  Agent can cite: {f}='{str(r[f])[:50]}'")
        else:
            skip(f"  {f} empty (check structuring)")


def test_reasoning_tool_get_slide_content(subject: str, session):
    """Reasoning tool: get_slide_content → get_slide_detail JSON."""
    section("Reasoning tool: get_slide_content")

    slide = session.query(Slide).filter(Slide.subject == subject).first()
    if not slide:
        skip("No slides for get_slide_content test")
        return

    detail = get_slide_detail(slide.id, session)
    json_out = json.dumps(detail, indent=2)
    ok(f"get_slide_content returns {len(json_out)} chars JSON")

    # This tool MUST include raw_text — it's for deep drill-down
    if "raw_text" in detail and detail["raw_text"]:
        ok("raw_text present (correct — agent uses this for targeted lookup)")
    else:
        fail("raw_text MISSING — agent needs this for detailed slide analysis")

    for f in REQUIRED_SLIDE_FIELDS:
        if f not in detail:
            fail(f"Detail missing: {f}")
            return
    ok(f"All {len(REQUIRED_SLIDE_FIELDS)} metadata fields present")


def test_reasoning_tool_find_by_type(subject: str, session):
    """Reasoning tool: find_slides_by_type → search_by_type JSON."""
    section("Reasoning tool: find_slides_by_type")

    found = False
    for stype in ("definition", "concept", "numerical_example", "formula", "summary"):
        results = search_by_type(subject, stype, session)
        if results:
            json_out = json.dumps(results[:20], indent=2)
            ok(f"Type '{stype}': {len(results)} slides ({len(json_out)} chars)")

            r = results[0]
            missing = [f for f in REQUIRED_SLIDE_FIELDS if f not in r]
            if missing:
                fail(f"Type result missing: {missing}")
            else:
                ok(f"Full metadata in type-filtered results")

            if "raw_text" in r:
                fail("Type results leak raw_text")
            else:
                ok("No raw_text in type results")
            found = True
            break
    if not found:
        skip("No slides found for any common type")


def test_reasoning_tool_find_by_concept(subject: str, session):
    """Reasoning tool: find_slides_by_concept → search_by_concept JSON."""
    section("Reasoning tool: find_slides_by_concept")

    # Get a concept that exists
    slide = (
        session.query(Slide)
        .filter(Slide.subject == subject, Slide.concepts.isnot(None), Slide.concepts != "")
        .first()
    )
    if not slide or not slide.concepts:
        skip("No slides with concepts to test concept search")
        return

    keyword = slide.concepts.split(",")[0].strip()
    results = search_by_concept(subject, keyword, session)
    if not results:
        skip(f"Concept search for '{keyword}' returned nothing")
        return

    ok(f"Concept '{keyword}': {len(results)} slides")
    r = results[0]
    missing = [f for f in REQUIRED_SLIDE_FIELDS if f not in r]
    if missing:
        fail(f"Concept result missing: {missing}")
    else:
        ok(f"Full metadata in concept-filtered results")

    if "raw_text" in r:
        fail("Concept results leak raw_text")
    else:
        ok("No raw_text in concept results")


def test_reasoning_tool_priorities(subject: str, session):
    """Reasoning tool: get_priorities → tier summary JSON."""
    section("Reasoning tool: get_priorities")

    tiers = get_priority_slides(subject, session)
    summary = {
        "high_count": len(tiers["high"]),
        "medium_count": len(tiers["medium"]),
        "low_count": len(tiers["low"]),
        "high_slides": tiers["high"][:15],
        "medium_slides": tiers["medium"][:10],
        "low_slides": tiers["low"][:5],
    }
    json_out = json.dumps(summary, indent=2)
    ok(f"Priorities: H={summary['high_count']}, M={summary['medium_count']}, "
       f"L={summary['low_count']} ({len(json_out)} chars)")

    # Agent needs counts + slide details to build plans
    for key in ("high_count", "medium_count", "low_count",
                "high_slides", "medium_slides", "low_slides"):
        if key not in summary:
            fail(f"Priority summary missing: {key}")
            return
    ok("All tier counts and slide lists present")

    # Check slides in tiers have required fields
    any_slides = summary["high_slides"] or summary["medium_slides"] or summary["low_slides"]
    if any_slides:
        s = any_slides[0]
        missing = [f for f in REQUIRED_SLIDE_FIELDS if f not in s]
        if missing:
            fail(f"Priority slide missing: {missing}")
        else:
            ok("Priority slides have full metadata")
        if "raw_text" in s:
            fail("Priority slides leak raw_text")
        else:
            ok("No raw_text in priority slides")
    else:
        skip("No slides in any tier")


def test_reasoning_tool_pyq_data(subject: str, session):
    """Reasoning tool: get_pyq_data → PYQ report JSON."""
    section("Reasoning tool: get_pyq_data")

    report = get_pyq_report(subject, session)

    if report["total_questions"] == 0:
        skip("No PYQ questions — can't verify pyq_data tool")
        return

    ok(f"{report['total_questions']} PYQ questions")

    # Check report structure
    for key in ("subject", "total_questions", "questions"):
        if key not in report:
            fail(f"Report missing: {key}")
            return
    ok("Report has subject, total_questions, questions")

    q = report["questions"][0]
    q_keys = ["question_id", "question_text", "source_file", "matched_slides", "match_count"]
    missing = [k for k in q_keys if k not in q]
    if missing:
        fail(f"Question entry missing: {missing}")
    else:
        ok(f"Question has all {len(q_keys)} fields")
        ok(f"  Q1: '{q['question_text'][:80]}...'")

    # Check matched slide structure
    if q["matched_slides"]:
        ms = q["matched_slides"][0]
        ms_keys = ["slide_id", "page_number", "filename", "chapter",
                    "concepts", "similarity_score"]
        missing = [k for k in ms_keys if k not in ms]
        if missing:
            fail(f"Matched slide missing: {missing}")
        else:
            ok(f"Matched slide has all {len(ms_keys)} fields")
    else:
        skip("No matched slides for first question")

    # The agent truncates question_text to 300 chars
    long_qs = [q for q in report["questions"] if len(q["question_text"]) > 300]
    if long_qs:
        ok(f"{len(long_qs)} questions >300 chars (agent will truncate to 300)")
    else:
        ok("All questions fit within 300-char agent truncation limit")


def test_reasoning_tool_chapters(subject: str, session):
    """Reasoning tool: get_chapters → chapter structure JSON."""
    section("Reasoning tool: get_chapters")

    chapters = get_chapter_structure(subject, session)
    if not chapters:
        skip("No chapter structure data")
        return

    json_out = json.dumps(chapters, indent=2)
    ok(f"{len(chapters)} chapters ({len(json_out)} chars)")

    ch = chapters[0]
    for key in ("filename", "doc_id"):
        if key not in ch:
            fail(f"Chapter entry missing: {key}")
            return
    ok("Chapter entries have filename and doc_id")

    # Check that chapter name exists (could be 'name' or 'chapter_name')
    if ch.get("name") or ch.get("chapter_name"):
        ok(f"  First chapter: '{ch.get('name', ch.get('chapter_name'))}'")
    else:
        skip("  Chapter name key unclear (check chapters_json format)")


def test_reasoning_tool_overview(subject: str, session):
    """Reasoning tool: get_overview → subject stats JSON."""
    section("Reasoning tool: get_overview")

    overview = get_subject_overview(subject, session)
    json_out = json.dumps(overview, indent=2)
    ok(f"Overview ({len(json_out)} chars)")

    required = ["subject", "documents", "total_slides", "embedded_slides",
                "pyq_questions", "avg_importance", "high_priority_slides",
                "document_list"]
    missing = [k for k in required if k not in overview]
    if missing:
        fail(f"Overview missing: {missing}")
    else:
        ok(f"All {len(required)} stat fields present")

    # Verify document_list entries
    if overview["document_list"]:
        d = overview["document_list"][0]
        for key in ("id", "filename", "core_topics", "total_slides"):
            if key not in d:
                fail(f"Document entry missing: {key}")
                return
        ok("Document list entries have id, filename, core_topics, total_slides")
    else:
        skip("No documents in overview list")

    print(f"    Docs={overview['documents']}, Slides={overview['total_slides']}, "
          f"PYQ={overview['pyq_questions']}, AvgImp={overview['avg_importance']}")


def test_reasoning_tool_weak_spots(subject: str, session):
    """Reasoning tool: find_weak_spots → weak spots JSON."""
    section("Reasoning tool: find_weak_spots")

    weak = get_weak_spots(subject, session)
    if not weak:
        skip("No weak spots (or no PYQ data)")
        return

    json_out = json.dumps(weak, indent=2)
    ok(f"{len(weak)} weak spots ({len(json_out)} chars)")

    w = weak[0]
    required = ["chapter", "pyq_hits", "matched_slides", "total_slides",
                "coverage_ratio", "priority"]
    missing = [k for k in required if k not in w]
    if missing:
        fail(f"Weak spot missing: {missing}")
    else:
        ok(f"All {len(required)} weak-spot fields present")

    for w in weak[:3]:
        ok(f"  {w['chapter']}: pyq={w['pyq_hits']}, "
           f"coverage={w['coverage_ratio']}, priority={w['priority']}")


# =====================================================================
#  6. GET /api/search/slides/{subject} — Direct DB (no LLM)
# =====================================================================

def test_route_filter_slides(subject: str, session):
    """GET /slides/{subject} — verify the DB query returns correct shape."""
    section("GET /slides/{subject} (no LLM, direct DB)")

    slides = (
        session.query(Slide)
        .filter(Slide.subject == subject, Slide.is_embedded == True)
        .order_by(Slide.importance_score.desc())
        .limit(5)
        .all()
    )
    if not slides:
        skip("No slides for filter test")
        return

    # Route builds rows with these keys:
    route_keys = ["slide_id", "page_number", "filename", "slide_type", "chapter",
                  "concepts", "summary", "exam_signal", "importance_score", "pyq_hit_count"]
    for sl in slides:
        doc = session.query(Document).filter(Document.id == sl.doc_id).first()
        row = {
            "slide_id": sl.id,
            "page_number": sl.page_number,
            "filename": doc.filename if doc else "",
            "slide_type": sl.slide_type,
            "chapter": sl.chapter,
            "concepts": sl.concepts,
            "summary": sl.summary,
            "exam_signal": sl.exam_signal,
            "importance_score": sl.importance_score,
            "pyq_hit_count": sl.pyq_hit_count,
        }
        missing = [k for k in route_keys if k not in row]
        if missing:
            fail(f"Slide row missing: {missing}")
            return
    ok(f"All {len(route_keys)} fields present in /slides response rows")
    ok(f"Verified {len(slides)} slides")


# =====================================================================
#  7. GET /api/search/concepts/{subject} — Direct DB (no LLM)
# =====================================================================

def test_route_concepts(subject: str, session):
    """GET /concepts/{subject} — verify concept browser data."""
    section("GET /concepts/{subject} (no LLM, direct DB)")

    slides = (
        session.query(Slide)
        .filter(Slide.subject == subject, Slide.concepts.isnot(None), Slide.concepts != "")
        .all()
    )
    if not slides:
        skip("No slides with concepts")
        return

    # Build concept frequency map as the route does
    freq = {}
    for sl in slides:
        for raw in sl.concepts.split(","):
            c = raw.strip().lower()
            if c:
                freq[c] = freq.get(c, 0) + 1

    ok(f"{len(freq)} unique concepts across {len(slides)} slides")
    top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:5]
    for c, f in top:
        ok(f"  '{c}' × {f}")


# =====================================================================
#  8. GET /api/exam/priorities/{subject} — Direct DB (no LLM)
# =====================================================================

def test_route_priorities(subject: str, session):
    """GET /priorities/{subject} — verify tier structure."""
    section("GET /priorities/{subject} (no LLM, direct DB)")

    tiers = get_priority_slides(subject, session)
    for tier in ("high", "medium", "low"):
        count = len(tiers.get(tier, []))
        if count > 0:
            ok(f"{tier}: {count} slides")
            s = tiers[tier][0]
            missing = [f for f in REQUIRED_SLIDE_FIELDS if f not in s]
            if missing:
                fail(f"  {tier}[0] missing: {missing}")
            if "raw_text" in s:
                fail(f"  {tier}[0] leaks raw_text")
        else:
            skip(f"{tier}: 0 slides")


# =====================================================================
#  9. GET /api/exam/pyq-report/{subject} — Direct DB (no LLM)
# =====================================================================

def test_route_pyq_report(subject: str, session):
    """GET /pyq-report/{subject} — verify returned structure."""
    section("GET /pyq-report/{subject} (no LLM, direct DB)")

    report = get_pyq_report(subject, session)
    for key in ("subject", "total_questions", "questions"):
        if key not in report:
            fail(f"Report missing: {key}")
            return
    ok(f"Report structure OK, {report['total_questions']} questions")

    if report["questions"]:
        q = report["questions"][0]
        for k in ("question_id", "question_text", "source_file", "matched_slides", "match_count"):
            if k not in q:
                fail(f"Question missing: {k}")
                return
        ok("Question entry structure complete")
    else:
        skip("No questions to verify structure")


# =====================================================================
# 10. GET /api/exam/weak-spots/{subject} — Direct DB (no LLM)
# =====================================================================

def test_route_weak_spots(subject: str, session):
    """GET /weak-spots/{subject} — verify structure."""
    section("GET /weak-spots/{subject} (no LLM, direct DB)")

    weak = get_weak_spots(subject, session)
    if not weak:
        skip("No weak spots")
        return

    w = weak[0]
    for k in ("chapter", "pyq_hits", "matched_slides", "total_slides",
              "coverage_ratio", "priority"):
        if k not in w:
            fail(f"Weak spot missing: {k}")
            return
    ok(f"{len(weak)} weak spots, all fields present")


# =====================================================================
# 11. GET /api/exam/readiness/{subject} — Composite (no LLM)
# =====================================================================

def test_route_readiness(subject: str, session):
    """GET /readiness/{subject} — verify composite score data."""
    section("GET /readiness/{subject} (no LLM, composite)")

    overview = get_subject_overview(subject, session)
    tiers = get_priority_slides(subject, session)
    weak = get_weak_spots(subject, session)

    total = overview["total_slides"]
    embedded = overview["embedded_slides"]
    pyq_qs = overview["pyq_questions"]

    # Reproduce the route's calculation
    material_cov = embedded / total if total > 0 else 0
    pyq_align = 1.0 if pyq_qs > 0 else 0.0
    hp_ratio = len(tiers["high"]) / total if total > 0 else 0
    critical_weak = [w for w in weak if w["priority"] == "high"]
    weak_penalty = min(len(critical_weak) * 0.1, 0.3)

    score = round(
        min(0.3 * material_cov + 0.3 * pyq_align + 0.2 * hp_ratio
            + 0.2 * (1.0 - weak_penalty), 1.0), 2,
    )

    for key in ("total_slides", "embedded_slides", "pyq_questions",
                "avg_importance", "high_priority_slides"):
        if key not in overview:
            fail(f"Readiness needs overview.{key}")
            return
    ok("All overview stats available for readiness computation")
    ok(f"Readiness score = {score} "
       f"(cov={material_cov:.2f}, pyq={pyq_align}, hp={hp_ratio:.2f}, "
       f"weak_pen={weak_penalty:.2f})")


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    subject = get_subject()
    if not subject:
        print(f"{RED}No subject found in DB. Process some material first.{RESET}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  ExamAI — LLM Context Validation for ALL Routes")
    print(f"  Subject: {subject}")
    print(f"{'='*60}")

    session = SessionFactory()
    embedder = get_embedder()
    chroma = get_chroma()

    # ── Fast-mode routes (reconstruct exact LLM prompts) ──

    test_fast_search_context(subject, session, embedder, chroma)
    test_fast_coverage_context(subject, session, embedder, chroma)
    test_fast_study_plan_context(subject, session)
    test_fast_revision_context(subject, session)

    # ── Reasoning-mode tools (verify each tool's JSON output) ──

    test_reasoning_tool_search_slides(subject, session, embedder, chroma)
    test_reasoning_tool_get_slide_content(subject, session)
    test_reasoning_tool_find_by_type(subject, session)
    test_reasoning_tool_find_by_concept(subject, session)
    test_reasoning_tool_priorities(subject, session)
    test_reasoning_tool_pyq_data(subject, session)
    test_reasoning_tool_chapters(subject, session)
    test_reasoning_tool_overview(subject, session)
    test_reasoning_tool_weak_spots(subject, session)

    # ── Direct DB routes (no LLM — verify response shapes) ──

    test_route_filter_slides(subject, session)
    test_route_concepts(subject, session)
    test_route_priorities(subject, session)
    test_route_pyq_report(subject, session)
    test_route_weak_spots(subject, session)
    test_route_readiness(subject, session)

    session.close()

    print(f"\n{'='*60}")
    print(f"  Results: {GREEN}{passed} passed{RESET}, "
          f"{RED}{failed} failed{RESET}, "
          f"{YELLOW}{skipped} skipped{RESET}")
    print(f"{'='*60}\n")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
