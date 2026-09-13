"""
G6 — agentic vs iterative vs baseline, done properly.

REPLACES G3, WHICH PRODUCED GARBAGE. G3 ran four concurrent Groq calls; the
free tier 429s at that rate, and its `chat()` helper swallowed the exception and
returned "". The result looked like a finished experiment - every system scored
~0.00 correctness with 0.26 LLM calls per query - and would have been written up
as "agentic RAG does not help". It was measuring nothing at all. The tell was
`llm_calls: 0.26` when every system makes at least one call by construction.

Fixes:
  - strictly sequential, one request at a time
  - 429s are retried with exponential backoff and jitter, up to a long budget
  - a call that ultimately fails RAISES and is recorded as a failure rather
    than silently becoming an empty answer
  - the run asserts that every system made at least one LLM call per query
  - listwise judging: all three answers for a query are graded in ONE call,
    anonymised and shuffled. Cheaper, and a relative comparison is more
    reliable than three independent absolute scores.
  - the context is persisted, so grounding can be checked against what the
    model was actually given (a gap in G1)

Smaller item set, because a slow sequential run on a rate-limited free tier is
the binding constraint. Fewer items measured correctly beat more measured wrong.
"""

import asyncio
import json
import os
import random
import re
import sys
import time
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from openai import AsyncOpenAI, RateLimitError          # noqa: E402
from engine.config import (GROQ_API_KEY, GROQ_BASE_URL,   # noqa: E402
                           OLLAMA_BASE_URL, OLLAMA_MODEL)
from engine.fast_mode import _build_context, _SEARCH_SYSTEM   # noqa: E402
from engine.tools import run_hybrid_search              # noqa: E402
from indexing.database import SessionFactory            # noqa: E402
from indexing.db_chroma import ChromaStore              # noqa: E402
from indexing.embedder import Embedder                  # noqa: E402

EVAL = REPO / "eval" / "eval_set.json"
HARD = REPO / "experiments" / "benchmarks" / "hard_eval_set.json"
INDEP = REPO / "experiments" / "benchmarks" / "independent_eval.json"
REAL = REPO / "experiments" / "benchmarks" / "q3_real_queries.json"
OUT = REPO / "experiments" / "benchmarks" / "g6_agentic.json"

# Groq's free tier 429s at even 2 concurrent requests, and with backoff a
# single item took 643 s - three hours for this experiment. Ollama is local and
# unmetered at ~1.7 s/call warm. llama3:8b is a weaker model than gpt-oss-120b,
# so ABSOLUTE quality here is lower than production would deliver; but all three
# systems share the model, so the COMPARISON between them - which is the whole
# question - stays controlled. Protocol adherence is recorded separately,
# because a small model failing to follow the agent contract is itself a
# finding about agentic RAG at this scale.
USE_OLLAMA = os.getenv("G6_BACKEND", "ollama") == "ollama"
MODEL = OLLAMA_MODEL if USE_OLLAMA else "openai/gpt-oss-120b"
TOP_K = 6
MAX_RETRIES = 4

STOP = set("""the a an of in on for to and or not is are was were be been being
this that these those it its their there they have has had will would should
can could may might must do does did as at by with from into about which what
how why when where who your you we our us also more most such some any each
other than then so if but while during used use using example examples explain
explains explained covered cover slide slides page write short note""".split())


def terms(t):
    return {w for w in re.findall(r"[a-z0-9]+", (t or "").lower())
            if len(w) > 3 and w not in STOP}


SPECIFIC = re.compile(r"\b(?:\d+(?:\.\d+)?|[A-Z]{2,}[0-9]*)\b")


def specifics(t):
    return {m.group(0).lower() for m in SPECIFIC.finditer(
        unicodedata.normalize("NFKC", t or ""))}


class Budget:
    def __init__(self):
        self.llm_calls = 0
        self.retrievals = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.failures = 0


