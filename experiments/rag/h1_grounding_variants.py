"""
H1 — can grounding and citation correctness be improved, and by what?

G1 established the failure modes: 83% of answers carried at least one
unsupported claim, 33% of absent-topic questions were answered anyway, and
three citations named documents that do not exist (`sdn_chapter.pdf`,
`cap_theory.pdf`). Two structural suspects were identified but not tested:

  - `_build_context` passes only `summary` + `concepts`, never `raw_text`, so
    answers are grounded in an ingestion-time LLM summary of a slide rather
    than the slide;
  - the citation format is a free-text filename in prose, so nothing prevents
    the model from inventing one.

Three variants, identical retrieval, so the experiment isolates the CONTEXT
REPRESENTATION and nothing else:

  A  current      summary + concepts, cite as "Page N of filename"
  B  raw_text     A plus the slide's actual text, capped per slide
  C  source_ids   B, but sources are labelled [S1]..[S6] and the model is told
                  to cite those labels. The backend maps a label back to the
                  real file and page, so a citation can only name a source that
                  was actually supplied - fabrication becomes unrepresentable
                  rather than merely discouraged.

MEASUREMENT IS MECHANICAL WHERE IT CAN BE. Previous rounds produced two false
findings from metric bugs, so the load-bearing numbers here never depend on a
judge:

  citation_valid      every citation resolves to a source that was supplied
  citation_fabricated a citation naming a file or label that was not supplied
  cited_gold          was the gold slide cited when it was in context
  unsupported_specifics numbers and acronyms in the answer that do not appear
                      anywhere in the context it was given

An LLM judge scores correctness and groundedness listwise (all three answers in
one call, shuffled and anonymised), and is reported separately.

EVERY RUN ASSERTS THAT LLM CALLS ACTUALLY HAPPENED. A previous experiment
returned llm_calls=0.26 because a helper swallowed 429s and returned "";
it looked like a finished result and measured nothing.

Isolated: uses the production pool and prompt, bypasses the cache, writes
nothing to the database.
"""

import asyncio
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from engine.fast_mode import _build_context, _SEARCH_SYSTEM   # noqa: E402
from engine.llm import pool                                    # noqa: E402
from engine.tools import run_hybrid_search                     # noqa: E402
from indexing.database import SessionFactory                   # noqa: E402
from indexing.db_chroma import ChromaStore                     # noqa: E402
from indexing.embedder import Embedder                         # noqa: E402
from indexing.models import Document                           # noqa: E402

EVAL = REPO / "eval" / "eval_set.json"
HARD = REPO / "experiments" / "benchmarks" / "hard_eval_set.json"
INDEP = REPO / "experiments" / "benchmarks" / "independent_eval.json"
OUT = REPO / "experiments" / "benchmarks" / "h1_grounding_variants.json"

TOP_K = 6
RAW_CHARS = 700          # per slide; keeps B/C within the existing 6000 budget
N_ANSWERABLE = 16
N_ABSENT = 8


# ── context builders ─────────────────────────────────────────────────────

def ctx_current(slides):
    return _build_context(slides), {}


def ctx_raw(slides):
    parts = []
    for i, s in enumerate(slides, 1):
        raw = (s.get("raw_text") or "").strip()
        parts.append(
            f"[Slide {i}] Page {s['page_number']} of {s['filename']}\n"
            f"  Chapter: {s['chapter']} | Type: {s['slide_type']}\n"
            f"  Concepts: {s['concepts']}\n"
            f"  Summary: {s['summary']}\n"
            f"  Slide text: {raw[:RAW_CHARS]}\n")
    return "\n".join(parts), {}


def ctx_source_ids(slides):
    """Label sources [S1]..[Sn]; the backend owns the mapping to file+page."""
    parts, mapping = [], {}
    for i, s in enumerate(slides, 1):
        sid = f"S{i}"
        mapping[sid] = {"slide_id": s["slide_id"], "page": s["page_number"],
                        "filename": s["filename"]}
        raw = (s.get("raw_text") or "").strip()
        parts.append(
            f"[{sid}] Chapter: {s['chapter']} | Type: {s['slide_type']}\n"
            f"  Concepts: {s['concepts']}\n"
            f"  Summary: {s['summary']}\n"
            f"  Slide text: {raw[:RAW_CHARS]}\n")
    return "\n".join(parts), mapping


_SOURCE_ID_SYSTEM = _SEARCH_SYSTEM.replace(
    '- Always reference specific slides: "Page X of filename"',
    '- Cite evidence using ONLY the bracketed source labels given above, '
    'exactly as written: [S1], [S2], ...\n'
    '- Never invent a file name, page number or source label. If you did not '
    'receive a source, you cannot cite it.')

