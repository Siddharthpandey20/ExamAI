"""
G1 — answer grounding and citation correctness.

The first look at what the system SAYS rather than what it retrieves. Every
previous phase measured whether the right slide was found; none checked whether
the answer that follows is supported by it.

Two structural facts about the production path shape this experiment:

1. `_build_context` passes only `summary` and `concepts` to the LLM. It never
   passes `raw_text`. So an answer is grounded in an AI-written summary of the
   slide, not the slide - any error introduced at ingestion is invisible here
   and unfalsifiable downstream.

2. `_SEARCH_SYSTEM` instructs the model to "speak with authority as if you
   studied the material yourself" and never to say "based on the data
   provided", with no instruction to hedge when the evidence is thin. That is a
   prompt optimised for confident prose, which is exactly the condition under
   which ungrounded claims are hardest to notice.

MEASUREMENT IS MOSTLY DETERMINISTIC ON PURPOSE. LLM-as-judge is itself
unreliable, so the load-bearing metrics here are mechanical:

  citation validity     the answer cites "Page N of file". Is that page/file
                        actually in the context it was given? A citation to
                        something absent is fabricated, and no judgement call
                        is involved.
  citation completeness when the gold slide was in context, was it cited?
  lexical grounding     share of the answer's rare content terms that occur in
                        the context. A proxy for unsupported specifics, biased
                        toward leniency (paraphrase counts as grounded).

An LLM judge is used only for correctness against the reference answer, which
cannot be done mechanically, and its verdicts are reported separately from the
deterministic ones rather than blended into a single score.

INSUFFICIENT-EVIDENCE ITEMS are included: questions whose answer is verifiably
absent from the subject. The system should visibly decline. Whether it does is
the most important single number in this report.

Isolated: calls the production components directly, bypassing the cache so
nothing is written to query_cache. Read-only against the database.
"""

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from openai import AsyncOpenAI                       # noqa: E402
from engine.config import GROQ_API_KEY, GROQ_BASE_URL  # noqa: E402
from engine.fast_mode import _build_context, _SEARCH_SYSTEM  # noqa: E402
from engine.tools import run_hybrid_search           # noqa: E402
from indexing.database import SessionFactory         # noqa: E402
from indexing.db_chroma import ChromaStore           # noqa: E402
from indexing.embedder import Embedder               # noqa: E402

EVAL = REPO / "eval" / "eval_set.json"
HARD = REPO / "experiments" / "benchmarks" / "hard_eval_set.json"
OUT = REPO / "experiments" / "benchmarks" / "g1_grounding.json"

# Only this model is alive on Groq; the other two in GROQ_MODELS are 404.
MODEL = "openai/gpt-oss-120b"
CONTEXT_MAX_SLIDES = 6
N_ANSWERABLE = 30
N_INSUFFICIENT = 15

STOP = set("""the a an of in on for to and or not is are was were be been being
this that these those it its their there they have has had will would should
can could may might must do does did as at by with from into about which what
how why when where who your you we our us slide slide page chapter figure
also more most such some any each other than then so if but while during
used use using example examples explain explains explained described
""".split())


def content_terms(t):
    return {w for w in re.findall(r"[a-z0-9]+", (t or "").lower())
            if len(w) > 3 and w not in STOP}


CITE_RE = re.compile(r"[Pp]age\s+(\d+)\s+of\s+([^\s,;:)\]]+(?:\.[A-Za-z0-9]+)?)")


def parse_citations(answer):
    """Extract (page, filename-ish) pairs the answer claims to cite."""
    out = []
    for m in CITE_RE.finditer(answer or ""):
        out.append((int(m.group(1)), m.group(2).strip().rstrip(".,;:")))
    return out


async def judge(client, question, reference, answer, context):
    """LLM judge, used ONLY where a mechanical check cannot substitute."""
    sys_p = ("You grade a study assistant's answer. Be strict and terse. "
             "Reply with ONLY a JSON object, no prose.")
    user_p = f"""QUESTION: {question}

REFERENCE ANSWER (ground truth): {reference}

CONTEXT THE ASSISTANT WAS GIVEN:
{context[:4000]}

ASSISTANT'S ANSWER:
{answer[:3000]}

Return JSON with exactly these keys:
"correct": 2 if the answer matches the reference in substance, 1 if partially, 0 if wrong or missing
"grounded": 2 if every factual claim is supported by the context, 1 if mostly, 0 if it asserts things the context does not contain
"unsupported_claims": integer count of specific factual claims not present in the context
"declines": true if the answer states the material does not cover this, false otherwise
"""
    for attempt in range(3):
        try:
            r = await client.chat.completions.create(
                model=MODEL, temperature=0, max_tokens=1400,
                messages=[{"role": "system", "content": sys_p},
                          {"role": "user", "content": user_p}])
            txt = (r.choices[0].message.content or "").strip()
            m = re.search(r"\{.*\}", txt, re.DOTALL)
            if m:
                return json.loads(m.group(0))
        except Exception:
            await asyncio.sleep(1.5 * (attempt + 1))
    return None