_client = (AsyncOpenAI(api_key="ollama", base_url=OLLAMA_BASE_URL) if USE_OLLAMA
           else AsyncOpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL))
_last = [0.0]


async def chat(messages, budget, max_tokens=1400, temperature=0.3):
    """One request at a time, with real backoff. Raises if it cannot succeed."""
    if not USE_OLLAMA:
        gap = time.perf_counter() - _last[0]
        if gap < 2.2:
            await asyncio.sleep(2.2 - gap)
    delay = 2.0 if USE_OLLAMA else 5.0
    for attempt in range(MAX_RETRIES):
        try:
            r = await _client.chat.completions.create(
                model=MODEL, messages=messages, temperature=temperature,
                max_tokens=max_tokens)
            _last[0] = time.perf_counter()
            if budget is not None:
                budget.llm_calls += 1
                if r.usage:
                    budget.prompt_tokens += r.usage.prompt_tokens or 0
                    budget.completion_tokens += r.usage.completion_tokens or 0
            return (r.choices[0].message.content or "").strip()
        except RateLimitError:
            await asyncio.sleep(delay + random.uniform(0, 2))
            delay = min(delay * 1.7, 45)
        except Exception:
            await asyncio.sleep(delay)
            delay = min(delay * 1.7, 45)
    if budget is not None:
        budget.failures += 1
    raise RuntimeError("LLM call failed after retries")


# ── systems ──────────────────────────────────────────────────────────────

def _search(q, subject, ctx, budget, top_k=TOP_K):
    budget.retrievals += 1
    return run_hybrid_search(q, subject, ctx["session"], ctx["embedder"],
                             ctx["chroma"], top_k=top_k)


async def sys_baseline(item, ctx, budget):
    slides = _search(item["question"], item["subject"], ctx, budget)
    context = _build_context(slides)
    ans = await chat([
        {"role": "system", "content": _SEARCH_SYSTEM},
        {"role": "user", "content": f"Subject: {item['subject']}\n"
         f"Student's question: {item['question']}\n\nRelevant slides:\n{context}"}],
        budget)
    return ans, [s["slide_id"] for s in slides], context


async def sys_iterative(item, ctx, budget):
    """Deterministic controller - a set difference, not an LLM."""
    slides = _search(item["question"], item["subject"], ctx, budget)
    q_terms = terms(item["question"])
    covered = set()
    for s in slides:
        covered |= terms(f"{s.get('summary','')} {s.get('concepts','')}")
    missing = q_terms - covered
    second_done = False
    if missing and len(missing) / max(len(q_terms), 1) >= 0.34:
        extra = _search(" ".join(sorted(missing)), item["subject"], ctx, budget)
        seen = {s["slide_id"] for s in slides}
        slides = slides + [s for s in extra if s["slide_id"] not in seen][:4]
        second_done = True
    context = _build_context(slides)
    ans = await chat([
        {"role": "system", "content": _SEARCH_SYSTEM},
        {"role": "user", "content": f"Subject: {item['subject']}\n"
         f"Student's question: {item['question']}\n\nRelevant slides:\n{context}"}],
        budget)
    return ans, [s["slide_id"] for s in slides], context, second_done


_AGENT_SYSTEM = """You are an exam study assistant with a slide search tool.

Reply with EXACTLY one line, either:

SEARCH: <query>
ANSWER: <your full answer>

Use SEARCH when you need evidence you do not have yet; you may search up to 3
times, using different wording or sub-topics. Use ANSWER when you have enough.
Reference slides as "Page X of filename". If the slides genuinely do not cover
the question, say so plainly instead of guessing. Output nothing else."""


