"""
G3 — does agentic or iterative retrieval beat the one-shot baseline, and is it
worth what it costs?

Three systems on identical hard queries, with identical judging:

  BASELINE      retrieve top-6 -> context -> answer.            1 LLM call
  ITERATIVE     retrieve -> CHEAP DETERMINISTIC sufficiency     1-2 LLM calls
                check -> if the evidence misses query terms,
                re-retrieve using the missing terms -> merge
                -> answer. No LLM in the control loop.
  AGENTIC       an LLM with a search tool decides what to look   2-5 LLM calls
                for, inspects results, searches again, then
                answers.

The ordering is deliberate. WS4 asks whether the simple mechanism captures the
benefit before a full agent is built, and WS10 asks whether a sufficiency
verifier has to be an LLM. ITERATIVE answers both: its controller is a set
intersection, costing microseconds, and if it matches AGENTIC then the agent's
orchestration is buying nothing.

Difficult queries only - there is no point measuring these on questions the
baseline already answers:

  multi_slide    real multi-part PYQ exam questions with 2+ gold slides
  short          1-3 word real queries, where R@1 is 0.10-0.20
  keyword        keyword-style phrasings
  weak_lexical   questions whose gold slide BM25 alone cannot find
  insufficient   answers verifiably absent from the subject

Cost is measured, not estimated: LLM calls, retrieval calls, prompt/completion
tokens and wall-clock per query.

Isolated. No production code path is modified and the cache is bypassed.
"""

import asyncio
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from openai import AsyncOpenAI                          # noqa: E402
from engine.config import GROQ_API_KEY, GROQ_BASE_URL   # noqa: E402
from engine.fast_mode import _build_context, _SEARCH_SYSTEM   # noqa: E402
from engine.tools import run_hybrid_search, _tokenize   # noqa: E402
from indexing.database import SessionFactory            # noqa: E402
from indexing.db_chroma import ChromaStore              # noqa: E402
from indexing.embedder import Embedder                  # noqa: E402

EVAL = REPO / "eval" / "eval_set.json"
HARD = REPO / "experiments" / "benchmarks" / "hard_eval_set.json"
INDEP = REPO / "experiments" / "benchmarks" / "independent_eval.json"
REAL = REPO / "experiments" / "benchmarks" / "q3_real_queries.json"
OUT = REPO / "experiments" / "benchmarks" / "g3_agentic.json"

MODEL = "openai/gpt-oss-120b"
CONCURRENCY = 4
TOP_K = 6

STOP = set("""the a an of in on for to and or not is are was were be been being
this that these those it its their there they have has had will would should
can could may might must do does did as at by with from into about which what
how why when where who your you we our us also more most such some any each
other than then so if but while during used use using example examples
explain explains explained covered cover slide slides page write short note
""".split())


def terms(t):
    return {w for w in re.findall(r"[a-z0-9]+", (t or "").lower())
            if len(w) > 3 and w not in STOP}


class Usage:
    def __init__(self):
        self.llm_calls = 0
        self.retrievals = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0


async def chat(client, messages, usage, max_tokens=1500, temperature=0.3):
    for attempt in range(3):
        try:
            r = await client.chat.completions.create(
                model=MODEL, messages=messages, temperature=temperature,
                max_tokens=max_tokens)
            usage.llm_calls += 1
            if r.usage:
                usage.prompt_tokens += r.usage.prompt_tokens or 0
                usage.completion_tokens += r.usage.completion_tokens or 0
            return (r.choices[0].message.content or "").strip()
        except Exception:
            await asyncio.sleep(2 * (attempt + 1))
    return ""


# ── the three systems ────────────────────────────────────────────────────

def _search(q, subject, ctx, top_k=TOP_K):
    ctx["usage"].retrievals += 1
    return run_hybrid_search(q, subject, ctx["session"], ctx["embedder"],
                             ctx["chroma"], top_k=top_k)


async def sys_baseline(client, item, ctx):
    slides = _search(item["question"], item["subject"], ctx)
    context = _build_context(slides)
    ans = await chat(client, [
        {"role": "system", "content": _SEARCH_SYSTEM},
        {"role": "user", "content": f"Subject: {item['subject']}\n"
                                    f"Student's question: {item['question']}\n\n"
                                    f"Relevant slides:\n{context}"}],
        ctx["usage"])
    return ans, [s["slide_id"] for s in slides], context