async def answer_one(client, question, context):
    user_msg = (f"Subject: ?\nStudent's question: {question}\n\n"
                f"Relevant slides:\n{context}")
    for attempt in range(3):
        try:
            r = await client.chat.completions.create(
                model=MODEL, temperature=0.3, max_tokens=1500,
                messages=[{"role": "system", "content": _SEARCH_SYSTEM},
                          {"role": "user", "content": user_msg}])
            return (r.choices[0].message.content or "").strip()
        except Exception:
            await asyncio.sleep(1.5 * (attempt + 1))
    return ""


async def main():
    eval_set = json.loads(EVAL.read_text(encoding="utf-8"))[:N_ANSWERABLE]
    hard = [it for it in json.loads(HARD.read_text(encoding="utf-8"))
            if it["category"] == "in_subject_absent"][:N_INSUFFICIENT]

    items = ([{"id": f"ans_{q['id']}", "kind": "answerable",
               "question": q["question"], "subject": q["subject"],
               "gold": q["gold_slide_id"], "reference": q["expected_answer"]}
              for q in eval_set]
             + [{"id": it["id"], "kind": "insufficient",
                 "question": it["question"], "subject": it["subject"],
                 "gold": None,
                 "reference": "This topic is not covered in the material."}
                for it in hard])

    print(f"{len(items)} items "
          f"({sum(1 for i in items if i['kind']=='answerable')} answerable, "
          f"{sum(1 for i in items if i['kind']=='insufficient')} insufficient)")
    print(f"model: {MODEL} (the only live model in GROQ_MODELS)\n")

    embedder, chroma = Embedder(), ChromaStore()
    session = SessionFactory()
    client = AsyncOpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)

    rows = []
    try:
        for n, it in enumerate(items, 1):
            slides = run_hybrid_search(it["question"], it["subject"], session,
                                       embedder, chroma, top_k=CONTEXT_MAX_SLIDES)
            context = _build_context(slides)
            ctx_pairs = {(s["page_number"], s["filename"]) for s in slides}
            ctx_pages = {s["page_number"] for s in slides}
            ctx_ids = [s["slide_id"] for s in slides]

            t0 = time.perf_counter()
            ans = await answer_one(client, it["question"], context)
            gen_ms = (time.perf_counter() - t0) * 1000

            cites = parse_citations(ans)
            valid = [c for c in cites if c in ctx_pairs]
            page_ok = [c for c in cites if c[0] in ctx_pages]
            fabricated = [c for c in cites if c[0] not in ctx_pages]

            a_terms = content_terms(ans)
            c_terms = content_terms(context + " " + it["question"])
            ungrounded = sorted(a_terms - c_terms)
            lex_ground = (len(a_terms & c_terms) / len(a_terms)) if a_terms else 1.0

            j = await judge(client, it["question"], it["reference"], ans, context)

            rows.append({
                "id": it["id"], "kind": it["kind"], "subject": it["subject"],
                "question": it["question"],
                "gold_in_context": it["gold"] in ctx_ids if it["gold"] else None,
                "n_context": len(slides),
                "answer_chars": len(ans),
                "n_citations": len(cites),
                "n_valid_citations": len(valid),
                "n_page_only_valid": len(page_ok),
                "n_fabricated_citations": len(fabricated),
                "fabricated": fabricated[:4],
                "cited_gold": (any(s["slide_id"] == it["gold"]
                                   and (s["page_number"], s["filename"]) in cites
                                   for s in slides) if it["gold"] else None),
                "lex_grounding": round(lex_ground, 3),
                "n_ungrounded_terms": len(ungrounded),
                "ungrounded_sample": ungrounded[:8],
                "gen_ms": round(gen_ms),
                "judge": j,
                "answer": ans[:1500],
            })
            if n % 10 == 0:
                print(f"  {n}/{len(items)}", flush=True)
    finally:
        session.close()

    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nsaved {len(rows)} rows -> {OUT}")
    print("run g1b_grounding_report.py for the analysis")


if __name__ == "__main__":
    os.environ["EXAMAI_OBSERVE_RETRIEVAL"] = "0"
    asyncio.run(main())