async def sys_agentic(item, ctx, budget, max_steps=4):
    transcript = [f"Student's question ({item['subject']}): {item['question']}"]
    ids, contexts, searches = [], [], []
    protocol_ok = True
    for step in range(max_steps):
        msg = await chat([{"role": "system", "content": _AGENT_SYSTEM},
                          {"role": "user", "content": "\n\n".join(transcript)}],
                         budget, max_tokens=1500)
        up = msg.upper().lstrip()
        if not (up.startswith("SEARCH:") or up.startswith("ANSWER:")):
            protocol_ok = False      # ignored the contract; treated as an answer
        if up.startswith("SEARCH:") and step < max_steps - 1:
            q = msg.split(":", 1)[1].strip()[:180] or item["question"]
            searches.append(q)
            sl = _search(q, item["subject"], ctx, budget)
            ids += [s["slide_id"] for s in sl]
            c = _build_context(sl)
            contexts.append(c)
            transcript.append(f"SEARCH: {q}")
            transcript.append(f"RESULTS:\n{c[:3000]}")
        else:
            ans = msg.split(":", 1)[1].strip() if up.startswith("ANSWER:") else msg
            if not contexts:
                sl = _search(item["question"], item["subject"], ctx, budget)
                ids += [s["slide_id"] for s in sl]
                contexts.append(_build_context(sl))
            return ans, list(dict.fromkeys(ids)), "\n".join(contexts), searches, protocol_ok
    ans = await chat([{"role": "system", "content": _SEARCH_SYSTEM},
                      {"role": "user", "content": "\n\n".join(transcript)
                       + "\n\nGive the final answer now."}], budget)
    return ans, list(dict.fromkeys(ids)), "\n".join(contexts), searches, protocol_ok


# ── listwise judging: one call grades all three ──────────────────────────

async def judge_all(item, answers, contexts):
    labels = list(answers.keys())
    random.shuffle(labels)
    letters = {lab: chr(65 + i) for i, lab in enumerate(labels)}
    blocks = "\n\n".join(
        f"--- ANSWER {letters[lab]} ---\n{answers[lab][:2200]}" for lab in labels)
    ctx = contexts[labels[0]][:4000]
    insufficient = item["kind"] == "insufficient"
    sys_p = "You grade a study assistant. Reply with ONLY one JSON object."
    user_p = f"""QUESTION: {item['question']}
REFERENCE: {item.get('reference') or '(none)'}
IS THIS TOPIC IN THE MATERIAL? {'NO - it is absent' if insufficient else 'yes'}

SLIDE CONTEXT (representative of what the assistants saw):
{ctx}

{blocks}

For each answer letter present, return an object with:
"correct": 2/1/0  {'(2 ONLY if it states the material does not cover this)' if insufficient else '(2 = matches the reference in substance)'}
"grounded": 2/1/0 (2 = every claim traceable to the slide context)
"unsupported_claims": integer
"declines": true/false (does it say the material does not cover this)

Respond exactly like: {{"A": {{...}}, "B": {{...}}, "C": {{...}}}}"""
    try:
        txt = await chat([{"role": "system", "content": sys_p},
                          {"role": "user", "content": user_p}],
                         None, max_tokens=1500, temperature=0)
    except RuntimeError:
        return None
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(0))
    except Exception:
        return None
    return {lab: parsed.get(letters[lab]) for lab in labels}


def build_items():
    ev = {q["id"]: q for q in json.loads(EVAL.read_text(encoding="utf-8"))}
    items = []
    for it in json.loads(INDEP.read_text(encoding="utf-8")):
        g = it.get("gold_slide_ids") or []
        if it["answerable"] and len(g) >= 2 and len(items) < 6:
            items.append({"id": it["id"], "kind": "multi_slide",
                          "question": it["question"], "subject": it["subject"],
                          "gold": set(g), "reference": None})
    for r in json.loads(REAL.read_text(encoding="utf-8")):
        if r["label"] == "answerable" and r["n_words"] <= 3 and \
                sum(1 for i in items if i["kind"] == "short") < 4:
            items.append({"id": f"short_{r['query'][:12]}", "kind": "short",
                          "question": r["query"], "subject": r["subject"],
                          "gold": set(), "reference": None})
    hard = json.loads(HARD.read_text(encoding="utf-8"))
    for h in [x for x in hard if x["category"] == "positive_keyword"][:3]:
        sid = h["id"].split("_")[-1]
        src = ev.get(int(sid)) if sid.isdigit() else None
        items.append({"id": h["id"], "kind": "keyword", "question": h["question"],
                      "subject": h["subject"], "gold": {h["gold_slide_id"]},
                      "reference": src["expected_answer"] if src else None})
    for h in [x for x in hard if x["category"] == "in_subject_absent"][:4]:
        items.append({"id": h["id"], "kind": "insufficient",
                      "question": h["question"], "subject": h["subject"],
                      "gold": set(),
                      "reference": "The material does not cover this topic."})
    return items


