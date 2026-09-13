"""
G7 — was the agent's honesty from the architecture, or from one sentence?

G6 found the agentic system decisively better at ONE thing and worse at
everything else:

                    correct  grounded  declines on absent topics  tokens
    baseline          1.53     2.00           0/4  (0%)            1.00x
    iterative         1.47     1.94           0/4  (0%)            1.19x
    agentic           0.94     0.94           3/4 (75%)            2.36x

The obvious reading is that inspecting evidence across multiple turns lets the
agent notice when it has nothing. But the comparison is CONFOUNDED, and the
confound is mine: the agent runs on `_AGENT_SYSTEM`, which contains

    "If the slides genuinely do not cover the question, say so plainly
     instead of guessing."

while the baseline runs on the production `_SEARCH_SYSTEM`, which contains

    "Speak with authority as if you studied the material yourself"

and no permission to decline at all. So the agent had an instruction the
baseline was denied, and attributing the difference to the architecture would
be wrong.

This runs the baseline architecture - ONE retrieval, ONE LLM call - with the
production prompt plus a single added sentence granting permission to decline.
Nothing else changes.

If it matches the agent's decline rate, the benefit costs one sentence rather
than 2.36x the tokens, and "agentic RAG helps with not-found" is false.

Same 17 items, same model, same judge protocol as G6.
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

from openai import AsyncOpenAI                              # noqa: E402
from engine.config import OLLAMA_BASE_URL, OLLAMA_MODEL     # noqa: E402
from engine.fast_mode import _build_context, _SEARCH_SYSTEM  # noqa: E402
from engine.tools import run_hybrid_search                  # noqa: E402
from indexing.database import SessionFactory                # noqa: E402
from indexing.db_chroma import ChromaStore                  # noqa: E402
from indexing.embedder import Embedder                      # noqa: E402

sys.path.insert(0, str(REPO / "experiments" / "rag"))
from g6_agentic_v2 import build_items, terms, specifics     # noqa: E402

OUT = REPO / "experiments" / "benchmarks" / "g7_decline.json"
MODEL = OLLAMA_MODEL
TOP_K = 6

# The entire intervention: one sentence appended to the production prompt.
DECLINE_LINE = ("- If the slides above do not actually cover the question, say "
                "so plainly and name the closest topic that IS covered. Do not "
                "fill gaps from general knowledge.\n")

PROMPTS = {
    "production": _SEARCH_SYSTEM,
    "production+decline": _SEARCH_SYSTEM.rstrip() + "\n" + DECLINE_LINE,
}

_client = AsyncOpenAI(api_key="ollama", base_url=OLLAMA_BASE_URL)


async def chat(messages, max_tokens=1400, temperature=0.3):
    delay = 2.0
    for _ in range(4):
        try:
            r = await _client.chat.completions.create(
                model=MODEL, messages=messages, temperature=temperature,
                max_tokens=max_tokens)
            return ((r.choices[0].message.content or "").strip(),
                    (r.usage.prompt_tokens if r.usage else 0),
                    (r.usage.completion_tokens if r.usage else 0))
        except Exception:
            await asyncio.sleep(delay)
            delay *= 1.7
    raise RuntimeError("LLM call failed")


async def judge_pair(item, answers, context):
    labels = list(answers)
    letters = {lab: chr(65 + i) for i, lab in enumerate(labels)}
    blocks = "\n\n".join(f"--- ANSWER {letters[l]} ---\n{answers[l][:2000]}"
                         for l in labels)
    insufficient = item["kind"] == "insufficient"
    user_p = f"""QUESTION: {item['question']}
REFERENCE: {item.get('reference') or '(none)'}
IS THIS TOPIC IN THE MATERIAL? {'NO - it is absent' if insufficient else 'yes'}

SLIDE CONTEXT:
{context[:3500]}

{blocks}

For each answer letter return:
"correct": 2/1/0 {'(2 ONLY if it states the material does not cover this)' if insufficient else ''}
"grounded": 2/1/0
"unsupported_claims": integer
"declines": true/false

