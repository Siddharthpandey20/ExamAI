# ExamPrep AI — System Documentation

> Complete technical reference for the entire pipeline.  
> Written for anyone taking over from here to the next phase.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Directory Structure](#2-directory-structure)
3. [Dependencies & External Services](#3-dependencies--external-services)
4. [Stage 1 — Ingestion](#4-stage-1--ingestion)
5. [Stage 2 — Structuring](#5-stage-2--structuring)
6. [Stage 3 — Indexing](#6-stage-3--indexing)
7. [Stage 4 — PYQ Mapping](#7-stage-4--pyq-mapping)
8. [Database Schemas](#8-database-schemas)
9. [Pydantic Schemas (Data Contracts)](#9-pydantic-schemas-data-contracts)
10. [Concurrency & Parallelism Map](#10-concurrency--parallelism-map)
11. [Input / Output Formats](#11-input--output-formats)
12. [Duplicate Prevention & Caching](#12-duplicate-prevention--caching)
13. [Configuration Reference](#13-configuration-reference)
14. [CLI Commands](#14-cli-commands)
15. [What's Implemented vs What's Pending](#15-whats-implemented-vs-whats-pending)
16. [Key Design Decisions](#16-key-design-decisions)

---

## 1. Project Overview

ExamPrep AI converts chaotic academic material (PDFs, PPTXs, scanned notes) into structured, exam-optimized knowledge. It is **not** a chatbot — it is a **knowledge extraction and exam-linking system**.

**Core idea:** Upload slides → system parses, classifies, embeds every slide → upload past-year papers → system links each question to the most relevant slides and scores importance.

**End-to-end pipeline:**

```
uploads/*.pdf, *.pptx
        │
        ▼
  ┌─────────────┐
  │  INGESTION   │  Parse + OCR + AI cleanup → knowledge/*.md
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │ STRUCTURING  │  Agent 1 (Ollama) + Agent 2 (Gemini) → enriched knowledge/*.md
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │   INDEXING   │  Sentence-Transformer → ChromaDB + SQLite
  └──────┬──────┘
         │
         ▼
  ┌─────────────┐
  │  PYQ MAPPER  │  Question extraction + Hybrid search → slide-question links
  └─────────────┘
```

Each stage runs independently via CLI. Stages must run in order for a given file: Ingestion → Structuring → Indexing → PYQ.

---

## 2. Directory Structure

```
ExamAI/
├── ingestion/              # Stage 1: Parse & OCR
│   ├── __init__.py         # run_ingestion() entry point
│   ├── __main__.py         # CLI: python -m ingestion [file]
│   ├── config.py           # Paths, OCR settings, Ollama config
│   ├── pipeline.py         # 6-stage orchestrator
│   ├── parser_pdf.py       # PyMuPDF wrapper
│   ├── parser_pptx.py      # python-pptx wrapper
│   ├── ocr_engine.py       # PaddleOCR singleton + layout detection
│   ├── table_extractor.py  # Camelot table extraction
│   ├── ai_cleanup.py       # Ollama Llama3 text cleanup
│   ├── md_writer.py        # Markdown assembly
│   ├── tracker.py          # JSON processed-file tracker
│   └── processed.json      # Tracks ingested files
│
├── structuring/            # Stage 2: AI classification
│   ├── __init__.py         # run_structuring() entry point (async)
│   ├── __main__.py         # CLI: python -m structuring [file]
│   ├── config.py           # Ollama, Gemini config, rate limits
│   ├── schemas.py          # Pydantic models for both agents
│   ├── md_parser.py        # Parse knowledge markdown into slides
│   ├── file_agent.py       # Agent 1 (Ollama): document overview
│   ├── slide_agent.py      # Agent 2 (Gemini): slide classification
│   ├── md_writer.py        # Write enriched markdown back
│   ├── tracker.py          # JSON structured-file tracker
│   └── structured.json     # Tracks structured files
│
├── indexing/               # Stage 3: Embed & store
│   ├── __init__.py         # Module anchor
│   ├── __main__.py         # CLI: python -m indexing [file] [--force]
│   ├── config.py           # Embedding model, DB paths, batch size
│   ├── models.py           # SQLAlchemy ORM (Document, Slide, PYQ tables)
│   ├── database.py         # Engine, session factory, init_db()
│   ├── db_sqlite.py        # Repository functions (insert, upsert, query)
│   ├── db_chroma.py        # ChromaDB wrapper (upsert, query, delete)
│   ├── embedder.py         # Sentence-Transformer encoder (e5-large-v2)
│   ├── md_reader.py        # Parse enriched markdown → DocMeta + SlideMeta
│   └── pipeline.py         # Per-file indexing orchestrator
│
├── pyq/                    # Stage 4: Past-year question linking
│   ├── __init__.py         # run_pyq() entry point
│   ├── __main__.py         # CLI: python -m pyq [file] [--force]
│   ├── config.py           # Search thresholds, scoring weights
│   ├── schemas.py          # Pydantic models for questions & RRF results
│   ├── ingestion_helper.py # PYQ-specific OCR pipeline
│   ├── extractor.py        # Llama3 question extraction via Agents SDK
│   ├── bm25_search.py      # Sparse BM25 index
│   ├── hybrid_search.py    # Dense + Sparse + RRF fusion
│   ├── mapper.py           # Record matches, compute importance scores
│   ├── pipeline.py         # 3-phase parallel orchestrator
│   ├── tracker.py          # Thread-safe JSON tracker
│   └── pyq_processed.json  # Tracks processed PYQ files
│
├── uploads/                # Drop zone: raw PDFs, PPTXs
├── pyq_uploads/            # Drop zone: past-year question papers
├── knowledge/              # Output: markdown files (raw → enriched)
├── chromadb_store/         # Persistent ChromaDB data
├── examai.db               # SQLite database
├── requirements.txt        # Python dependencies
└── SYSTEM.md               # This file
```

---

## 3. Dependencies & External Services

### Python Packages

| Package | Purpose | Used In |
|---------|---------|---------|
| `PyMuPDF` (fitz) | PDF parsing + page rendering | Ingestion, PYQ |
| `python-pptx` | PPTX parsing | Ingestion |
| `paddleocr` + `paddlepaddle` | OCR (image → text) | Ingestion, PYQ |
| `camelot-py[cv]` + `opencv-python-headless` | Table extraction from PDFs | Ingestion |
| `Pillow` | Image manipulation | Ingestion |
| `openai-agents` | Agent framework (Agents SDK) | Structuring, PYQ |
| `pydantic` | Structured output / data validation | All modules |
| `chromadb` | Vector database (persistent) | Indexing, PYQ |
| `sentence-transformers` | Embedding model (`e5-large-v2`) | Indexing, PYQ |
| `sqlalchemy` | SQLite ORM | Indexing, PYQ |
| `rank-bm25` | BM25 sparse search | PYQ |
| `requests` | HTTP (Ollama API) | Ingestion |
| `python-dotenv` | Environment variables | Structuring |

### External Services

| Service | Endpoint | Purpose | Required When |
|---------|----------|---------|---------------|
| **Ollama** (local) | `http://127.0.0.1:11434` | Llama3 — AI cleanup, doc overview, question extraction | Ingestion, Structuring, PYQ |
| **Gemini API** (cloud) | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.5-flash` — slide classification | Structuring |

### Environment Variables

| Variable | Required By | Description |
|----------|-------------|-------------|
| `GEMINI_API_KEY` | Structuring (slide_agent) | Google Gemini API key |
| `GROQ_API_KEY` | (unused, legacy config) | Was for Groq, now replaced by Gemini |

---

## 4. Stage 1 — Ingestion

**Module:** `ingestion/`  
**Entry point:** `run_ingestion(source=None)` or `python -m ingestion [file]`  
**Input:** PDF/PPTX files in `uploads/`  
**Output:** Markdown files in `knowledge/` (one `.md` per source file)

### 6-Stage Pipeline (`pipeline.py`)

```
PDF / PPTX
    │
    ▼
Stage 1 — Native Parsing              [SERIAL per file]
    │   PyMuPDF (PDF) or python-pptx (PPTX)
    │   Output: list[dict] with text_blocks, image_blocks, table hints per page
    │
    ▼
Stage 2 — Block Segmentation          [SERIAL]
    │   Classifies each page into: text blocks, image blocks, table hints
    │   Output: text_map, ocr_jobs list, table_pages list
    │
    ▼
Stage 3 — Specialized Extraction      [PARALLEL — ThreadPoolExecutor]
    │   ├── OCR: PaddleOCR on all image_blocks (MAX_WORKERS=4 threads)
    │   └── Tables: Camelot on flagged pages (MAX_WORKERS=4 threads)
    │   OCR and Camelot run concurrently
    │
    ▼
Stage 4 — Unified Block Merge         [SERIAL]
    │   Per page: merge native text + OCR text + tables
    │   Priority: PPTX tables > Camelot tables > OCR-reconstructed tables
    │   Diagram-only pages (no text, only images, <30 chars OCR) → flagged
    │
    ▼
Stage 5 — AI Cleanup                  [PARALLEL — ThreadPoolExecutor]
    │   Ollama Llama3 on NATIVE TEXT ONLY (not OCR text)
    │   Design choice: OCR text is NOT sent to AI to avoid hallucination
    │   MAX_WORKERS=4 threads
    │
    ▼
Stage 6 — Markdown Generation         [SERIAL]
    Output: knowledge/<stem>.md
```

### Per-Page Data Flow (Stage 3 internal)

```python
# After Stage 1 parsing, each page dict looks like:
{
    "page_num": int,
    "text_blocks": [{"text": str}],       # native text regions
    "image_blocks": [{"image_bytes": bytes}],  # embedded images
    "has_tables": bool,                    # table detection hint
    "table_data": [[[str]]]               # PPTX native tables (if PPTX)
}
```

### After Stage 4 merge, each page dict:

```python
{
    "page_num": int,
    "native_text": str,      # joined native text blocks
    "ocr_text": str,         # joined OCR results from image blocks
    "tables": [[[str]]],     # all tables (PPTX + Camelot + OCR-reconstructed)
    "is_diagram": bool       # True if page is image-only with <30 chars OCR
}
```

### After Stage 5 cleanup, each page dict adds:

```python
{
    "cleaned_text": str       # AI-cleaned native text (or original on failure)
}
```

### OCR Engine Details (`ocr_engine.py`)

- **Library:** PaddleOCR 3.4
- **Thread-safe:** Singleton pattern with threading lock
- **Two modes:**
  - `ocr_image_bytes()` — Basic OCR, returns text string
  - `ocr_image_bytes_with_layout()` — Returns structured result + table detection
- **Table detection heuristic:** 4+ rows with 2+ cols aligned = table-like image
- `build_table_from_ocr(lines, img_height)` — Reconstructs markdown table from OCR entries

### AI Cleanup (`ai_cleanup.py`)

- **Model:** Ollama Llama3 (local, `http://127.0.0.1:11434`)
- **Strict prompt:** "Output ONLY text from input. No fabrication. Fix obvious OCR typos. Remove garbage tokens."
- **Rejection logic:** If AI output is empty or unchanged, returns original text
- **Only cleans native text** — OCR text passed through as-is

### Output Markdown Format (from Ingestion)

```markdown
# <filename without extension>
_Source: <original filename>_

---

## Page 1

<AI-cleaned native text>

### Table 1
| Col1 | Col2 | Col3 |
| --- | --- | --- |
| val  | val  | val  |

### Extracted from Image (OCR)
<OCR text if present and no tables>

---

## Page 2
> **[Diagram/Figure]** This page contains a visual diagram...

---
```

---

## 5. Stage 2 — Structuring

**Module:** `structuring/`  
**Entry point:** `await run_structuring(source=None)` or `python -m structuring [file]`  
**Input:** Markdown files in `knowledge/` (output of Ingestion)  
**Output:** Same markdown files, enriched in-place with metadata headers  
**Async:** Yes — uses `asyncio.run()`

### Two-Agent Architecture

```
knowledge/*.md (raw)
        │
        ▼
  ┌──────────────────────────────────┐
  │  Agent 1 — Ollama/Llama3 (local) │
  │                                   │
  │  Step 1: Document Overview        │   DocumentOverview
  │    → title, subject, chapters,    │     ↓
  │      overarching summary          │   (HANDOFF: output injected
  │                                   │    into Agent 2 system prompt)
  │  Step 2: Map (per chapter)        │
  │    → chapter summaries, concepts  │
  │                                   │
  │  Step 3: Reduce                   │   GlobalDocumentSummary
  │    → global summary, core topics  │
  └──────────────┬───────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────┐
  │  Agent 2 — Gemini 2.5 Flash      │
  │                                   │
  │  Sliding window: 25 slides/batch  │
  │  Rate limited: 10 calls/min       │
  │                                   │
  │  Per slide: type, concepts,       │   list[SlideMetadata]
  │    exam_signals, summary          │
  └──────────────┬───────────────────┘
                 │
                 ▼
  ┌──────────────────────────────────┐
  │  Writer                           │
  │  Injects metadata into markdown   │
  │  Overwrites knowledge/*.md        │
  └──────────────────────────────────┘
```

### Agent 1 Details (`file_agent.py`)

- **Framework:** OpenAI Agents SDK with `OpenAIProvider` pointed at Ollama
- **Three sub-agents,** each with `output_type` set to a Pydantic model (auto-parsing):
  - `overview_agent` → `DocumentOverview`
  - `chapter_agent` → `ChapterSummary` (runs once per chapter — Map step)
  - `global_summary_agent` → `GlobalDocumentSummary` (Reduce step)
- **Input to Step 1:** Truncated preview (first ~chars per slide) to fit Ollama context
- **Input to Step 2:** Full chapter text + overarching summary context
- **Input to Step 3:** All chapter summaries concatenated

### Agent 2 Details (`slide_agent.py`)

- **Framework:** Direct `client.beta.chat.completions.parse()` with `response_format=SlideBatchResponse`
- **Model:** `gemini-2.5-flash` via OpenAI-compatible endpoint
- **Context injection (handoff):** `build_instructions_slide_agent(overview)` bakes Agent 1's output (title, subject, chapters) into the system prompt
- **Sliding window:** 25 slides per API call
- **Rate limiter:** Async token-bucket, 10 calls/min
- **Fallback:** On API failure, slides get `SlideType.OTHER` with error message

### SlideType Classification

| Type | Description |
|------|-------------|
| `definition` | Defines a term or concept |
| `syntax/code` | Code snippets, syntax examples |
| `comparison` | Compares two or more concepts |
| `numerical_example` | Contains calculations, formulas with numbers |
| `diagram_explanation` | Explains a visual/diagram |
| `summary` | Recap/summary slide |
| `concept` | General concept explanation |
| `example` | Worked example (non-numerical) |
| `table` | Primarily tabular data |
| `other` | Doesn't fit above categories |

### Enriched Markdown Format (after Structuring)

```markdown
# Document Title
_Source: filename.pdf_

---

## Document Overview

**Subject:** Computer Architecture
**Summary:** This document covers...
**Core Topics:** ARM Architecture, Pipelining, Thumb Instructions
**Chapters:**
  - **Introduction** (slides 1-3): overview, history
  - **Instruction Decoding** (slides 4-8): decode stages, formats

---

## Page 1

> **Title:** Introduction | **Type:** concept | **Concepts:** ARM, ISA | **Exam Signal:** No
> **Summary:** Introduces the ARM instruction set architecture.

<original slide content preserved below>

---

## Page 2
...
```

---

## 6. Stage 3 — Indexing

**Module:** `indexing/`  
**Entry point:** `run_indexing(filepath=None, force=False)` or `python -m indexing [file] [--force]`  
**Input:** Enriched markdown files in `knowledge/` (output of Structuring)  
**Output:** Records in ChromaDB + SQLite  
**Prerequisite:** File must contain `## Document Overview` block (structuring must have run)

### Pipeline Per File (`pipeline.py`)

```
enriched knowledge/*.md
        │
        ▼
Step 1 — MD5 hash → check SQLite cache
        │   If hash exists AND all slides embedded → SKIP (cached)
        │
        ▼
Step 2 — Verify structured (check for "## Document Overview")
        │
        ▼
Step 3 — Parse enriched markdown → DocMeta + list[SlideMeta]
        │   Uses md_reader.py regex parser
        │
        ▼
Step 4 — Upsert Document record in SQLite
        │
        ▼
Step 5 — Upsert each Slide record in SQLite
        │
        ▼
Step 6 — Build embedding text per slide
        │   Format: "summary | concepts | raw_text" (truncated to 2000 chars)
        │
        ▼
Step 7 — Batch-encode with sentence-transformers     [SERIAL, batch_size=64]
        │   Model: intfloat/e5-large-v2, 1024-dim vectors
        │   Prefix: "passage: " for documents
        │
        ▼
Step 8 — Upsert into ChromaDB with metadata
        │   ID format: "doc{doc_id}_page{page_number}"
        │
        ▼
Step 9 — Mark slides as embedded in SQLite (is_embedded=True)
```

### Embedding Model

- **Model:** `intfloat/e5-large-v2` (HuggingFace, ~1.3 GB, no API key)
- **Dimensions:** 1024
- **Critical requirement:** e5 models need prefix:
  - `"passage: "` — when indexing documents
  - `"query: "` — when searching
- **Embedding text construction:** `build_embed_text(summary, concepts, raw_text)` → `"summary | concepts | raw_text"` truncated to 2000 chars
- **Batch encoding:** 64 slides per batch

### ChromaDB Record Format

```python
{
    "id": "doc{doc_id}_page{page_number}",   # e.g. "doc1_page3"
    "embedding": [float × 1024],              # e5-large-v2 vector
    "document": "summary | concepts | raw_text",  # searchable text
    "metadata": {
        "source_file": "3.md",
        "page_number": 3,
        "slide_type": "concept",
        "concepts": "ARM, Thumb, ISA",
        "chapter": "Introduction"
    }
}
```

- **Collection name:** `"slides"`
- **Distance metric:** Cosine similarity (`hnsw:space: cosine`)

### What Gets Stored Where

| Data | ChromaDB | SQLite |
|------|----------|--------|
| Embedding vectors | ✅ | ✗ |
| Slide raw text | ✅ (in `document` field) | ✅ (`raw_text`) |
| Slide metadata (type, concepts, chapter) | ✅ (in `metadata`) | ✅ |
| Slide summary | ✗ | ✅ |
| Document-level info (subject, summary, chapters) | ✗ | ✅ |
| `pyq_hit_count`, `importance_score` | ✗ | ✅ (dynamic) |
| PYQ questions & matches | ✗ | ✅ |

**Rule:** ChromaDB = vector search only. SQLite = source of truth for all data + dynamic scores.

---

## 7. Stage 4 — PYQ Mapping

**Module:** `pyq/`  
**Entry point:** `run_pyq_pipeline(filepath=None, force=False)` or `python -m pyq [file] [--force]`  
**Input:** PDF files in `pyq_uploads/`  
**Output:** Records in SQLite (pyq_questions, pyq_matches tables) + updated importance scores  
**Prerequisite:** Indexing must have run first (slides must exist in ChromaDB + SQLite)

### 3-Phase Pipeline (`pipeline.py`)

```
pyq_uploads/*.pdf
        │
        ▼
Phase A — Text Extraction                    [IO-bound, parallelizable across files]
        │   Stage 1: PyMuPDF native text + render pages at 2x zoom as PNG
        │   Stage 2: PaddleOCR on all rendered images (parallel, 3 workers)
        │   No Camelot — table extraction not useful on scanned PYQ text
        │   Output: concatenated text from all pages
        │
        ▼
Phase B — LLM Question Extraction            [API-bound, parallelizable]
        │   Ollama Llama3 via OpenAI Agents SDK
        │   output_type=ExtractedQuestionList (auto-parsed)
        │   Strict prompt: extract ONLY exam questions, not headers/footers
        │   Output: list[ExtractedQuestion] with text, marks, subtopic
        │
        ▼
Phase C — Hybrid Search + DB Write           [SERIALIZED via threading.Lock]
        │
        │   For each question:
        │     1. Dense search: embed question with e5 → query ChromaDB (top 20)
        │     2. Sparse search: BM25 over all slide texts (top 20)
        │     3. RRF Fusion: combine ranks → score each slide
        │     4. Filter: top 5 results above threshold (0.01)
        │     5. Record: insert PYQQuestion + PYQMatch in SQLite
        │     6. Increment slide.pyq_hit_count
        │
        ▼
Global Recomputation                          [SERIAL, after all files]
        Recompute importance_score for ALL slides
```

### Hybrid Search Details (`hybrid_search.py`)

```
Question text
    │
    ├──→ Dense Search (ChromaDB)
    │      embed question with "query: " prefix
    │      cosine similarity → top 20 results
    │      returns: list of {slide_id_key, doc_id, page_number, rank}
    │
    └──→ Sparse Search (BM25)
           tokenize question (lowercase, alphanumeric)
           BM25Okapi scoring → top 20 results
           returns: list of {slide_id, doc_id, page_number, rank}
    │
    ▼
RRF Fusion
    For each unique slide across both result sets:
      RRF(slide) = Σ 1/(K + rank_i)    where K=60
    Sort by RRF score descending
    │
    ▼
Filter
    Keep top 5 (RRF_TOP_K)
    Discard if RRF score < 0.01 (RRF_SCORE_THRESHOLD)
```

### Importance Score Formula (`mapper.py`)

```
importance_score = 0.5 × normalized_pyq_freq
                 + 0.3 × slide_emphasis
                 + 0.2 × concept_importance

Where:
  normalized_pyq_freq = slide.pyq_hit_count / max(pyq_hit_count across all slides)
  slide_emphasis       = 1.0 if slide.exam_signal else 0.0
  concept_importance   = min(num_concepts / 5, 1.0)
```

After all PYQ files are processed, `recompute_importance_scores(session)` runs globally to normalize across all slides.

### BM25 Index (`bm25_search.py`)

- **Built fresh** every time Phase C runs (from all `is_embedded=True` slides in SQLite)
- **Tokenization:** lowercase, regex `[a-z0-9]+`
- **Searchable text per slide:** `summary + concepts + raw_text` (same as embedding text)
- **Library:** `rank_bm25.BM25Okapi`

---

## 8. Database Schemas

### SQLite (`examai.db`) — 4 Tables

#### `documents`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, autoincrement | |
| `filename` | String | NOT NULL | Original file name (e.g. "3.md") |
| `file_hash` | String | NOT NULL, UNIQUE, INDEXED | MD5 of the knowledge markdown file |
| `processed_at` | DateTime | NOT NULL | UTC timestamp |
| `status` | String | NOT NULL, default="pending" | "pending" or "processed" |
| `subject` | String | nullable | From Agent 1 overview |
| `summary` | Text | nullable | Global document summary |
| `core_topics` | Text | nullable | Comma-separated topic list |
| `chapters_json` | Text | nullable | JSON array: `[{name, slide_range, topics}]` |
| `total_slides` | Integer | default=0 | Total slides in document |

#### `slides`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, autoincrement | |
| `doc_id` | Integer | FK → documents.id, INDEXED | |
| `page_number` | Integer | NOT NULL | 1-based page/slide number |
| `slide_type` | String | nullable | From Agent 2 (e.g. "concept", "definition") |
| `exam_signal` | Boolean | default=False | True if slide has exam hints |
| `raw_text` | Text | nullable | Original slide text content |
| `summary` | Text | nullable | Agent 2 generated summary |
| `concepts` | Text | nullable | Comma-separated concept list |
| `chapter` | String | nullable | Chapter name (resolved from doc chapters) |
| `is_embedded` | Boolean | default=False | True after ChromaDB upsert |
| `pyq_hit_count` | Integer | default=0 | Times matched by PYQ questions |
| `importance_score` | Float | default=0.0 | Computed score (0.0 – 1.0) |

**Unique constraint:** `(doc_id, page_number)`

#### `pyq_questions`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, autoincrement | |
| `question_text` | Text | NOT NULL | Full extracted question text |
| `source_file` | String | nullable | PYQ filename (e.g. "PyqCA.pdf") |
| `embedding_id` | String | nullable | (reserved, not currently used) |

#### `pyq_matches`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `pyq_id` | Integer | PK, FK → pyq_questions.id | |
| `slide_id` | Integer | PK, FK → slides.id | |
| `similarity_score` | Float | NOT NULL | RRF fusion score |

**Composite PK:** `(pyq_id, slide_id)`

### SQLite Config

- **Path:** `ExamAI/examai.db`
- **Journal mode:** WAL (Write-Ahead Logging)
- **Foreign keys:** Enabled via PRAGMA on every connection
- **Connection pooling:** SQLAlchemy engine with `pool_pre_ping=True`
- **Thread safety:** `check_same_thread=False` — multiple threads can share the engine
- **Session pattern:** `get_db()` context manager — auto-commits on success, rolls back on exception

### ChromaDB (`chromadb_store/`)

- **Client:** `PersistentClient` (disk-backed)
- **Collection:** `"slides"` with cosine distance (`hnsw:space: cosine`)
- **ID format:** `"doc{doc_id}_page{page_number}"`
- **Record count:** Matches total embedded slides

---

## 9. Pydantic Schemas (Data Contracts)

### Structuring Module (`structuring/schemas.py`)

```python
# Input to pipeline
ParsedSlide:
    slide_number: int
    header: str                  # "## Page N"
    content: str                 # full slide text
    preview: str                 # truncated for Ollama
    has_table: bool
    has_ocr: bool
    char_count: int

# Agent 1, Step 1 output
DocumentOverview:
    document_title: str
    subject: str
    overarching_summary: str     # 2-3 sentences
    chapters: list[ChapterInfo]  # [{chapter_name, slide_range, key_topics}]
    total_slides: int

# Agent 1, Map step output (per chapter)
ChapterSummary:
    chapter_name: str
    summary: str                 # 3-5 sentences
    key_concepts: list[str]
    has_numerical_examples: bool

# Agent 1, Reduce step output
GlobalDocumentSummary:
    document_title: str
    subject: str
    global_summary: str
    chapter_summaries: list[ChapterSummary]
    core_topics: list[str]
    total_chapters: int

# Agent 2 output (per slide)
SlideMetadata:
    slide_number: int
    parent_topic: str
    slide_type: SlideType        # enum (10 values)
    core_concepts: list[str]
    exam_signals: bool
    slide_summary: str           # 1-2 sentences

# Agent 2 batch response
SlideBatchResponse:
    slides: list[SlideMetadata]
```

### PYQ Module (`pyq/schemas.py`)

```python
ExtractedQuestion:
    question_number: int
    question_text: str
    marks: int | None
    subtopic_hint: str

ExtractedQuestionList:
    source_info: str             # e.g. "Midterm 2024"
    questions: list[ExtractedQuestion]

RRFResult:
    slide_id: int
    doc_id: int
    page_number: int
    source_file: str
    rrf_score: float
    dense_rank: int | None
    sparse_rank: int | None
```

### Indexing Module (`indexing/md_reader.py`)

```python
DocMeta:                         # plain class, not Pydantic
    title: str
    subject: str
    summary: str
    core_topics: list[str]
    chapters: list[dict]         # [{name, slide_range, topics}]

SlideMeta:                       # plain class, not Pydantic
    page_number: int
    parent_topic: str
    slide_type: str
    concepts: list[str]
    exam_signal: bool
    summary: str
    raw_text: str
    chapter: str
```

---

## 10. Concurrency & Parallelism Map

### Stage 1 — Ingestion

| Operation | Execution | Workers | Notes |
|-----------|-----------|---------|-------|
| Native parsing (Stage 1) | Serial | 1 | Single file at a time |
| Block segmentation (Stage 2) | Serial | 1 | |
| OCR on image blocks (Stage 3) | **Parallel** | 4 threads | `ThreadPoolExecutor(max_workers=4)` |
| Camelot table extraction (Stage 3) | **Parallel** | 4 threads | Runs concurrently with OCR |
| Block merge (Stage 4) | Serial | 1 | |
| AI cleanup via Ollama (Stage 5) | **Parallel** | 4 threads | Multiple Ollama calls concurrent |
| Markdown generation (Stage 6) | Serial | 1 | |
| **Multiple files** | **Serial** | 1 | Files processed one at a time |

### Stage 2 — Structuring

| Operation | Execution | Workers | Notes |
|-----------|-----------|---------|-------|
| Agent 1 Step 1 (overview) | Serial | 1 | Single Ollama call |
| Agent 1 Step 2 (chapter map) | **Serial** | 1 | One Ollama call per chapter, sequential |
| Agent 1 Step 3 (reduce) | Serial | 1 | Single Ollama call |
| Agent 2 (slide batches) | **Serial** | 1 | One Gemini call per batch (25 slides), rate-limited 10/min |
| **Multiple files** | **Serial** | 1 | Files processed one at a time |

### Stage 3 — Indexing

| Operation | Execution | Workers | Notes |
|-----------|-----------|---------|-------|
| Parse markdown | Serial | 1 | |
| SQLite upserts | Serial | 1 | |
| Batch embedding | Serial | 1 | Uses GPU if available, batch_size=64 |
| ChromaDB upsert | Serial | 1 | |
| **Multiple files** | **Serial** | 1 | Each file gets own session, processed sequentially |

### Stage 4 — PYQ

| Operation | Execution | Workers | Notes |
|-----------|-----------|---------|-------|
| Phase A: Text extraction | **Parallel across files** | 3 threads | OCR internally parallelized too (3 workers) |
| Phase B: LLM extraction | **Parallel across files** | 3 threads | Multiple Ollama calls |
| Phase C: Search + DB write | **Serialized** | 1 (lock) | `threading.Lock` ensures SQLite safety |
| BM25 index build | Serial | 1 | Built once per Phase C execution |
| **Multiple files** | **Parallel** | 3 threads | `ThreadPoolExecutor(max_workers=3)` |
| **Single file** | Serial | 1 | No thread overhead |
| Importance recomputation | Serial | 1 | Runs once after all files done |

### Can Stages Run Concurrently?

| Combination | Safe? | Why |
|-------------|-------|-----|
| Ingestion + Ingestion (diff files) | ❌ | Serial by design |
| Structuring + Structuring | ❌ | Serial by design |
| Indexing + Indexing | ❌ | Serial by design, shared session |
| PYQ + PYQ (diff files) | ✅ | Built-in ThreadPool, DB writes locked |
| Ingestion + PYQ | ⚠️ | Both use PaddleOCR singleton — potential contention |
| Indexing → PYQ | ✅ | PYQ reads from Indexing output, no conflict |
| **Different stages, different files** | ✅ | As long as no file is in two stages simultaneously |

---

## 11. Input / Output Formats

### What Goes Into Each Stage

| Stage | Input | Source | Format |
|-------|-------|--------|--------|
| Ingestion | PDF, PPTX files | `uploads/` | Binary files |
| Structuring | Raw markdown | `knowledge/*.md` | Markdown (from Ingestion) |
| Indexing | Enriched markdown | `knowledge/*.md` | Markdown (from Structuring) |
| PYQ | PDF files | `pyq_uploads/` | Binary files (scanned exams) |

### What Comes Out of Each Stage

| Stage | Output | Destination | Format |
|-------|--------|-------------|--------|
| Ingestion | Per-file markdown | `knowledge/<stem>.md` | Markdown with `## Page N` sections |
| Structuring | Enriched markdown (in-place) | `knowledge/<stem>.md` | Same file, metadata injected |
| Indexing | DB records | `examai.db` + `chromadb_store/` | SQLite rows + ChromaDB vectors |
| PYQ | Match records + scores | `examai.db` | SQLite rows (pyq_questions, pyq_matches, updated slides) |

### Tracker Files (JSON)

**`ingestion/processed.json`:**
```json
{
    "3.pdf": "2026-03-06T17:24:20.123456"
}
```

**`structuring/structured.json`:**
```json
{
    "3.md": {
        "structured_at": "2026-03-06T18:00:00",
        "output_path": "E:\\Project\\ExamAI\\knowledge\\3.md"
    }
}
```

**`pyq/pyq_processed.json`:**
```json
{
    "PyqCA.pdf": {
        "processed_at": "2026-03-07T10:00:00",
        "questions_extracted": 8,
        "total_matches": 40
    }
}
```

---

## 12. Duplicate Prevention & Caching

Every stage has duplicate prevention:

| Stage | Fast Check (Pre-filter) | Authoritative Check | Re-run Override |
|-------|------------------------|---------------------|-----------------|
| Ingestion | `processed.json` — filename lookup | (JSON is authoritative here) | Delete entry from JSON |
| Structuring | `structured.json` — filename lookup | (JSON is authoritative here) | Delete entry from JSON |
| Indexing | MD5 hash in SQLite `documents.file_hash` | All slides `is_embedded=True` | `--force` flag |
| PYQ | `pyq_processed.json` — filename lookup | SQLite `pyq_questions.source_file` count | `--force` flag |

**Two-layer pattern in PYQ:**
1. JSON tracker checked first (fast, avoids DB query)
2. SQLite checked second (authoritative, catches cases where JSON is out of sync)
3. If SQLite says "already ingested" but JSON doesn't have it → JSON is synced

**Indexing cache logic:**
1. MD5 hash the markdown file
2. If hash exists in SQLite AND all slides have `is_embedded=True` → Skip entirely
3. If hash exists but some slides not embedded → Re-embed only those
4. If hash is new → Full re-index (also deletes old ChromaDB records for that source)

---

## 13. Configuration Reference

### Ingestion (`ingestion/config.py`)

| Setting | Value | Description |
|---------|-------|-------------|
| `UPLOAD_DIR` | `ExamAI/uploads/` | Source file drop zone |
| `KNOWLEDGE_DIR` | `ExamAI/knowledge/` | Markdown output directory |
| `SUPPORTED_EXTENSIONS` | `.pdf`, `.pptx`, `.ppt` | Accepted file types |
| `OCR_LANG` | `"en"` | PaddleOCR language |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama API |
| `OLLAMA_MODEL` | `llama3:latest` | Model for AI cleanup |
| `MAX_WORKERS` | `4` | Thread pool size |

### Structuring (`structuring/config.py`)

| Setting | Value | Description |
|---------|-------|-------------|
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434/v1` | OpenAI-compatible endpoint |
| `OLLAMA_MODEL` | `llama3` | Agent 1 model |
| `PREVIEW_CHAR_LIMIT` | `6000` | Max chars for Ollama Step 1 preview |
| `GEMINI_API_KEY` | env `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` | Gemini endpoint |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Agent 2 model |
| `SLIDE_BATCH_SIZE` | `25` | Slides per Gemini API call |
| `GEMINI_MAX_CALLS_PER_MINUTE` | `10` | Rate limit |

### Indexing (`indexing/config.py`)

| Setting | Value | Description |
|---------|-------|-------------|
| `SQLITE_DB_PATH` | `ExamAI/examai.db` | SQLite file location |
| `CHROMA_DB_DIR` | `ExamAI/chromadb_store/` | ChromaDB persistence |
| `CHROMA_COLLECTION` | `"slides"` | Collection name |
| `EMBEDDING_MODEL` | `intfloat/e5-large-v2` | 1024-dim embeddings |
| `EMBEDDING_BATCH_SIZE` | `64` | Slides per encoding batch |
| `MAX_WORKERS` | `4` | Thread pool size |

### PYQ (`pyq/config.py`)

| Setting | Value | Description |
|---------|-------|-------------|
| `PYQ_UPLOAD_DIR` | `ExamAI/pyq_uploads/` | PYQ file drop zone |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434/v1` | For question extraction |
| `OLLAMA_MODEL` | `llama3` | LLM for extraction |
| `DENSE_TOP_N` | `20` | ChromaDB results per query |
| `SPARSE_TOP_N` | `20` | BM25 results per query |
| `RRF_K` | `60` | RRF smoothing constant |
| `RRF_TOP_K` | `5` | Final results per question |
| `RRF_SCORE_THRESHOLD` | `0.01` | Minimum RRF score |
| `WEIGHT_PYQ_FREQUENCY` | `0.5` | Importance formula weight |
| `WEIGHT_SLIDE_EMPHASIS` | `0.3` | Importance formula weight |
| `WEIGHT_CONCEPT_IMPORTANCE` | `0.2` | Importance formula weight |
| `MAX_WORKERS` | `3` | Concurrent PYQ files |
| `SUPPORTED_EXTENSIONS` | `.pdf`, `.pptx`, `.ppt` | Accepted PYQ file types |

---

## 14. CLI Commands

```bash
# Activate virtual environment first
cd ExamAI
.\env\Scripts\Activate.ps1

# Stage 1: Ingest all pending files in uploads/
python -m ingestion

# Stage 1: Ingest a specific file
python -m ingestion uploads/lecture.pdf

# Stage 2: Structure all pending knowledge files
python -m structuring

# Stage 2: Structure a specific file
python -m structuring knowledge/3.md

# Stage 3: Index all knowledge files
python -m indexing

# Stage 3: Index specific file
python -m indexing knowledge/3.md

# Stage 3: Force re-index (ignore cache)
python -m indexing --force

# Stage 4: Process all PYQ files
python -m pyq

# Stage 4: Process specific PYQ
python -m pyq pyq_uploads/midterm.pdf

# Stage 4: Force re-process
python -m pyq --force
```

### Programmatic Entry Points

```python
# Ingestion (synchronous)
from ingestion import run_ingestion
results = run_ingestion()                    # all pending
results = run_ingestion("uploads/file.pdf")  # single file
# Returns: list[str] — paths to generated markdown files

# Structuring (async)
from structuring import run_structuring
import asyncio
results = asyncio.run(run_structuring())                       # all pending
results = asyncio.run(run_structuring("knowledge/3.md"))       # single file
# Returns: list[str] — paths to structured markdown files

# Indexing (synchronous)
from indexing.pipeline import run_indexing
results = run_indexing()                             # all files
results = run_indexing("knowledge/3.md", force=True) # single, force
# Returns: list[dict] — [{filename, status, slides_indexed, cached}]

# PYQ (synchronous)
from pyq import run_pyq
results = run_pyq()                                  # all files
results = run_pyq("pyq_uploads/exam.pdf", force=True)
# Returns: list[dict] — [{filename, status, questions, matches}]
```

---

## 15. What's Implemented vs What's Pending

### Fully Implemented

| Feature | Module | Status |
|---------|--------|--------|
| PDF parsing (PyMuPDF) | Ingestion | ✅ Done |
| PPTX parsing (python-pptx) | Ingestion | ✅ Done |
| OCR (PaddleOCR) with layout detection | Ingestion | ✅ Done |
| Table extraction (Camelot + OCR reconstruction) | Ingestion | ✅ Done |
| AI text cleanup (Ollama Llama3) | Ingestion | ✅ Done |
| Markdown generation | Ingestion | ✅ Done |
| Document overview agent (Ollama, Map-Reduce) | Structuring | ✅ Done |
| Slide classification agent (Gemini) | Structuring | ✅ Done |
| Agent 1 → Agent 2 handoff | Structuring | ✅ Done |
| Enriched markdown writing | Structuring | ✅ Done |
| Sentence-Transformer embedding (e5-large-v2) | Indexing | ✅ Done |
| ChromaDB vector store | Indexing | ✅ Done |
| SQLite ORM (SQLAlchemy) | Indexing | ✅ Done |
| MD5 caching for re-indexing | Indexing | ✅ Done |
| PYQ text extraction (scanned PDFs) | PYQ | ✅ Done |
| LLM question extraction | PYQ | ✅ Done |
| Hybrid search (Dense + BM25 + RRF) | PYQ | ✅ Done |
| Slide-to-question linking | PYQ | ✅ Done |
| Importance score computation | PYQ | ✅ Done |
| Duplicate prevention (2-layer) | All | ✅ Done |
| CLI for all stages | All | ✅ Done |

### Pending (Next Phase)

| Feature | Description | Data Available? |
|---------|-------------|-----------------|
| **Priority Scoring System** | Categorize concepts as High / Medium / Low priority based on importance_score | Yes — `slides.importance_score` exists |
| **Exam-Focused Study Plan Generator** | Generate structured revision output grouping topics by priority | Yes — all data in SQLite |
| **Last-Day Revision Mode** | Given X hours, produce time-allocated study order | Yes — importance scores + slide types available |
| **Topic Coverage Detection** | "Is X covered in my slides?" — semantic query interface | Yes — ChromaDB + embedder ready for queries |
| **Concept Frequency Tracking** | Track repeated concepts across slides, beyond PYQ hits | Partial — `concepts` column exists, needs aggregation |
| **Numerical/Formula Detection** | Surface slides of type `numerical_example` for focused practice | Yes — `slide_type` available |
| **Web Interface / API** | Frontend for upload, search, study plan, revision | `database.py` has FastAPI `Depends(get_db)` comment ready |
| **Async Document Ingestion** | Queue-based upload → background processing | Not yet — currently blocking CLI |

### Data Already Available for Next Phase

All the raw ingredients exist in SQLite for building the pending features:

```sql
-- High priority slides (ready for study plan)
SELECT s.page_number, s.summary, s.concepts, s.importance_score, d.filename
FROM slides s JOIN documents d ON s.doc_id = d.id
WHERE s.importance_score > 0.5
ORDER BY s.importance_score DESC;

-- Topic coverage check (needs embedding query + this SQL)
SELECT s.page_number, s.summary, s.concepts, d.filename
FROM slides s JOIN documents d ON s.doc_id = d.id
WHERE s.concepts LIKE '%TCP%';

-- Numerical problems
SELECT s.page_number, s.summary, d.filename
FROM slides s JOIN documents d ON s.doc_id = d.id
WHERE s.slide_type = 'numerical_example';

-- PYQ → Slide mapping
SELECT q.question_text, q.source_file, m.similarity_score,
       s.page_number, s.summary, d.filename
FROM pyq_matches m
JOIN pyq_questions q ON m.pyq_id = q.id
JOIN slides s ON m.slide_id = s.id
JOIN documents d ON s.doc_id = d.id
ORDER BY m.similarity_score DESC;
```

---

## 16. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| OCR text is NOT sent to AI cleanup | Prevents hallucination — AI only cleans reliably parsed native text |
| Agent 1 output injected into Agent 2 system prompt | Gives slide classifier document-level context for better classification |
| ChromaDB for vectors, SQLite for everything else | ChromaDB optimized for vector search; SQLite handles relational queries, dynamic scores, and is the source of truth |
| e5-large-v2 with prefix requirement | High-quality embeddings, but MUST use "passage:" / "query:" prefixes |
| RRF fusion instead of single search | Combines strengths of dense (semantic) and sparse (keyword) search |
| BM25 index rebuilt per PYQ run | Ensures index reflects latest embedded slides; fast enough in memory |
| JSON tracker + SQLite (2-layer dedup) | JSON is fast pre-filter; SQLite is authoritative — covers edge cases where JSON gets out of sync |
| Enriched markdown overwrites original | Single source of truth — no separate structured files to keep in sync |
| Slides as individual knowledge units | Each slide gets its own embedding, metadata, and importance score |
| Importance scores computed globally after all PYQ files | Normalization needs max across all slides — can't compute per-file |

---

*Generated: 2026-03-08*
