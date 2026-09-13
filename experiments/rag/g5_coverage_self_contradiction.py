"""
G5 — does fast_coverage contradict itself?

Q1 showed the `covered` boolean is computed from RRF score and is effectively
always true. G1 showed something else: when the production answer prompt is run
on a topic the corpus does not contain, the LLM says so 67% of the time
unprompted.

Those two facts sit in the same response object. `fast_coverage` returns:

    {"covered": <from RRF score>, "confidence": ..., "answer": <LLM prose>}

If the prose says "this is not covered" while the boolean says `true`, the
endpoint is internally inconsistent - and the component that is right is the
one that actually looked at the evidence.

That reframes the whole workstream. The question is not "what threshold should
replace the RRF gate" (Q8 found no threshold the three populations agree on).
It is "why is a boolean being computed from a rank score at all, when the
generator already produces a verdict from the evidence?"

This runs the REAL production coverage prompt over four independently
constructed classes and compares the boolean with the prose:

  known_present   topics with heavy lexical presence in the subject
  known_absent    lexically verified absent (anchor term occurs 0 times)
  related_insufficient  a real topic from a DIFFERENT subject, sharing
                  vocabulary with the target but not content
  short_ambiguous a bare high-frequency term ("TCP") that matches hundreds
                  of slides - covered, but not answerable as asked

Isolated: builds the same context and prompt as fast_coverage but calls the LLM
directly, so nothing is cached and no production state changes.
"""

import asyncio
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from openai import AsyncOpenAI                          # noqa: E402
from engine.config import OLLAMA_BASE_URL, OLLAMA_MODEL  # noqa: E402
from engine.fast_mode import _build_context, _COVERAGE_SYSTEM  # noqa: E402
from engine.tools import run_hybrid_search              # noqa: E402
from indexing.database import SessionFactory            # noqa: E402
from indexing.db_chroma import ChromaStore              # noqa: E402
from indexing.embedder import Embedder                  # noqa: E402
from indexing.models import Slide                       # noqa: E402

HARD = REPO / "experiments" / "benchmarks" / "hard_eval_set.json"
OUT = REPO / "experiments" / "benchmarks" / "g5_coverage.json"
# Groq free tier 429s at 2+ concurrent; Ollama is local and unmetered.
MODEL = OLLAMA_MODEL
CONCURRENCY = 1

NOT_COVERED = re.compile(
    r"\b(not\s+covered|does\s+not\s+(?:appear|cover|contain)|isn'?t\s+covered|"
    r"no\s+(?:slides?|material|mention|coverage)|not\s+(?:present|included|"
    r"found|in\s+your)|nothing\s+(?:in|about)|absent\s+from)\b", re.IGNORECASE)


def classify_rrf(top_score):
    """Verbatim production rule from engine/fast_mode.py::fast_coverage."""
    if top_score > 0.025:
        return "high"
    if top_score > 0.015:
        return "medium"
    return "low"


async def ask(client, topic, subject, context, confidence, top_score):
    user = (f"Subject: {subject}\nTopic to check: {topic}\n"
            f"Match confidence: {confidence} (top RRF score {top_score:.4f})\n\n"
            f"Closest matching slides:\n{context}")
    for attempt in range(3):
        try:
            r = await client.chat.completions.create(
                model=MODEL, temperature=0.3, max_tokens=1200,
                messages=[{"role": "system", "content": _COVERAGE_SYSTEM},
                          {"role": "user", "content": user}])
            return (r.choices[0].message.content or "").strip()
        except Exception:
            await asyncio.sleep(2 * (attempt + 1))
    return ""


def build_probes(session):
    """Four independently constructed classes. No embedding used for labels."""
    counts, by_subject = {}, {}
    for sl in session.query(Slide).filter(Slide.is_embedded == True).all():  # noqa: E712
        c = counts.setdefault(sl.subject, Counter())
        c.update(re.findall(r"[a-z0-9]+",
                            f"{sl.summary or ''} {sl.concepts or ''} "
                            f"{sl.raw_text or ''}".lower()))
        by_subject.setdefault(sl.subject, []).append(sl)

    probes = []

    # known_present: terms occurring very frequently in their own subject
    present_specs = [("TCP congestion control", "CN"), ("SMTP", "CN"),
                     ("ARM instruction set", "CA"), ("pipelining", "CA"),
                     ("gradient descent", "ML"), ("waterfall model", "SE")]
    for topic, subj in present_specs:
        if subj not in counts:
            continue
        toks = [t for t in re.findall(r"[a-z0-9]+", topic.lower()) if len(t) > 2]
        occ = min(counts[subj].get(t, 0) for t in toks) if toks else 0
        if occ >= 3:
            probes.append({"topic": topic, "subject": subj,
                           "cls": "known_present", "evidence": f"min term {occ}x"})

    # known_absent: from the lexically verified in_subject_absent set
    for it in json.loads(HARD.read_text(encoding="utf-8")):
        if it["category"] == "in_subject_absent" and len(probes) < 40:
            topic = it["question"].replace("Explain ", "").replace(
                " as covered in this subject.", "")
            probes.append({"topic": topic, "subject": it["subject"],
                           "cls": "known_absent",
                           "evidence": it["verification"]["anchor_term"] + " 0x"})
        if sum(1 for p in probes if p["cls"] == "known_absent") >= 10:
            break

    # related_insufficient: a real topic from another subject
    cross = [("gradient descent", "CN"), ("ARM barrel shifter", "ML"),
             ("waterfall model", "CA"), ("TCP three-way handshake", "SE"),
             ("linear regression", "CA")]
    for topic, subj in cross:
        if subj not in counts:
            continue
        toks = [t for t in re.findall(r"[a-z0-9]+", topic.lower()) if len(t) > 2]
        occ = min(counts[subj].get(t, 0) for t in toks) if toks else 0
        if occ == 0:
            probes.append({"topic": topic, "subject": subj,
                           "cls": "related_insufficient",
                           "evidence": "rarest term 0x in target subject"})

    # short_ambiguous: bare high-frequency terms - genuinely covered, but the
    # query names hundreds of slides equally
    for topic, subj in [("TCP", "CN"), ("memory", "CA"), ("model", "ML"),
                        ("testing", "SE")]:
        if subj in counts and counts[subj].get(topic.lower(), 0) > 20:
            probes.append({"topic": topic, "subject": subj,
                           "cls": "short_ambiguous",
                           "evidence": f"{counts[subj][topic.lower()]}x in subject"})
    return probes


