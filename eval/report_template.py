"""
report_template.py — Conference-quality HTML report generator for ExamPrep AI eval.

Produces a fully self-contained HTML file with Chart.js visualizations,
detailed methodology/rubric section, and 4-pipeline comparison.
"""

import json


def build_html(metrics, judge_results, importance, latency, eval_set, retrieval_results, total_api_calls):
    h = metrics["hybrid"]
    v = metrics["vector"]
    b = metrics["bm25"]
    kw = metrics["keyword"]
    n_j = max(len(judge_results), 1)

    avg_faith = round(sum(j["faithfulness"] for j in judge_results) / n_j, 2)
    avg_rel = round(sum(j["relevance"] for j in judge_results) / n_j, 2)
    avg_comp = round(sum(j["completeness"] for j in judge_results) / n_j, 2)

    ret_map = {r["id"]: r for r in retrieval_results}
    judge_map = {j["id"]: j for j in judge_results}

    # Question type counts
    type_counts = {}
    for qa in eval_set:
        t = qa.get("question_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    # Importance histogram
    bins = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]
    bin_labels = ["0.0–0.2", "0.2–0.4", "0.4–0.6", "0.6–0.8", "0.8–1.0"]
    def _bin(scores):
        counts = [0] * 5
        for s in scores:
            for i, (lo, hi) in enumerate(bins):
                if lo <= s < hi or (i == 4 and s >= lo):
                    counts[i] += 1; break
        return counts
    pyq_hist = _bin(importance["pyq_scores"])
    non_pyq_hist = _bin(importance["non_pyq_scores"])

    p_str = f"{importance['p_value']:.4f}"
    sig_text = "statistically significant" if importance["significant"] else "not significant"

    # Per-question table
    table_rows = ""
    for qa in eval_set:
        qid = qa["id"]
        ret = ret_map.get(qid, {})
        jdg = judge_map.get(qid, {})
        gold = qa["gold_slide_id"]
        h5 = ret.get("hybrid_top5", [])
        hit1 = "✓" if gold in h5[:1] else "✗"
        hit3 = "✓" if gold in h5[:3] else "✗"
        hit5 = "✓" if gold in h5[:5] else "✗"
        color = "#1b3a2a" if gold in h5[:3] else "#3a3520" if gold in h5[:5] else "#3a1b1b"
        trunc = qa["question"][:55] + ("…" if len(qa["question"]) > 55 else "")
        qt = qa.get("question_type", "?")[:5]
        table_rows += f'<tr style="background:{color}"><td>{qid}</td><td>{qa["subject"]}</td><td>{qt}</td><td title="{qa["question"]}">{trunc}</td><td>{hit1}</td><td>{hit3}</td><td>{hit5}</td><td>{jdg.get("faithfulness","-")}</td><td>{jdg.get("relevance","-")}</td><td>{jdg.get("completeness","-")}</td></tr>\n'

    def _d(a, b_val):
        d = a - b_val
        c = "#4caf50" if d >= 0 else "#ef5350"
        s = "+" if d >= 0 else ""
        return f'<span style="color:{c};font-weight:600">{s}{d:.4f}</span>'

    # ── Build HTML ──────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ExamPrep AI — Retrieval &amp; RAG Evaluation Report</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',system-ui,sans-serif;background:#0a0a0f;color:#d4d4d8;min-height:100vh;padding:0}}
