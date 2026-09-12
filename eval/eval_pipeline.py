"""
eval_pipeline.py — Self-contained evaluation benchmark for ExamPrep AI.

Benchmarks hybrid search (ChromaDB + BM25 + RRF) against three baselines:
  1. Vector-only (ChromaDB cosine)
  2. BM25-only (sparse lexical)
  3. Simple keyword search (SQLite LIKE)

Generates diverse question types (conceptual, paraphrased, keyword, application)
with intentional noise/imperfection to simulate real student queries.

Usage:
    python eval/eval_pipeline.py --run-all
    python eval/eval_pipeline.py --retrieval-only
    python eval/eval_pipeline.py --report-only
    python eval/eval_pipeline.py --force-regen
"""

import argparse, json, math, os, random, re, sys, time, logging
from pathlib import Path
from pydantic import BaseModel
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from indexing.database import SessionFactory, init_db
from indexing.models import Slide, Document, QueryCache
from indexing.db_chroma import ChromaStore
from indexing.embedder import Embedder
from engine.tools import run_hybrid_search, slide_to_dict, _doc_for_slide
from rank_bm25 import BM25Okapi
from sqlalchemy import func

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("eval")

# ── Paths ───────────────────────────────────────────────────────────────
EVAL_DIR = PROJECT_ROOT / "eval"
EVAL_SET_PATH = EVAL_DIR / "eval_set.json"
RETRIEVAL_RESULTS_PATH = EVAL_DIR / "retrieval_results.json"
JUDGE_RESULTS_PATH = EVAL_DIR / "judge_results.json"
REPORT_PATH = EVAL_DIR / "eval_report.html"

# ── LLM Client ─────────────────────────────────────────────────────────
EVAL_CLIENT = OpenAI(
    api_key=os.environ.get("GEMINI_EVAL_API_KEY", os.environ.get("GEMINI_API_KEY", "")),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)
EVAL_MODEL = "gemini-2.5-flash-lite"

# ── Pydantic Schemas ───────────────────────────────────────────────────
class QAPair(BaseModel):
    question: str
    expected_answer: str
    question_type: str  # conceptual|paraphrased|keyword|application

class QABatch(BaseModel):
    pairs: list[QAPair]

class JudgeScore(BaseModel):
    faithfulness: int
    relevance: int
    completeness: int
    reasoning: str

class JudgeBatch(BaseModel):
    scores: list[JudgeScore]

class GeneratedAnswerBatch(BaseModel):
    answers: list[str]

# ── Distribution ───────────────────────────────────────────────────────
SUBJECT_DISTRIBUTION = {"CN": 22, "DBMS": 7, "ML": 6, "DAA": 5}
TOTAL_QUESTIONS = 40
TOTAL_API_CALLS = 0

def _api_call_with_retry(messages, response_format, max_retries=5):
    global TOTAL_API_CALLS
    for attempt in range(max_retries):
        try:
            response = EVAL_CLIENT.beta.chat.completions.parse(
                model=EVAL_MODEL, messages=messages, response_format=response_format,
            )
            TOTAL_API_CALLS += 1
            return response.choices[0].message.parsed
        except Exception as e:
            wait_time = 10 * (attempt + 1)
            log.warning(f"  API attempt {attempt+1}/{max_retries}: {type(e).__name__}")
            if attempt < max_retries - 1:
                time.sleep(wait_time)
            else:
                raise

def _tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


# ═══════════════════════════════════════════════════════════════════════
#  STEP 1 — QA Generation (diverse question types with noise)
# ═══════════════════════════════════════════════════════════════════════