Respond exactly like: {{"A": {{...}}, "B": {{...}}}}"""
    try:
        txt, _, _ = await chat(
            [{"role": "system", "content": "Reply with ONLY one JSON object."},
             {"role": "user", "content": user_p}], max_tokens=900, temperature=0)
    except RuntimeError:
        return None
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        return None
    try:
        p = json.loads(m.group(0))
    except Exception:
        return None
    return {l: p.get(letters[l]) for l in labels}


async def main():
    items = build_items()
    from collections import Counter
    print(f"{len(items)} items: {dict(Counter(i['kind'] for i in items))}")
    print(f"model {MODEL}; identical architecture, prompt differs by one line\n")

    session = SessionFactory()
    embedder, chroma = Embedder(), ChromaStore()
    rows = []
    try:
        for n, item in enumerate(items, 1):
            slides = run_hybrid_search(item["question"], item["subject"],
                                       session, embedder, chroma, top_k=TOP_K)
            context = _build_context(slides)
            ids = [s["slide_id"] for s in slides]
            answers, meta = {}, {}
            for pname, prompt in PROMPTS.items():
                t0 = time.perf_counter()
                ans, pt, ct = await chat([
                    {"role": "system", "content": prompt},
                    {"role": "user", "content":
                        f"Subject: {item['subject']}\n"
                        f"Student's question: {item['question']}\n\n"
                        f"Relevant slides:\n{context}"}])
                wall = (time.perf_counter() - t0) * 1000
                a_t, c_t = terms(ans), terms(context)
                sp_a, sp_c = specifics(ans), specifics(context)
                answers[pname] = ans
                meta[pname] = {
                    "n_citations": len(re.findall(r"[Pp]age\s*\d+", ans)),
                    "lex_grounding": round(len(a_t & c_t)/len(a_t), 3) if a_t else 1.0,
                    "specifics_not_in_context": len(sp_a - sp_c),
                    "prompt_tokens": pt, "completion_tokens": ct,
                    "wall_ms": round(wall), "answer_chars": len(ans)}
            verdict = await judge_pair(item, answers, context)
            for pname in PROMPTS:
                rows.append({"id": item["id"], "kind": item["kind"],
                             "prompt": pname, "retrieved": ids,
                             "hit": bool(set(ids) & item["gold"]) if item["gold"] else None,
                             **meta[pname], "judge": (verdict or {}).get(pname),
                             "answer": answers[pname][:800]})
            print(f"  {n}/{len(items)} {item['kind']}", flush=True)
    finally:
        session.close()

    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    # ── report ───────────────────────────────────────────────────────────
    import statistics
    from collections import defaultdict
    by = defaultdict(list)
    for r in rows:
        by[r["prompt"]].append(r)

    def jv(r, k):
        j = r.get("judge") or {}
        v = j.get(k, 0)
        return v if isinstance(v, (int, float)) else 0

    print("\n" + "=" * 84)
    print("ONE SENTENCE vs THE AGENT LOOP")
    print("=" * 84)
    print(f"{'variant':22s} {'correct':>8s} {'grounded':>9s} {'citations':>10s} "
          f"{'tokens':>8s} {'ms':>7s}")
    for p in PROMPTS:
        g = by[p]
        print(f"{p:22s} {statistics.mean([jv(r,'correct') for r in g]):>8.2f} "
              f"{statistics.mean([jv(r,'grounded') for r in g]):>9.2f} "
              f"{statistics.mean([r['n_citations'] for r in g]):>10.1f} "
              f"{statistics.mean([r['prompt_tokens']+r['completion_tokens'] for r in g]):>8.0f} "
              f"{statistics.median([r['wall_ms'] for r in g]):>7.0f}")
    print(f"{'agentic (from G6)':22s} {0.94:>8.2f} {0.94:>9.2f} {0.1:>10.1f} "
          f"{2946:>8.0f} {7543:>7.0f}")

    print("\n" + "=" * 84)
    print("DECLINE RATE ON TOPICS THE MATERIAL DOES NOT COVER")
    print("=" * 84)
    for p in PROMPTS:
        g = [r for r in by[p] if r["kind"] == "insufficient"]
        if not g:
            continue
        d = sum(1 for r in g if (r.get("judge") or {}).get("declines"))
        c = sum(r["n_citations"] for r in g)
        print(f"  {p:22s} {d}/{len(g)} = {d/len(g):>4.0%}   "
              f"citations emitted: {c}")
    print(f"  {'agentic (from G6)':22s} 3/4 =  75%   citations emitted: 0")

    print("\n" + "=" * 84)
    print("DOES THE ADDED LINE HURT ANSWERABLE QUESTIONS?")
    print("=" * 84)
    print(f"{'variant':22s} {'n':>3s} {'correct':>8s} {'grounded':>9s} {'citations':>10s}")
    for p in PROMPTS:
        g = [r for r in by[p] if r["kind"] != "insufficient"]
        print(f"{p:22s} {len(g):>3d} "
              f"{statistics.mean([jv(r,'correct') for r in g]):>8.2f} "
              f"{statistics.mean([jv(r,'grounded') for r in g]):>9.2f} "
              f"{statistics.mean([r['n_citations'] for r in g]):>10.1f}")

    base = {r["id"]: r for r in by["production"]}
    better = worse = tied = 0
    for r in by["production+decline"]:
        d = jv(r, "correct") - jv(base[r["id"]], "correct")
        better += d > 0
        worse += d < 0
        tied += d == 0
    print(f"\n  paired: {better} better, {worse} worse, {tied} tied")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    os.environ["EXAMAI_OBSERVE_RETRIEVAL"] = "0"
    asyncio.run(main())