.hero{{background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 50%,#0f172a 100%);padding:3rem 2rem 2rem;text-align:center;border-bottom:1px solid rgba(139,92,246,0.2)}}
.hero h1{{font-size:2rem;font-weight:700;background:linear-gradient(135deg,#a78bfa,#60a5fa,#34d399);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:.4rem}}
.hero .meta{{color:#6b7280;font-size:.85rem;line-height:1.6}}
.hero .meta strong{{color:#a78bfa}}
.container{{max-width:1280px;margin:0 auto;padding:1.5rem}}
.section-title{{font-size:1.1rem;font-weight:600;color:#a78bfa;margin:2rem 0 1rem;padding-bottom:.5rem;border-bottom:1px solid rgba(139,92,246,0.15);display:flex;align-items:center;gap:.5rem}}
.card{{background:rgba(15,15,25,0.8);border:1px solid rgba(139,92,246,0.12);border-radius:12px;padding:1.5rem;margin-bottom:1.2rem;backdrop-filter:blur(8px)}}
.card h3{{font-size:.95rem;font-weight:600;color:#c4b5fd;margin-bottom:.8rem}}
table{{width:100%;border-collapse:collapse;font-size:.8rem}}
th{{background:rgba(139,92,246,0.1);padding:8px 10px;text-align:left;font-weight:600;color:#a78bfa;border-bottom:1px solid rgba(139,92,246,0.15);font-size:.78rem;text-transform:uppercase;letter-spacing:.04em}}
td{{padding:6px 10px;border-bottom:1px solid rgba(255,255,255,0.03);color:#a1a1aa}}
.chart-grid{{display:grid;grid-template-columns:1fr 1fr;gap:1.2rem}}
.chart-box{{position:relative;height:320px}}
.stat-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.8rem;margin:.8rem 0}}
.stat{{background:rgba(139,92,246,0.06);border:1px solid rgba(139,92,246,0.1);border-radius:10px;padding:1rem;text-align:center}}
.stat .val{{font-size:1.6rem;font-weight:700;color:#a78bfa}}
.stat .lbl{{font-size:.72rem;color:#6b7280;margin-top:2px;text-transform:uppercase;letter-spacing:.05em}}
.callout{{background:rgba(250,204,21,0.06);border-left:3px solid #facc15;padding:.6rem .8rem;border-radius:0 8px 8px 0;margin:.8rem 0;font-size:.82rem;color:#d4d4d8}}
.methodology-grid{{display:grid;grid-template-columns:1fr 1fr;gap:1.2rem}}
.method-card{{background:rgba(30,27,75,0.4);border:1px solid rgba(139,92,246,0.1);border-radius:10px;padding:1.2rem}}
.method-card h4{{font-size:.85rem;font-weight:600;color:#c4b5fd;margin-bottom:.5rem}}
.method-card p,.method-card li{{font-size:.8rem;color:#9ca3af;line-height:1.6}}
.method-card ul{{padding-left:1.2rem}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.7rem;font-weight:600;text-transform:uppercase}}
.badge-auto{{background:rgba(96,165,250,0.15);color:#60a5fa}}
.badge-llm{{background:rgba(167,139,250,0.15);color:#a78bfa}}
.tag{{display:inline-block;padding:1px 6px;border-radius:3px;font-size:.7rem;margin:1px}}
.tag-conceptual{{background:rgba(96,165,250,0.12);color:#93c5fd}}
.tag-paraphrased{{background:rgba(52,211,153,0.12);color:#6ee7b7}}
.tag-keyword{{background:rgba(250,204,21,0.12);color:#fde68a}}
.tag-application{{background:rgba(244,114,182,0.12);color:#f9a8d4}}
footer{{text-align:center;padding:2rem;color:#4b5563;font-size:.75rem;border-top:1px solid rgba(139,92,246,0.08)}}
@media(max-width:768px){{.chart-grid,.methodology-grid{{grid-template-columns:1fr}}.container{{padding:1rem}}}}
</style>
</head>
<body>

<div class="hero">
<h1>ExamPrep AI — Retrieval &amp; RAG Evaluation Report</h1>
<p class="meta">
<strong>{len(eval_set)}</strong> evaluation queries &bull;
<strong>4</strong> retrieval pipelines compared &bull;
<strong>{total_api_calls}</strong> API calls &bull;
Model: <strong>Gemini 2.5 Flash Lite</strong><br>
Subjects: CN ({type_counts.get('conceptual',0)+type_counts.get('paraphrased',0)+type_counts.get('keyword',0)+type_counts.get('application',0)} total) &bull;
Question types: {' &bull; '.join(f'{t}: {c}' for t,c in sorted(type_counts.items()))}
</p>
</div>

<div class="container">

<!-- ══════ 1. Executive Summary ══════ -->
<div class="section-title">📊 Executive Summary — Retrieval Performance</div>
<div class="card">
<table>
<thead><tr><th>Metric</th><th>Hybrid (RRF)</th><th>Vector-Only</th><th>BM25-Only</th><th>Keyword Search</th><th>Hybrid vs Vector</th><th>Hybrid vs BM25</th></tr></thead>
<tbody>
<tr><td>Recall@1</td><td><strong>{h['recall@1']:.4f}</strong></td><td>{v['recall@1']:.4f}</td><td>{b['recall@1']:.4f}</td><td>{kw['recall@1']:.4f}</td><td>{_d(h['recall@1'],v['recall@1'])}</td><td>{_d(h['recall@1'],b['recall@1'])}</td></tr>
<tr><td>Recall@3</td><td><strong>{h['recall@3']:.4f}</strong></td><td>{v['recall@3']:.4f}</td><td>{b['recall@3']:.4f}</td><td>{kw['recall@3']:.4f}</td><td>{_d(h['recall@3'],v['recall@3'])}</td><td>{_d(h['recall@3'],b['recall@3'])}</td></tr>
<tr><td>Recall@5</td><td><strong>{h['recall@5']:.4f}</strong></td><td>{v['recall@5']:.4f}</td><td>{b['recall@5']:.4f}</td><td>{kw['recall@5']:.4f}</td><td>{_d(h['recall@5'],v['recall@5'])}</td><td>{_d(h['recall@5'],b['recall@5'])}</td></tr>
<tr><td>MRR</td><td><strong>{h['mrr']:.4f}</strong></td><td>{v['mrr']:.4f}</td><td>{b['mrr']:.4f}</td><td>{kw['mrr']:.4f}</td><td>{_d(h['mrr'],v['mrr'])}</td><td>{_d(h['mrr'],b['mrr'])}</td></tr>
<tr><td>NDCG@5</td><td><strong>{h['ndcg@5']:.4f}</strong></td><td>{v['ndcg@5']:.4f}</td><td>{b['ndcg@5']:.4f}</td><td>{kw['ndcg@5']:.4f}</td><td>{_d(h['ndcg@5'],v['ndcg@5'])}</td><td>{_d(h['ndcg@5'],b['ndcg@5'])}</td></tr>
</tbody>
</table>
</div>

<!-- ══════ 2. Charts ══════ -->
<div class="section-title">📈 Retrieval Performance Visualizations</div>
<div class="chart-grid">
<div class="card"><h3>Recall@k — All Pipelines</h3><div class="chart-box"><canvas id="recallChart"></canvas></div></div>
<div class="card"><h3>MRR &amp; NDCG@5 Comparison</h3><div class="chart-box"><canvas id="mrrChart"></canvas></div></div>
<div class="card"><h3>Answer Quality — Radar</h3><div class="chart-box"><canvas id="radarChart"></canvas></div></div>
<div class="card"><h3>Question Type Distribution</h3><div class="chart-box"><canvas id="typeChart"></canvas></div></div>
</div>

<!-- ══════ 3. Answer Quality ══════ -->
<div class="section-title">📝 Answer Quality (RAG Pipeline)</div>
<div class="stat-row">
<div class="stat"><div class="val">{avg_faith}</div><div class="lbl">Faithfulness</div></div>
<div class="stat"><div class="val">{avg_rel}</div><div class="lbl">Relevance</div></div>
<div class="stat"><div class="val">{avg_comp}</div><div class="lbl">Completeness</div></div>
<div class="stat"><div class="val">{round((avg_faith+avg_rel+avg_comp)/3,2)}</div><div class="lbl">Overall</div></div>
</div>

<!-- ══════ 4. Importance Scores ══════ -->
<div class="section-title">🔬 Importance Score Validation (PYQ vs Non-PYQ)</div>
<div class="chart-grid">
<div class="card"><h3>Distribution Histogram</h3><div class="chart-box"><canvas id="importanceChart"></canvas></div>
<div class="callout">Mann-Whitney U test: <strong>p = {p_str}</strong> — {sig_text} (α=0.05). PYQ mean={importance['pyq_mean']:.3f} ± {importance['pyq_std']:.3f} (n={importance['pyq_count']}), Non-PYQ mean={importance['non_pyq_mean']:.3f} ± {importance['non_pyq_std']:.3f} (n={importance['non_pyq_count']}).</div>
</div>
<div class="card"><h3>Latency Profile</h3>
<div class="stat-row">
<div class="stat"><div class="val">{latency['p50_ms']:.0f}<small>ms</small></div><div class="lbl">p50</div></div>
<div class="stat"><div class="val">{latency['p95_ms']:.0f}<small>ms</small></div><div class="lbl">p95</div></div>
<div class="stat"><div class="val">{latency['samples']}</div><div class="lbl">Samples</div></div>
<div class="stat"><div class="val">{latency['cache_entries']}</div><div class="lbl">Cache Entries</div></div>
</div>
</div>
</div>

<!-- ══════ 5. Per-Question Table ══════ -->
<div class="section-title">📋 Per-Question Results (Hybrid Pipeline)</div>
<div class="card" style="overflow-x:auto">
<table>
<thead><tr><th>#</th><th>Subj</th><th>Type</th><th>Question</th><th>H@1</th><th>H@3</th><th>H@5</th><th>Faith</th><th>Rel</th><th>Comp</th></tr></thead>
<tbody>{table_rows}</tbody>
</table>
</div>

<!-- ══════ 6. Methodology ══════ -->
<div class="section-title">📖 Evaluation Methodology &amp; Transparency</div>
<div class="methodology-grid">
<div class="method-card">
<h4>🔍 Evaluation Type</h4>
<p><span class="badge badge-auto">Automated</span> <span class="badge badge-llm">LLM-as-Judge</span></p>
<p style="margin-top:.5rem">This evaluation uses <strong>RAGAS-style LLM-as-judge</strong> methodology (Es et al., 2023). No human annotators were used. All scoring is performed by a single LLM judge (Gemini 2.5 Flash Lite) using structured Pydantic output parsing for deterministic schema compliance.</p>
</div>
<div class="method-card">
<h4>📏 Scoring Rubric</h4>
<ul>
<li><strong>Faithfulness (1–5)</strong>: Is the answer grounded in the retrieved material? 5 = zero hallucination, factually verified. 1 = mostly fabricated content.</li>
<li><strong>Relevance (1–5)</strong>: Does the answer directly address the question asked? 5 = perfectly on-topic. 1 = completely off-topic.</li>
<li><strong>Completeness (1–5)</strong>: Does the answer cover all key points from the expected answer? 5 = comprehensive. 1 = misses all key points.</li>
</ul>
</div>
<div class="method-card">
<h4>🧪 Question Generation</h4>
<p>40 questions generated across 4 types to simulate real student query patterns:</p>
<ul>
<li><span class="tag tag-conceptual">conceptual</span> (40%) — Understanding-based: why/how questions</li>
<li><span class="tag tag-paraphrased">paraphrased</span> (20%) — Same idea, different wording</li>
<li><span class="tag tag-keyword">keyword</span> (20%) — Short search-like queries (3-7 words)</li>
<li><span class="tag tag-application">application</span> (20%) — Real student doubts, indirect questions</li>
</ul>
<p style="margin-top:.4rem">~30% of questions include intentional noise: vague phrasing, missing keywords, informal language, or slightly broader scope to test retrieval robustness.</p>
</div>
<div class="method-card">
<h4>⚙️ Pipeline Descriptions</h4>
<ul>
<li><strong>Hybrid (RRF)</strong>: ChromaDB cosine similarity + BM25 Okapi sparse search, fused via Reciprocal Rank Fusion (K=60). The production pipeline.</li>
<li><strong>Vector-Only</strong>: ChromaDB cosine similarity only (intfloat/e5-large-v2, 1024-dim). No lexical matching.</li>
<li><strong>BM25-Only</strong>: BM25 Okapi sparse search over slide text. No semantic understanding.</li>
<li><strong>Keyword Search</strong>: SQLite LIKE-based pattern matching. Simplest baseline.</li>
</ul>
</div>
</div>

<div class="card" style="margin-top:1rem">
<h3>📑 Annotator &amp; Reproducibility Details</h3>
<table>
<tr><td style="width:200px;font-weight:600;color:#a78bfa">Number of annotators</td><td>1 (LLM judge — Gemini 2.5 Flash Lite)</td></tr>
<tr><td style="font-weight:600;color:#a78bfa">Human oversight</td><td>None — fully automated pipeline. All questions, answers, and scores generated/evaluated by LLM.</td></tr>
<tr><td style="font-weight:600;color:#a78bfa">Evaluation model</td><td>Gemini 2.5 Flash Lite (via OpenAI-compatible endpoint)</td></tr>
<tr><td style="font-weight:600;color:#a78bfa">Embedding model</td><td>intfloat/e5-large-v2 (1024-dim, sentence-transformers)</td></tr>
<tr><td style="font-weight:600;color:#a78bfa">Total API calls</td><td>{total_api_calls} (~5 QA gen + 4 answer gen + 4 judging + 1 extra)</td></tr>
<tr><td style="font-weight:600;color:#a78bfa">Resume safety</td><td>All intermediate results cached to JSON. Pipeline resumes from last checkpoint on restart.</td></tr>
<tr><td style="font-weight:600;color:#a78bfa">Statistical test</td><td>Mann-Whitney U (one-sided, α=0.05) for importance score separation</td></tr>
<tr><td style="font-weight:600;color:#a78bfa">Known limitations</td><td>LLM-as-judge may inflate scores vs human judgment. Single-relevance assumption (1 gold slide per query) underestimates multi-slide topics. Keyword search baseline limited to AND-conjunction of top-3 tokens.</td></tr>
</table>
</div>

<footer>
ExamPrep AI Evaluation Report &bull; Generated automatically by eval_pipeline.py &bull; RAGAS-style methodology (Es et al., 2023)
</footer>
</div>

<script>
Chart.defaults.color='#9ca3af';
Chart.defaults.borderColor='rgba(139,92,246,0.06)';
const COLORS={{hybrid:'rgba(139,92,246,0.8)',vector:'rgba(96,165,250,0.7)',bm25:'rgba(52,211,153,0.7)',keyword:'rgba(250,204,21,0.6)'}};

new Chart(document.getElementById('recallChart'),{{type:'bar',data:{{labels:['Recall@1','Recall@3','Recall@5'],datasets:[
{{label:'Hybrid (RRF)',data:[{h['recall@1']},{h['recall@3']},{h['recall@5']}],backgroundColor:COLORS.hybrid,borderRadius:5}},
{{label:'Vector-Only',data:[{v['recall@1']},{v['recall@3']},{v['recall@5']}],backgroundColor:COLORS.vector,borderRadius:5}},
{{label:'BM25-Only',data:[{b['recall@1']},{b['recall@3']},{b['recall@5']}],backgroundColor:COLORS.bm25,borderRadius:5}},
{{label:'Keyword',data:[{kw['recall@1']},{kw['recall@3']},{kw['recall@5']}],backgroundColor:COLORS.keyword,borderRadius:5}}
]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'top'}}}},scales:{{y:{{beginAtZero:true,max:1,ticks:{{callback:v=>(v*100).toFixed(0)+'%'}}}}}}}}}});

new Chart(document.getElementById('mrrChart'),{{type:'bar',data:{{labels:['MRR','NDCG@5'],datasets:[
{{label:'Hybrid',data:[{h['mrr']},{h['ndcg@5']}],backgroundColor:COLORS.hybrid,borderRadius:6}},
{{label:'Vector',data:[{v['mrr']},{v['ndcg@5']}],backgroundColor:COLORS.vector,borderRadius:6}},
{{label:'BM25',data:[{b['mrr']},{b['ndcg@5']}],backgroundColor:COLORS.bm25,borderRadius:6}},
{{label:'Keyword',data:[{kw['mrr']},{kw['ndcg@5']}],backgroundColor:COLORS.keyword,borderRadius:6}}
]}},options:{{responsive:true,maintainAspectRatio:false,scales:{{y:{{beginAtZero:true,max:1}}}}}}}});

new Chart(document.getElementById('radarChart'),{{type:'radar',data:{{labels:['Faithfulness','Relevance','Completeness'],datasets:[
{{label:'System',data:[{avg_faith},{avg_rel},{avg_comp}],backgroundColor:'rgba(139,92,246,0.15)',borderColor:'rgba(139,92,246,1)',borderWidth:2,pointRadius:5,pointBackgroundColor:'rgba(139,92,246,1)'}},
{{label:'Target (4.0/4.0/3.5)',data:[4,4,3.5],backgroundColor:'rgba(250,204,21,0.08)',borderColor:'rgba(250,204,21,0.6)',borderWidth:2,borderDash:[5,5],pointRadius:4}}
]}},options:{{responsive:true,maintainAspectRatio:false,scales:{{r:{{min:0,max:5,ticks:{{stepSize:1,backdropColor:'transparent'}},grid:{{color:'rgba(139,92,246,0.08)'}},pointLabels:{{font:{{size:12}}}}}}}}}}}});

new Chart(document.getElementById('typeChart'),{{type:'doughnut',data:{{labels:{json.dumps(list(type_counts.keys()))},datasets:[{{data:{json.dumps(list(type_counts.values()))},backgroundColor:['rgba(96,165,250,0.7)','rgba(52,211,153,0.7)','rgba(250,204,21,0.7)','rgba(244,114,182,0.7)','rgba(139,92,246,0.7)'],borderWidth:0}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{position:'right',labels:{{padding:12}}}}}}}}}});

new Chart(document.getElementById('importanceChart'),{{type:'bar',data:{{labels:{json.dumps(bin_labels)},datasets:[
{{label:'PYQ-Matched',data:{json.dumps(pyq_hist)},backgroundColor:'rgba(52,211,153,0.5)',borderColor:'rgba(52,211,153,0.8)',borderWidth:1,borderRadius:4}},
{{label:'Non-PYQ',data:{json.dumps(non_pyq_hist)},backgroundColor:'rgba(107,114,128,0.3)',borderColor:'rgba(107,114,128,0.6)',borderWidth:1,borderRadius:4}}
]}},options:{{responsive:true,maintainAspectRatio:false,scales:{{y:{{beginAtZero:true,title:{{display:true,text:'Count'}}}},x:{{title:{{display:true,text:'Importance Score'}}}}}}}}}});
</script>
</body>
</html>"""