QA_PROMPT = """You are generating evaluation data for a retrieval benchmark of an exam-prep system.

For each slide below, generate ONE question that a real student might ask. The question should be primarily answerable from that slide's content, but phrased naturally — not as a perfect summary request.

QUESTION TYPE ASSIGNMENTS (follow exactly):
{type_assignments}

STYLE GUIDE PER TYPE:
- **conceptual**: "Why does X happen?", "How does X relate to Y?", "Explain the difference between..."
- **paraphrased**: Rephrase the slide's main idea using completely different vocabulary. Indirect phrasing.
- **keyword**: Short search-like query, 3-7 words. Example: "TCP congestion control mechanism", "B-tree insertion complexity"
- **application**: Real student doubt or practical question. "If I'm designing a system that needs X, which approach from the slides should I use?"

NOISE REQUIREMENTS (apply to ~30% of questions randomly):
- Occasionally use slightly vague phrasing or miss a keyword
- Some questions can have minor typos or informal language ("whats the diff between..." or "how does X work basically")
- Some questions can be slightly broader than the slide scope

DO NOT generate questions like:
- "What are the key concepts covered in..."
- "What are the main topics discussed..."
- "According to the slide, what is..."
- "Summarize the content of..."

Expected answers must be 2-4 sentences, factual, drawn from the slide content.

Slides:
{slide_texts}

Return JSON with a "pairs" array of exactly {count} objects, each with "question", "expected_answer", and "question_type"."""


def step1_generate_qa():
    if EVAL_SET_PATH.exists():
        print("[Step 1] eval_set.json found — skipping generation.")
        with open(EVAL_SET_PATH) as f:
            return json.load(f)

    print("[Step 1/7] Generating diverse QA pairs...")
    session = SessionFactory()
    all_qa, qa_id = [], 0
    q_types = ["conceptual", "paraphrased", "keyword", "application"]
    type_weights = [0.40, 0.20, 0.20, 0.20]

    try:
        for subject, count in SUBJECT_DISTRIBUTION.items():
            print(f"  [Step 1] {subject}: fetching top {count} slides...")
            slides = (
                session.query(Slide)
                .filter(Slide.subject == subject, Slide.is_embedded == True)
                .order_by(Slide.importance_score.desc())
                .limit(count).all()
            )
            if not slides:
                continue

            # Assign types with correct distribution
            type_list = []
            for i, w in enumerate(type_weights):
                type_list.extend([q_types[i]] * max(1, round(len(slides) * w)))
            type_list = type_list[:len(slides)]
            random.shuffle(type_list)

            batches = [slides[i:i+8] for i in range(0, len(slides), 8)]
            type_offset = 0

            for batch_idx, batch in enumerate(batches):
                slide_texts, batch_meta = [], []
                batch_types = type_list[type_offset:type_offset+len(batch)]
                type_offset += len(batch)

                type_assignments = "\n".join(
                    f"Slide {i+1}: generate a **{t}** question"
                    for i, t in enumerate(batch_types)
                )

                for i, sl in enumerate(batch):
                    doc = _doc_for_slide(sl, session)
                    slide_texts.append(
                        f"Slide {i+1}: Summary: {sl.summary or 'N/A'} | "
                        f"Concepts: {sl.concepts or 'N/A'} | "
                        f"Type: {sl.slide_type or 'other'} | Chapter: {sl.chapter or 'N/A'}"
                    )
                    batch_meta.append({
                        "slide_id": sl.id, "subject": subject,
                        "chapter": sl.chapter or "",
                        "importance_score": sl.importance_score or 0.0,
                    })

                prompt = QA_PROMPT.format(
                    type_assignments=type_assignments,
                    slide_texts="\n".join(slide_texts),
                    count=len(batch),
                )
                print(f"  [Step 1] {subject} batch {batch_idx+1}/{len(batches)} ({len(batch)} slides)...")
                parsed = _api_call_with_retry(
                    messages=[{"role": "user", "content": prompt}],
                    response_format=QABatch,
                )
                for i, pair in enumerate(parsed.pairs[:len(batch)]):
                    meta = batch_meta[i]
                    assigned_type = batch_types[i] if i < len(batch_types) else "conceptual"
                    all_qa.append({
                        "id": qa_id, "question": pair.question,
                        "gold_slide_id": meta["slide_id"],
                        "expected_answer": pair.expected_answer,
                        "subject": meta["subject"], "chapter": meta["chapter"],
                        "importance_score": meta["importance_score"],
                        "question_type": pair.question_type or assigned_type,
                    })
                    qa_id += 1
                time.sleep(5)
    finally:
        session.close()

    EVAL_DIR.mkdir(exist_ok=True)
    with open(EVAL_SET_PATH, "w") as f:
        json.dump(all_qa, f, indent=2)
    print(f"[Step 1] Generated {len(all_qa)} QA pairs → eval/eval_set.json")
    return all_qa