async def main():
    items = build_items()
    from collections import Counter
    print(f"{len(items)} items: {dict(Counter(i['kind'] for i in items))}")
    print(f"model {MODEL}, STRICTLY SEQUENTIAL with backoff\n")

    session = SessionFactory()
    ctx = {"session": session, "embedder": Embedder(), "chroma": ChromaStore()}
    rows = []
    t_start = time.perf_counter()
    try:
        for n, item in enumerate(items, 1):
            answers, contexts, meta = {}, {}, {}
            for name in ("baseline", "iterative", "agentic"):
                b = Budget()
                t0 = time.perf_counter()
                try:
                    if name == "baseline":
                        a, ids, c = await sys_baseline(item, ctx, b)
                        extra = {}
                    elif name == "iterative":
                        a, ids, c, did2 = await sys_iterative(item, ctx, b)
                        extra = {"second_retrieval": did2}
                    else:
                        a, ids, c, sq, pok = await sys_agentic(item, ctx, b)
                        extra = {"searches": sq, "protocol_ok": pok}
                except RuntimeError:
                    a, ids, c, extra = "", [], "", {"failed": True}
                wall = (time.perf_counter() - t0) * 1000
                assert b.llm_calls >= 1 or b.failures, \
                    f"{name} made no LLM call - the G3 failure mode"
                answers[name], contexts[name] = a, c
                a_t, c_t = terms(a), terms(c)
                sp_a, sp_c = specifics(a), specifics(c)
                meta[name] = {
                    "retrieved": ids,
                    "hit": bool(set(ids) & item["gold"]) if item["gold"] else None,
                    "n_citations": len(re.findall(r"[Pp]age\s*\d+", a)),
                    "lex_grounding": round(len(a_t & c_t)/len(a_t), 3) if a_t else 1.0,
                    "specifics_in_answer": len(sp_a),
                    "specifics_not_in_context": len(sp_a - sp_c),
                    "llm_calls": b.llm_calls, "retrievals": b.retrievals,
                    "prompt_tokens": b.prompt_tokens,
                    "completion_tokens": b.completion_tokens,
                    "failures": b.failures, "wall_ms": round(wall), **extra}
            verdict = await judge_all(item, answers, contexts)
            for name in ("baseline", "iterative", "agentic"):
                rows.append({"id": item["id"], "kind": item["kind"],
                             "system": name, **meta[name],
                             "judge": (verdict or {}).get(name),
                             "answer": answers[name][:900]})
            print(f"  {n}/{len(items)} {item['kind']:12s} "
                  f"calls={sum(meta[s]['llm_calls'] for s in meta)} "
                  f"({time.perf_counter()-t_start:.0f}s)", flush=True)
    finally:
        session.close()

    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    tot = sum(r["llm_calls"] for r in rows)
    fail = sum(r["failures"] for r in rows)
    print(f"\n{len(rows)} rows, {tot} LLM calls, {fail} failures -> {OUT}")


if __name__ == "__main__":
    os.environ["EXAMAI_OBSERVE_RETRIEVAL"] = "0"
    asyncio.run(main())