async def sys_iterative(client, item, ctx):
    """Deterministic controller: no LLM decides whether to search again."""
    slides = _search(item["question"], item["subject"], ctx)
    q_terms = terms(item["question"])
    covered = set()
    for s in slides:
        covered |= terms(f"{s.get('summary','')} {s.get('concepts','')}")
    missing = q_terms - covered

    # Re-retrieve only when the first pass left query concepts unaddressed.
    # The threshold is deliberately crude - the question is whether ANY cheap
    # controller helps, not whether this exact one is tuned.
    if missing and len(missing) / max(len(q_terms), 1) >= 0.34:
        second = _search(" ".join(sorted(missing)), item["subject"], ctx)
        seen = {s["slide_id"] for s in slides}
        slides = slides + [s for s in second if s["slide_id"] not in seen][:4]

    context = _build_context(slides)
    ans = await chat(client, [
        {"role": "system", "content": _SEARCH_SYSTEM},
        {"role": "user", "content": f"Subject: {item['subject']}\n"
                                    f"Student's question: {item['question']}\n\n"
                                    f"Relevant slides:\n{context}"}],
        ctx["usage"])
    return ans, [s["slide_id"] for s in slides], context


_AGENT_SYSTEM = """You are an exam study assistant with a slide search tool.

Work in steps. On each step reply with EXACTLY one of:

SEARCH: <query>
  to search the student's slides. Use this when you need evidence you do not
  yet have. You may search up to 3 times with different wording or sub-topics.

ANSWER: <your answer>
  to give the final answer. Reference slides as "Page X of filename".
  If the retrieved slides genuinely do not cover the question, say so plainly
  in the answer instead of guessing.

Reply with nothing else. Do not explain your choice."""


async def sys_agentic(client, item, ctx, max_steps=4):
    transcript = [f"Student's question ({item['subject']}): {item['question']}"]
    all_ids, contexts = [], []
    for step in range(max_steps):
        msg = await chat(client, [
            {"role": "system", "content": _AGENT_SYSTEM},
            {"role": "user", "content": "\n\n".join(transcript)}],
            ctx["usage"], max_tokens=1600)
        if msg.upper().startswith("SEARCH:") and step < max_steps - 1:
            q = msg.split(":", 1)[1].strip()[:200] or item["question"]
            slides = _search(q, item["subject"], ctx)
            all_ids += [s["slide_id"] for s in slides]
            c = _build_context(slides)
            contexts.append(c)
            transcript.append(f"SEARCH: {q}")
            transcript.append(f"RESULTS:\n{c[:3500]}")
        else:
            ans = msg.split(":", 1)[1].strip() if msg.upper().startswith("ANSWER:") else msg
            if not contexts:                     # answered without searching
                slides = _search(item["question"], item["subject"], ctx)
                all_ids += [s["slide_id"] for s in slides]
                contexts.append(_build_context(slides))
            return ans, list(dict.fromkeys(all_ids)), "\n".join(contexts)

    # ran out of steps: force an answer on what it has
    ans = await chat(client, [
        {"role": "system", "content": _SEARCH_SYSTEM},
        {"role": "user", "content": "\n\n".join(transcript)
                                    + "\n\nGive the final answer now."}],
        ctx["usage"])
    return ans, list(dict.fromkeys(all_ids)), "\n".join(contexts)


SYSTEMS = {"baseline": sys_baseline, "iterative": sys_iterative,
           "agentic": sys_agentic}


# ── judging ──────────────────────────────────────────────────────────────

async def judge(client, item, answer, context, usage):
    sys_p = "You grade a study assistant. Reply with ONLY a JSON object."
    ref = item.get("reference") or "(no reference available)"
    user_p = f"""QUESTION: {item['question']}
REFERENCE ANSWER: {ref}
IS THE ANSWER PRESENT IN THE MATERIAL? {"no - the material does not cover this" if item['kind']=='insufficient' else "yes"}

CONTEXT GIVEN TO THE ASSISTANT:
{context[:4500]}

ASSISTANT'S ANSWER:
{answer[:2500]}

JSON keys:
"correct": 2 full, 1 partial, 0 wrong/missing (for an uncovered topic, correct=2 ONLY if it says the material does not cover it)
"grounded": 2 every claim supported by context, 1 mostly, 0 asserts things absent from context
"unsupported_claims": integer
"declines": true if it states the material does not cover this"""
    for attempt in range(3):
        try:
            r = await client.chat.completions.create(
                model=MODEL, temperature=0, max_tokens=1200,
                messages=[{"role": "system", "content": sys_p},
                          {"role": "user", "content": user_p}])
            usage.llm_calls += 0     # judging is not charged to the system
            m = re.search(r"\{.*\}", r.choices[0].message.content or "", re.DOTALL)
            if m:
                return json.loads(m.group(0))
        except Exception:
            await asyncio.sleep(2 * (attempt + 1))
    return None