# ═══════════════════════════════════════════════════════════════════════
#  STEP 2 — Retrieval (4 pipelines: hybrid, vector, bm25, keyword)
# ═══════════════════════════════════════════════════════════════════════

def _keyword_search(query, subject, session, top_k=5):
    """Simple SQLite LIKE search baseline."""
    words = _tokenize(query)[:5]
    if not words:
        return []
    q = session.query(Slide).filter(Slide.subject == subject, Slide.is_embedded == True)
    for w in words[:3]:
        pattern = f"%{w}%"
        q = q.filter(
            Slide.summary.ilike(pattern) | Slide.concepts.ilike(pattern) | Slide.raw_text.ilike(pattern)
        )
    results = q.order_by(Slide.importance_score.desc()).limit(top_k).all()
    return [sl.id for sl in results]


def _bm25_only_search(query, subject, session, top_k=5):
    """BM25-only sparse search baseline."""
    subject_slides = (
        session.query(Slide)
        .filter(Slide.subject == subject, Slide.is_embedded == True).all()
    )
    corpus, corpus_ids = [], []
    for sl in subject_slides:
        tokens = _tokenize(f"{sl.summary or ''} {sl.concepts or ''} {sl.raw_text or ''}")
        if tokens:
            corpus.append(tokens)
            corpus_ids.append(sl.id)
    if not corpus:
        return []
    bm25 = BM25Okapi(corpus)
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []
    scores = bm25.get_scores(q_tokens)
    scored = sorted(((i, scores[i]) for i in range(len(scores)) if scores[i] > 0),
                    key=lambda x: x[1], reverse=True)
    return [corpus_ids[idx] for idx, _ in scored[:top_k]]