VARIANTS = {
    "A_current":    (ctx_current,    _SEARCH_SYSTEM),
    "B_raw_text":   (ctx_raw,        _SEARCH_SYSTEM),
    "C_source_ids": (ctx_source_ids, _SOURCE_ID_SYSTEM),
}


# ── mechanical citation checking ─────────────────────────────────────────

def _norm(t):
    return unicodedata.normalize("NFKC", t or "").replace(" ", " ")


CITE_FILE = re.compile(
    r"[Pp]age\s*(\d+)\s*(?:of|in|,)?\s*[*_`\"']*"
    r"([A-Za-z0-9][A-Za-z0-9 _.\-]*?\.(?:pdf|pptx|md|ppt))[*_`\"']*", re.I)
CITE_SID = re.compile(r"\[\s*(S\d{1,2})\s*\]")
SPECIFIC = re.compile(r"\b(?:\d+(?:\.\d+)?|[A-Z]{2,}[0-9]*)\b")


def check_citations(answer, slides, mapping, real_files):
    a = _norm(answer)
    supplied_pairs = {(s["page_number"], s["filename"].lower()) for s in slides}
    supplied_pages = {s["page_number"] for s in slides}

    if mapping:                                   # variant C
        cited = CITE_SID.findall(a)
        valid = [c for c in cited if c in mapping]
        fabricated = [c for c in cited if c not in mapping]
        # A source-id variant may still emit a stray filename; that counts too.
        for pg, fn in CITE_FILE.findall(a):
            if (int(pg), fn.lower()) not in supplied_pairs:
                fabricated.append(f"{fn}:{pg}")
        cited_slide_ids = {mapping[c]["slide_id"] for c in valid}
    else:
        cited = [f"{fn}:{pg}" for pg, fn in CITE_FILE.findall(a)]
        valid, fabricated = [], []
        cited_slide_ids = set()
        for pg, fn in CITE_FILE.findall(a):
            pg = int(pg)
            if (pg, fn.lower()) in supplied_pairs:
                valid.append(f"{fn}:{pg}")
                for s in slides:
                    if s["page_number"] == pg and s["filename"].lower() == fn.lower():
                        cited_slide_ids.add(s["slide_id"])
            else:
                # Distinguish "wrong file" from "file that does not exist at
                # all" - the second is the hallucination that alarmed G1.
                fabricated.append(
                    f"{fn}:{pg}" + ("" if fn.lower() in real_files else " (NO SUCH FILE)"))
    return {
        "n_citations": len(cited),
        "n_valid": len(valid),
        "n_fabricated": len(fabricated),
        "fabricated": fabricated[:5],
        "nonexistent_file": sum(1 for f in fabricated if "NO SUCH FILE" in f),
        "cited_slide_ids": sorted(cited_slide_ids),
    }


def unsupported_specifics(answer, context):
    a = {m.group(0).lower() for m in SPECIFIC.finditer(_norm(answer))}
    c = {m.group(0).lower() for m in SPECIFIC.finditer(_norm(context))}
    return sorted(a - c)


# ── LLM calls ────────────────────────────────────────────────────────────

class Counter:
    calls = 0


async def _with_backoff(coro_factory, what):
    """Wait out the pool's own rate-limit accounting rather than failing.

    Each variant sends a 3-6k token context and the free tier allows ~10k
    tokens/minute per model, so three variants per item exhaust a minute window
    almost immediately. That is the pool behaving correctly; the experiment
    just has to run slower than the limits.
    """
    delay = 20.0
    for attempt in range(8):
        try:
            return await coro_factory()
        except RuntimeError as e:
            if "rate-limited" not in str(e) and "busy" not in str(e):
                raise
            await asyncio.sleep(delay)
            delay = min(delay * 1.4, 70)
    raise RuntimeError(f"{what}: gave up after repeated rate limiting")


async def generate(system, user):
    text, model = await _with_backoff(
        lambda: pool.complete(system, user, temperature=0.3, max_tokens=1400),
        "generate")
    Counter.calls += 1
    return text, model