CITE_RE = re.compile(r"[Pp]age\s+(\d+)\s+of\s+([^\s,;:)\]]+)")


def build_items():
    ev = {q["id"]: q for q in json.loads(EVAL.read_text(encoding="utf-8"))}
    items = []

    ind = json.loads(INDEP.read_text(encoding="utf-8"))
    for it in ind:
        gold = it.get("gold_slide_ids") or []
        if it["answerable"] and len(gold) >= 2:
            items.append({"id": it["id"], "kind": "multi_slide",
                          "question": it["question"], "subject": it["subject"],
                          "gold": set(gold), "reference": None})

    real = json.loads(REAL.read_text(encoding="utf-8"))
    for r in real:
        if r["label"] == "answerable" and r["n_words"] <= 3:
            items.append({"id": f"short_{r['query'][:14]}", "kind": "short",
                          "question": r["query"], "subject": r["subject"],
                          "gold": set(), "reference": None})

    hard = json.loads(HARD.read_text(encoding="utf-8"))
    kw = [h for h in hard if h["category"] == "positive_keyword"][:6]
    for h in kw:
        src = ev.get(int(h["id"].split("_")[-1])) if h["id"].split("_")[-1].isdigit() else None
        items.append({"id": h["id"], "kind": "keyword", "question": h["question"],
                      "subject": h["subject"], "gold": {h["gold_slide_id"]},
                      "reference": src["expected_answer"] if src else None})

    absent = [h for h in hard if h["category"] == "in_subject_absent"][:8]
    for h in absent:
        items.append({"id": h["id"], "kind": "insufficient",
                      "question": h["question"], "subject": h["subject"],
                      "gold": set(),
                      "reference": "The material does not cover this topic."})
    return items


async def run_one(client, sem, item, sysname, fn, ctx):
    async with sem:
        u = Usage()
        local = dict(ctx)
        local["usage"] = u
        t0 = time.perf_counter()
        ans, ids, context = await fn(client, item, local)
        wall = (time.perf_counter() - t0) * 1000
        j = await judge(client, item, ans, context, u)
        cites = [(int(a), b.rstrip(".,;:")) for a, b in CITE_RE.findall(ans or "")]
        a_t, c_t = terms(ans), terms(context + " " + item["question"])
        return {
            "id": item["id"], "kind": item["kind"], "system": sysname,
            "retrieved": ids,
            "hit": bool(set(ids) & item["gold"]) if item["gold"] else None,
            "hit_at_5": bool(set(ids[:5]) & item["gold"]) if item["gold"] else None,
            "n_citations": len(cites),
            "lex_grounding": round(len(a_t & c_t) / len(a_t), 3) if a_t else 1.0,
            "llm_calls": u.llm_calls, "retrievals": u.retrievals,
            "prompt_tokens": u.prompt_tokens,
            "completion_tokens": u.completion_tokens,
            "wall_ms": round(wall), "judge": j, "answer": (ans or "")[:900],
        }


async def main():
    items = build_items()
    from collections import Counter
    print(f"{len(items)} hard items: {dict(Counter(i['kind'] for i in items))}")
    print(f"model {MODEL}, concurrency {CONCURRENCY}\n")

    session = SessionFactory()
    ctx = {"session": session, "embedder": Embedder(), "chroma": ChromaStore()}
    client = AsyncOpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
    sem = asyncio.Semaphore(CONCURRENCY)

    rows = []
    try:
        for sysname, fn in SYSTEMS.items():
            t0 = time.perf_counter()
            got = await asyncio.gather(*[
                run_one(client, sem, it, sysname, fn, ctx) for it in items])
            rows += got
            print(f"  {sysname:10s} done in {time.perf_counter()-t0:.0f}s")
    finally:
        session.close()

    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nsaved {len(rows)} rows -> {OUT}")


if __name__ == "__main__":
    os.environ["EXAMAI_OBSERVE_RETRIEVAL"] = "0"
    asyncio.run(main())