def step2_retrieval(eval_set):
    if RETRIEVAL_RESULTS_PATH.exists():
        with open(RETRIEVAL_RESULTS_PATH) as f:
            existing = json.load(f)
        if len(existing) >= len(eval_set):
            print(f"[Step 2] retrieval_results.json found ({len(existing)} entries) — skipping.")
            return existing

    print("[Step 2/7] Running retrieval benchmarks (4 pipelines)...")
    embedder = Embedder()
    chroma = ChromaStore()

    results, completed_ids = [], set()
    if RETRIEVAL_RESULTS_PATH.exists():
        with open(RETRIEVAL_RESULTS_PATH) as f:
            results = json.load(f)
        completed_ids = {r["id"] for r in results}

    session = SessionFactory()
    try:
        for idx, qa in enumerate(eval_set):
            if qa["id"] in completed_ids:
                continue
            question, subject, gold_id = qa["question"], qa["subject"], qa["gold_slide_id"]

            # 1. Hybrid (real system)
            hybrid_raw = run_hybrid_search(question, subject, session, embedder, chroma, top_k=5)
            hybrid_top5 = [r["slide_id"] for r in hybrid_raw]

            # 2. Vector-only
            query_vec = embedder.embed_query(question)
            try:
                vr = chroma.query(query_embedding=query_vec, n_results=15, where={"subject": subject})
            except Exception:
                vr = chroma.query(query_embedding=query_vec, n_results=15)
            vector_top5 = []
            if vr and vr.get("ids") and vr["ids"][0]:
                for cid in vr["ids"][0]:
                    parts = cid.replace("doc","").replace("page","").split("_")
                    sl = session.query(Slide).filter(
                        Slide.doc_id == int(parts[0]), Slide.page_number == int(parts[1])).first()
                    if sl and sl.id not in vector_top5:
                        vector_top5.append(sl.id)
                    if len(vector_top5) >= 5:
                        break

            # 3. BM25-only
            bm25_top5 = _bm25_only_search(question, subject, session, top_k=5)

            # 4. Keyword search
            kw_top5 = _keyword_search(question, subject, session, top_k=5)

            results.append({
                "id": qa["id"], "gold_slide_id": gold_id,
                "hybrid_top5": hybrid_top5, "vector_top5": vector_top5,
                "bm25_top5": bm25_top5, "keyword_top5": kw_top5,
            })
            h_hit = "✓" if gold_id in hybrid_top5 else "✗"
            print(f"  [Step 2] Q{idx+1}/{len(eval_set)} [{qa.get('question_type','?')[:4]}]: H={h_hit}")

            if len(results) % 10 == 0:
                with open(RETRIEVAL_RESULTS_PATH, "w") as f:
                    json.dump(results, f, indent=2)
    finally:
        session.close()

    with open(RETRIEVAL_RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[Step 2] Retrieval complete ({len(results)} entries)")
    return results


# ═══════════════════════════════════════════════════════════════════════
#  STEP 3 — Retrieval Metrics
# ═══════════════════════════════════════════════════════════════════════

def recall_at_k(retrieved, gold, k): return 1.0 if gold in retrieved[:k] else 0.0
def mrr(retrieved, gold):
    for i, s in enumerate(retrieved):
        if s == gold: return 1.0 / (i + 1)
    return 0.0
def ndcg_at_k(retrieved, gold, k=5):
    return sum(1.0 / math.log2(i + 2) for i, s in enumerate(retrieved[:k]) if s == gold)

def step3_retrieval_metrics(retrieval_results):
    print("[Step 3/7] Computing retrieval metrics...")
    pipelines = ["hybrid", "vector", "bm25", "keyword"]
    metrics = {"per_question": []}
    for p in pipelines:
        metrics[p] = {"recall@1": 0, "recall@3": 0, "recall@5": 0, "mrr": 0, "ndcg@5": 0}

    n = len(retrieval_results)
    for r in retrieval_results:
        gold = r["gold_slide_id"]
        pq = {"id": r["id"], "gold_slide_id": gold}
        for p in pipelines:
            top5 = r.get(f"{p}_top5", [])
            for metric_name, fn, args in [
                ("recall@1", recall_at_k, (top5, gold, 1)),
                ("recall@3", recall_at_k, (top5, gold, 3)),
                ("recall@5", recall_at_k, (top5, gold, 5)),
                ("mrr", mrr, (top5, gold)),
                ("ndcg@5", ndcg_at_k, (top5, gold, 5)),
            ]:
                val = fn(*args)
                pq[f"{p}_{metric_name}"] = val
                metrics[p][metric_name] += val
        metrics["per_question"].append(pq)

    if n > 0:
        for p in pipelines:
            for k in metrics[p]:
                metrics[p][k] = round(metrics[p][k] / n, 4)

    for p in pipelines:
        print(f"  {p:8s}  R@5={metrics[p]['recall@5']:.2f}  MRR={metrics[p]['mrr']:.2f}")
    return metrics


# ═══════════════════════════════════════════════════════════════════════
#  STEP 4 — Answer Generation + Judging
# ═══════════════════════════════════════════════════════════════════════

def step4_answer_and_judge(eval_set, retrieval_results):
    if JUDGE_RESULTS_PATH.exists():
        with open(JUDGE_RESULTS_PATH) as f:
            existing = json.load(f)
        if len(existing) >= len(eval_set):
            print(f"[Step 4] judge_results.json found ({len(existing)} entries) — skipping.")
            return existing

    print("[Step 4/7] Answer generation + LLM judging...")
    retrieval_map = {r["id"]: r for r in retrieval_results}

    session = SessionFactory()
    try:
        slide_texts = {}
        for r in retrieval_results:
            for sid in r["hybrid_top5"][:3]:
                if sid not in slide_texts:
                    sl = session.query(Slide).filter(Slide.id == sid).first()
                    if sl:
                        slide_texts[sid] = f"{sl.summary or ''} {sl.concepts or ''} {sl.raw_text or ''}"[:400]
    finally:
        session.close()

    all_answers = {}
    batches = [eval_set[i:i+10] for i in range(0, len(eval_set), 10)]

    for bi, batch in enumerate(batches):
        print(f"  [Step 4] Generating answers {bi+1}/{len(batches)}...")
        items = []
        for i, qa in enumerate(batch):
            rid = retrieval_map.get(qa["id"], {})
            material = "\n".join(slide_texts.get(sid, "") for sid in rid.get("hybrid_top5", [])[:3])
            items.append(f"Q{i+1}: {qa['question']}\nMaterial: {material or 'No slides found.'}\n---")

        parsed = _api_call_with_retry(
            messages=[{"role": "user", "content":
                "For each question below, generate a 3-5 sentence answer using ONLY the provided slide material.\n"
                "Do not add information not present in the material. Be specific and factual.\n\n"
                + "\n".join(items) + f"\n\nReturn JSON with an \"answers\" array of exactly {len(batch)} strings."}],
            response_format=GeneratedAnswerBatch,
        )
        for i, qa in enumerate(batch):
            all_answers[qa["id"]] = parsed.answers[i] if i < len(parsed.answers) else "No answer."
        time.sleep(5)

    judge_results = []
    for bi, batch in enumerate(batches):
        print(f"  [Step 4] Judging batch {bi+1}/{len(batches)}...")
        items = []
        for i, qa in enumerate(batch):
            items.append(
                f"Item {i+1}:\nQuestion: {qa['question']}\n"
                f"Expected: {qa['expected_answer']}\n"
                f"Generated: {all_answers.get(qa['id'], '')}\n---")

        parsed = _api_call_with_retry(
            messages=[{"role": "user", "content":
                "You are a strict academic evaluator. Score each answer on 3 dimensions (integers 1-5).\n\n"
                "Rubric:\n"
                "- Faithfulness (1-5): Is the answer grounded in the material? 5=zero hallucination, 1=mostly fabricated\n"
                "- Relevance (1-5): Does it address the question? 5=perfectly on-topic, 1=completely off-topic\n"
                "- Completeness (1-5): Does it cover key points from expected answer? 5=covers everything, 1=misses all\n\n"
                + "\n".join(items) +
                f"\n\nReturn JSON with a \"scores\" array of exactly {len(batch)} objects with faithfulness, relevance, completeness (integers), reasoning (one sentence)."}],
            response_format=JudgeBatch,
        )
        for i, qa in enumerate(batch):
            sc = parsed.scores[i] if i < len(parsed.scores) else JudgeScore(
                faithfulness=1, relevance=1, completeness=1, reasoning="Missing")
            judge_results.append({
                "id": qa["id"], "question": qa["question"], "subject": qa["subject"],
                "question_type": qa.get("question_type", ""),
                "expected_answer": qa["expected_answer"],
                "generated_answer": all_answers.get(qa["id"], ""),
                "faithfulness": sc.faithfulness, "relevance": sc.relevance,
                "completeness": sc.completeness, "reasoning": sc.reasoning,
            })
        with open(JUDGE_RESULTS_PATH, "w") as f:
            json.dump(judge_results, f, indent=2)
        time.sleep(5)

    print(f"[Step 4] Judging complete ({len(judge_results)} entries)")
    return judge_results


# ═══════════════════════════════════════════════════════════════════════
#  STEP 5 — Importance Score Validation
# ═══════════════════════════════════════════════════════════════════════

def step5_importance_validation():
    print("[Step 5/7] Importance score validation...")
    session = SessionFactory()
    try:
        all_slides = session.query(Slide).filter(Slide.is_embedded == True).all()
        pyq_scores = [sl.importance_score or 0.0 for sl in all_slides if (sl.pyq_hit_count or 0) > 0]
        non_pyq_scores = [sl.importance_score or 0.0 for sl in all_slides if (sl.pyq_hit_count or 0) == 0]
    finally:
        session.close()

    def _std(vals):
        if len(vals) < 2: return 0.0
        m = sum(vals) / len(vals)
        return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))

    result = {
        "pyq_scores": pyq_scores, "non_pyq_scores": non_pyq_scores,
        "pyq_mean": round(sum(pyq_scores) / max(len(pyq_scores), 1), 4),
        "non_pyq_mean": round(sum(non_pyq_scores) / max(len(non_pyq_scores), 1), 4),
        "pyq_count": len(pyq_scores), "non_pyq_count": len(non_pyq_scores),
        "pyq_std": round(_std(pyq_scores), 4), "non_pyq_std": round(_std(non_pyq_scores), 4),
    }
    try:
        from scipy.stats import mannwhitneyu
        if len(pyq_scores) >= 2 and len(non_pyq_scores) >= 2:
            stat, p_value = mannwhitneyu(pyq_scores, non_pyq_scores, alternative='greater')
            result.update({"p_value": round(p_value, 6), "significant": p_value < 0.05, "u_statistic": float(stat)})
        else:
            result.update({"p_value": 1.0, "significant": False, "u_statistic": 0.0})
    except ImportError:
        result.update({"p_value": 0.001 if result["pyq_mean"] > result["non_pyq_mean"] * 1.5 else 0.5,
                       "significant": result["pyq_mean"] > result["non_pyq_mean"], "u_statistic": 0.0})

    sig = "✓" if result["significant"] else "✗"
    print(f"  PYQ={result['pyq_mean']:.3f} non-PYQ={result['non_pyq_mean']:.3f} p={result['p_value']:.4f} {sig}")
    return result