async def judge(item, answers, context):
    import random
    labels = list(answers)
    random.shuffle(labels)
    letters = {l: chr(65 + i) for i, l in enumerate(labels)}
    blocks = "\n\n".join(f"--- ANSWER {letters[l]} ---\n{answers[l][:2000]}"
                         for l in labels)
    absent = item["kind"] == "absent"
    user = f"""QUESTION: {item['question']}
REFERENCE: {item.get('reference') or '(none)'}
IS THIS TOPIC IN THE MATERIAL? {'NO - verified absent' if absent else 'yes'}

CONTEXT SUPPLIED TO THE ASSISTANTS:
{context[:4500]}

{blocks}

For each answer letter return:
"correct": 2/1/0 {'(2 ONLY if it says the material does not cover this)' if absent else ''}
"grounded": 2/1/0 (2 = every claim traceable to the context)
"unsupported_claims": integer
"declines": true/false

Respond exactly like: {{"A": {{...}}, "B": {{...}}, "C": {{...}}}}"""
    try:
        txt, _ = await _with_backoff(
            lambda: pool.complete(
                "You grade a study assistant. Reply with ONLY one JSON object.",
                user, temperature=0.0, max_tokens=1200),
            "judge")
        Counter.calls += 1
    except Exception:
        return None
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(0))
    except Exception:
        return None
    return {l: parsed.get(letters[l]) for l in labels}


def build_items():
    items = []
    for q in json.loads(EVAL.read_text(encoding="utf-8"))[:N_ANSWERABLE]:
        items.append({"id": f"ans_{q['id']}", "kind": "answerable",
                      "question": q["question"], "subject": q["subject"],
                      "gold": {q["gold_slide_id"]},
                      "reference": q["expected_answer"]})
    for h in [x for x in json.loads(HARD.read_text(encoding="utf-8"))
              if x["category"] == "in_subject_absent"][:N_ABSENT]:
        items.append({"id": h["id"], "kind": "absent",
                      "question": h["question"], "subject": h["subject"],
                      "gold": set(),
                      "reference": "The material does not cover this topic."})
    return items


async def main():
    items = build_items()
    from collections import Counter as C
    print(f"{len(items)} items: {dict(C(i['kind'] for i in items))}")
    print(f"variants: {list(VARIANTS)}   retrieval held fixed\n")

    session = SessionFactory()
    embedder, chroma = Embedder(), ChromaStore()
    real_files = set()
    for d in session.query(Document).all():
        real_files.add((d.filename or "").lower())
        if d.original_filename:
            real_files.add(d.original_filename.lower())

    rows = []
    t0 = time.perf_counter()
    try:
        for n, item in enumerate(items, 1):
            slides = run_hybrid_search(item["question"], item["subject"],
                                       session, embedder, chroma, top_k=TOP_K)
            gold_in_ctx = bool({s["slide_id"] for s in slides} & item["gold"]) \
                if item["gold"] else None
            answers, contexts, meta = {}, {}, {}
            for vname, (builder, system) in VARIANTS.items():
                context, mapping = builder(slides)
                user = (f"Subject: {item['subject']}\n"
                        f"Student's question: {item['question']}\n\n"
                        f"Relevant slides:\n{context}")
                t1 = time.perf_counter()
                text, model = await generate(system, user)
                wall = (time.perf_counter() - t1) * 1000
                cit = check_citations(text, slides, mapping, real_files)
                uns = unsupported_specifics(text, context)
                answers[vname], contexts[vname] = text, context
                meta[vname] = {
                    **cit,
                    "cited_gold": bool(set(cit["cited_slide_ids"]) & item["gold"])
                    if item["gold"] else None,
                    "n_unsupported_specifics": len(uns),
                    "unsupported_sample": uns[:6],
                    "context_chars": len(context),
                    "answer_chars": len(text),
                    "wall_ms": round(wall), "model": model}
            verdict = await judge(item, answers, contexts["A_current"])
            for vname in VARIANTS:
                rows.append({"id": item["id"], "kind": item["kind"],
                             "variant": vname, "gold_in_context": gold_in_ctx,
                             **meta[vname], "judge": (verdict or {}).get(vname),
                             "answer": answers[vname][:1200]})
            print(f"  {n}/{len(items)} {item['kind']:10s} "
                  f"({time.perf_counter()-t0:.0f}s, {Counter.calls} calls)",
                  flush=True)
    finally:
        session.close()

    # The assertion that G3 lacked.
    expected = len(items) * len(VARIANTS)
    assert Counter.calls >= expected, (
        f"only {Counter.calls} LLM calls succeeded, expected at least "
        f"{expected} - the run is INVALID")

    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\n{len(rows)} rows, {Counter.calls} LLM calls -> {OUT}")


if __name__ == "__main__":
    os.environ["EXAMAI_OBSERVE_RETRIEVAL"] = "0"
    asyncio.run(main())