async def main():
    session = SessionFactory()
    embedder, chroma = Embedder(), ChromaStore()
    probes = build_probes(session)
    print(f"{len(probes)} probes: {dict(Counter(p['cls'] for p in probes))}\n")

    client = AsyncOpenAI(api_key="ollama", base_url=OLLAMA_BASE_URL)
    sem = asyncio.Semaphore(CONCURRENCY)

    prepared = []
    for p in probes:
        stats = {}
        slides = run_hybrid_search(p["topic"], p["subject"], session, embedder,
                                   chroma, top_k=8, stats=stats)
        top = slides[0].get("rrf_score", 0) if slides else 0
        conf = classify_rrf(top) if slides else "none"
        prepared.append({**p, "slides": slides, "rrf_top1": top,
                         "confidence": conf,
                         "covered_boolean": conf in ("high", "medium"),
                         "dense_top1": stats["dense_top1"],
                         "context": _build_context(slides[:6])})

    async def one(pp):
        async with sem:
            ans = await ask(client, pp["topic"], pp["subject"], pp["context"],
                            pp["confidence"], pp["rrf_top1"])
            return {**{k: v for k, v in pp.items()
                       if k not in ("slides", "context")},
                    "answer": ans,
                    "prose_says_not_covered": bool(NOT_COVERED.search(ans))}

    rows = await asyncio.gather(*[one(p) for p in prepared])
    session.close()

    print("=" * 100)
    print(f"{'topic':30s} {'subj':5s} {'class':22s} {'bool':>6s} {'prose':>10s} "
          f"{'dense':>7s} {'agree':>6s}")
    print("=" * 100)
    for r in sorted(rows, key=lambda x: (x["cls"], x["topic"])):
        prose = "NOT cov" if r["prose_says_not_covered"] else "covered"
        agree = (r["covered_boolean"] != r["prose_says_not_covered"])
        print(f"{r['topic'][:30]:30s} {r['subject'][:5]:5s} {r['cls']:22s} "
              f"{str(r['covered_boolean']):>6s} {prose:>10s} "
              f"{r['dense_top1']:>7.4f} {'yes' if agree else 'NO':>6s}")

    print("\n" + "=" * 76)
    print("SELF-CONTRADICTION - boolean vs the prose in the same response")
    print("=" * 76)
    contra = [r for r in rows
              if r["covered_boolean"] and r["prose_says_not_covered"]]
    print(f"  responses where covered=True but the answer says NOT covered: "
          f"{len(contra)}/{len(rows)} ({len(contra)/len(rows):.0%})")
    for r in contra[:6]:
        print(f"    [{r['cls']:20s}] {r['topic']!r} ({r['subject']})")

    print("\n" + "=" * 76)
    print("WHICH COMPONENT IS RIGHT?")
    print("=" * 76)
    print(f"{'class':24s} {'n':>4s} {'boolean correct':>16s} {'prose correct':>15s}")
    for cls in ("known_present", "known_absent", "related_insufficient",
                "short_ambiguous"):
        grp = [r for r in rows if r["cls"] == cls]
        if not grp:
            continue
        should_be_covered = cls in ("known_present", "short_ambiguous")
        b_ok = sum(1 for r in grp if r["covered_boolean"] == should_be_covered)
        p_ok = sum(1 for r in grp
                   if (not r["prose_says_not_covered"]) == should_be_covered)
        print(f"{cls:24s} {len(grp):>4d} {b_ok}/{len(grp):<14} {p_ok}/{len(grp):<13}")

    b_tot = sum(1 for r in rows
                if r["covered_boolean"] == (r["cls"] in ("known_present",
                                                          "short_ambiguous")))
    p_tot = sum(1 for r in rows
                if (not r["prose_says_not_covered"])
                == (r["cls"] in ("known_present", "short_ambiguous")))
    print(f"\n  overall: boolean {b_tot}/{len(rows)} ({b_tot/len(rows):.0%})   "
          f"prose {p_tot}/{len(rows)} ({p_tot/len(rows):.0%})")

    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    os.environ["EXAMAI_OBSERVE_RETRIEVAL"] = "0"
    asyncio.run(main())