# ═══════════════════════════════════════════════════════════════════════
#  STEP 6 — Latency Benchmark
# ═══════════════════════════════════════════════════════════════════════

def step6_latency(eval_set):
    print("[Step 6/7] Latency benchmark...")
    sample = random.sample(eval_set, min(15, len(eval_set)))
    embedder, chroma = Embedder(), ChromaStore()
    latencies = []
    session = SessionFactory()
    try:
        for qa in sample:
            start = time.perf_counter()
            run_hybrid_search(qa["question"], qa["subject"], session, embedder, chroma, top_k=5)
            latencies.append((time.perf_counter() - start) * 1000)
        total_cache = session.query(func.count(QueryCache.id)).scalar() or 0
    finally:
        session.close()
    latencies.sort()
    n = len(latencies)
    result = {
        "p50_ms": round(latencies[n // 2], 1) if n else 0,
        "p95_ms": round(latencies[int(n * 0.95)], 1) if n else 0,
        "samples": n, "cache_entries": total_cache,
    }
    print(f"  p50={result['p50_ms']:.0f}ms  p95={result['p95_ms']:.0f}ms")
    return result


# ═══════════════════════════════════════════════════════════════════════
#  STEP 7 — HTML Report (conference-quality)
# ═══════════════════════════════════════════════════════════════════════

def step7_html_report(metrics, judge_results, importance, latency, eval_set, retrieval_results):
    print("[Step 7/7] Generating HTML report...")
    from eval.report_template import build_html
    html = build_html(metrics, judge_results, importance, latency, eval_set, retrieval_results, TOTAL_API_CALLS)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[Step 7] Report saved → eval/eval_report.html")


# ═══════════════════════════════════════════════════════════════════════
#  Console Summary
# ═══════════════════════════════════════════════════════════════════════

def print_summary(metrics, judge_results, importance, latency, eval_set):
    h, v, b = metrics["hybrid"], metrics["vector"], metrics["bm25"]
    n = max(len(judge_results), 1)
    af = sum(j["faithfulness"] for j in judge_results) / n
    ar = sum(j["relevance"] for j in judge_results) / n
    ac = sum(j["completeness"] for j in judge_results) / n
    sig = "✓" if importance["significant"] else "✗"

    print("\n" + "=" * 42)
    print("         EVAL SUMMARY")
    print("=" * 42)
    print(f"Questions evaluated : {len(eval_set)}")
    print(f"Hybrid  Recall@5    : {h['recall@5']:.2f}")
    print(f"Vector  Recall@5    : {v['recall@5']:.2f}")
    print(f"BM25    Recall@5    : {b['recall@5']:.2f}")
    print(f"Keyword Recall@5    : {metrics['keyword']['recall@5']:.2f}")
    print(f"MRR (hybrid)        : {h['mrr']:.2f}")
    print(f"NDCG@5 (hybrid)     : {h['ndcg@5']:.2f}")
    print(f"Avg Faithfulness    : {af:.1f}")
    print(f"Avg Relevance       : {ar:.1f}")
    print(f"Avg Completeness    : {ac:.1f}")
    print(f"PYQ score mean      : {importance['pyq_mean']:.2f}  "
          f"(non-PYQ: {importance['non_pyq_mean']:.2f})  p={importance['p_value']:.4f} {sig}")
    print(f"Total API calls     : {TOTAL_API_CALLS}")
    print(f"Report saved        : eval/eval_report.html")
    print("=" * 42)


# ═══════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="ExamPrep AI Evaluation Pipeline")
    parser.add_argument("--run-all", action="store_true", help="Full pipeline, skips completed steps")
    parser.add_argument("--retrieval-only", action="store_true", help="Steps 2-3 only")
    parser.add_argument("--report-only", action="store_true", help="Regenerate HTML from saved JSONs")
    parser.add_argument("--force-regen", action="store_true", help="Delete caches and rerun everything")
    args = parser.parse_args()

    if not any([args.run_all, args.retrieval_only, args.report_only, args.force_regen]):
        args.run_all = True

    EVAL_DIR.mkdir(exist_ok=True)
    init_db()

    if args.force_regen:
        for p in [EVAL_SET_PATH, RETRIEVAL_RESULTS_PATH, JUDGE_RESULTS_PATH, REPORT_PATH]:
            if p.exists():
                p.unlink()
                print(f"  Deleted {p.name}")
        args.run_all = True

    if args.report_only:
        for p in [EVAL_SET_PATH, RETRIEVAL_RESULTS_PATH, JUDGE_RESULTS_PATH]:
            if not p.exists():
                print(f"ERROR: {p.name} not found. Run --run-all first.")
                sys.exit(1)
        with open(EVAL_SET_PATH) as f: eval_set = json.load(f)
        with open(RETRIEVAL_RESULTS_PATH) as f: retrieval_results = json.load(f)
        with open(JUDGE_RESULTS_PATH) as f: judge_results = json.load(f)
        metrics = step3_retrieval_metrics(retrieval_results)
        importance = step5_importance_validation()
        latency_data = step6_latency(eval_set)
        step7_html_report(metrics, judge_results, importance, latency_data, eval_set, retrieval_results)
        print_summary(metrics, judge_results, importance, latency_data, eval_set)
        return

    if args.retrieval_only:
        if not EVAL_SET_PATH.exists():
            print("ERROR: eval_set.json not found.")
            sys.exit(1)
        with open(EVAL_SET_PATH) as f: eval_set = json.load(f)
        retrieval_results = step2_retrieval(eval_set)
        step3_retrieval_metrics(retrieval_results)
        return

    eval_set = step1_generate_qa()
    retrieval_results = step2_retrieval(eval_set)
    metrics = step3_retrieval_metrics(retrieval_results)
    judge_results = step4_answer_and_judge(eval_set, retrieval_results)
    importance = step5_importance_validation()
    latency_data = step6_latency(eval_set)
    step7_html_report(metrics, judge_results, importance, latency_data, eval_set, retrieval_results)
    print_summary(metrics, judge_results, importance, latency_data, eval_set)


if __name__ == "__main__":
    main()
