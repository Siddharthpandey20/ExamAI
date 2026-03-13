# ExamPrep AI — Frontend Engineering Reference

> **For the frontend developer.** This document is the single source of truth for building the UI. It covers every API route, exact request/response shapes, state flows, error handling, SSE streaming, and UI recommendations. Read it fully before writing a single component.

---

## Table of Contents

1. [Tech Stack & Connection Details](#1-tech-stack--connection-details)
2. [Core Concepts](#2-core-concepts)
3. [Global Rules & Conventions](#3-global-rules--conventions)
4. [API Reference — Subjects](#4-api-reference--subjects)
5. [API Reference — Upload](#5-api-reference--upload)
6. [API Reference — Jobs (with SSE)](#6-api-reference--jobs-with-sse)
7. [API Reference — Documents](#7-api-reference--documents)
8. [API Reference — Search & Coverage](#8-api-reference--search--coverage)
9. [API Reference — Exam Intelligence](#9-api-reference--exam-intelligence)
10. [API Reference — Health](#10-api-reference--health)
11. [Shared Object Shapes](#11-shared-object-shapes)
12. [Error Handling](#12-error-handling)
13. [Application Flow & Page Architecture](#13-application-flow--page-architecture)
14. [Priority Colour System](#14-priority-colour-system)
15. [Slide Type Taxonomy](#15-slide-type-taxonomy)

---

## 1. Tech Stack & Connection Details

| Item | Value |
|---|---|
| Base URL (dev) | `http://localhost:8000` |
| All API routes | `/api/...` |
| CORS | All origins allowed (`*`) during development |
| Content-Type | `application/json` for all JSON endpoints |
| File uploads | `multipart/form-data` |
| Real-time updates | Server-Sent Events (SSE) |
| Docs (auto-generated) | `http://localhost:8000/docs` |

---

## 2. Core Concepts

Understanding these five concepts will prevent most integration mistakes.

### Subject
A subject is the top-level container (e.g. `COMPUTER NETWORKS`). All names are **stored and queried as UPPERCASE**. Always send subject names uppercase. A subject must be created before any files can be uploaded to it.

### Document
One uploaded file (PDF or PPTX) = one Document. A Document has a `status` field that goes from `pending` → `processed`. Slides only exist after a document is processed.

### Slide
Every page/slide of a processed document becomes a Slide. Each slide has AI-extracted metadata: `slide_type`, `chapter`, `concepts`, `summary`, `importance_score`, `exam_signal`, and `pyq_hit_count`.

### Job
Every file upload fires an async background pipeline (Celery). A Job tracks that pipeline's progress in multiple phases. The UI uses jobs to show upload/processing feedback.

### PYQ (Past Year Questions)
Uploaded exam question papers. After processing, each question is matched to the most relevant slides. This powers the priority scoring and study plan features.

---

## 3. Global Rules & Conventions

- **Subject names must be uppercase.** The backend normalizes them. Always send and display as uppercase (e.g., `"CN"`, `"DBMS"`).
- **All timestamps** returned from the API are strings in IST (`"2026-03-11 14:32:51 IST"`) or ISO-8601 UTC (`"2026-03-11T09:02:51.000Z"`).
- **`importance_score`** is a float `0.0 – 1.0`. Higher = more exam-critical.
  - `>= 0.4` → High Priority (🔴 red)
  - `>= 0.15` → Medium Priority (🟡 yellow)
  - `< 0.15` → Low Priority (🟢 green)
- **`mode` field** in search/exam routes accepts `"fast"` (default) or `"reasoning"`. Fast is instant; reasoning is slower but more thorough (multi-step AI agent). Always default to `"fast"`.
- **`force` query param** — adding `?force=true` to any AI endpoint bypasses the cache and forces a fresh LLM call. Use only for an explicit user "Refresh" action.
- **Upload order matters**: PYQ upload will be rejected with `409` if no processed study material exists for that subject yet.
- **`concepts` field in Slide** is a comma-separated string, e.g. `"TCP, congestion control, sliding window"`. Split on `,` to render as chips/tags.
- **`core_topics` field in Document** is also comma-separated.

---

## 4. API Reference — Subjects

### `GET /api/subjects`

List all subjects with summary statistics.

**Response** `200` — `Array<SubjectStats>`
```json
[
  {
    "name": "COMPUTER NETWORKS",
    "created_at": "2026-03-10T18:22:00.000Z",
    "documents": 3,
    "slides": 187,
    "pyq_papers": 2,
    "pyq_questions": 45,
    "has_pyq": true
  }
]
```

---

### `POST /api/subjects`

Create a new subject.

**Request body**
```json
{ "name": "COMPUTER NETWORKS" }
```

**Response** `201` — `SubjectStats`
```json
{
  "name": "COMPUTER NETWORKS",
  "created_at": "2026-03-11T12:00:00.000Z",
  "documents": 0,
  "slides": 0,
  "pyq_papers": 0,
  "pyq_questions": 0,
  "has_pyq": false
}
```

**Errors**
| Status | When |
|---|---|
| `400` | Empty subject name |
| `409` | Subject already exists |

---

### `GET /api/subjects/{name}`

Full detail for one subject including a list of all its documents.

**Path param** — `name`: uppercase subject name (e.g. `COMPUTER NETWORKS`)

**Response** `200` — `SubjectDetail`
```json
{
  "name": "COMPUTER NETWORKS",
  "created_at": "2026-03-10T18:22:00.000Z",
  "documents": 3,
  "slides": 187,
  "pyq_papers": 2,
  "pyq_questions": 45,
  "has_pyq": true,
  "document_list": [
    {
      "id": 1,
      "filename": "unit1_datalink.pptx",
      "status": "processed",
      "total_slides": 62,
      "core_topics": "ARQ, flow control, HDLC",
      "processed_at": "2026-03-11T12:05:00.000Z"
    }
  ]
}
```

**Errors**
| Status | When |
|---|---|
| `404` | Subject not found |

---

## 5. API Reference — Upload

All uploads use `multipart/form-data`.

### `POST /api/upload/study-material`

Upload a lecture file (PDF / PPTX / PPT) for processing.

**Form fields**
| Field | Type | Required | Notes |
|---|---|---|---|
| `file` | file | ✅ | `.pdf`, `.pptx`, `.ppt` only |
| `subject` | string | ✅ | Must be an existing subject name |

**Response** `200`
```json
{
  "message": "File 'unit1.pdf' uploaded and queued for processing.",
  "job_id": 7,
  "subject": "COMPUTER NETWORKS",
  "filepath": "data/COMPUTER NETWORKS/uploads/unit1.pdf"
}
```

> **After this call:** Poll `GET /api/jobs/{job_id}` or open `GET /api/jobs/{job_id}/stream` for real-time status. The job phases are `ingest → structure → index`.

**Errors**
| Status | When |
|---|---|
| `400` | Unsupported file type |
| `404` | Subject does not exist |
| `500` | Job creation failed (backend error) |

---

### `POST /api/upload/pyq`

Upload a past-year question paper (PDF only).

**Form fields**
| Field | Type | Required | Notes |
|---|---|---|---|
| `file` | file | ✅ | `.pdf` only |
| `subject` | string | ✅ | Must have at least one `processed` study material document |

**Response** `200`
```json
{
  "message": "PYQ 'exam2024.pdf' uploaded and queued for processing.",
  "job_id": 12,
  "subject": "COMPUTER NETWORKS",
  "filepath": "data/COMPUTER NETWORKS/pyq_uploads/exam2024.pdf"
}
```

> **After this call:** Same as study material — poll or stream `GET /api/jobs/{job_id}`. The phases for PYQ are `ingest_pyq → extract → map`.

**Errors**
| Status | When |
|---|---|
| `400` | Unsupported file type |
| `404` | Subject does not exist |
| `409` | Subject has no processed study material yet |
| `500` | Job creation failed |

---

## 6. API Reference — Jobs (with SSE)

### `GET /api/jobs`

All jobs, newest first.

**Response** `200` — `Array<JobDetail>` (see [JobDetail](#jobdetail))

---

### `GET /api/jobs/active`

Only jobs with status `pending` or `processing`.

**Response** `200` — `Array<JobDetail>`

---

### `GET /api/jobs/overview`

Compact pipeline dashboard view: one row per file.

**Response** `200` — `Array<JobOverview>`
```json
[
  {
    "id": 7,
    "filename": "unit1.pdf",
    "job_type": "study_material",
    "status": "processing",
    "subject": "COMPUTER NETWORKS",
    "current_phase": "structure",
    "progress": "1/3",
    "overall_progress_pct": 33,
    "progress_detail": "Processing slide 24/62",
    "total_duration_sec": 18.4,
    "total_duration": "18.4s",
    "created_at": "2026-03-11 14:30:00 IST",
    "error": null
  }
]
```

---

### `GET /api/jobs/{job_id}`

Full status of a single job with phase-by-phase breakdown.

**Response** `200` — `JobDetail`
```json
{
  "id": 7,
  "filename": "unit1.pdf",
  "filepath": "data/COMPUTER NETWORKS/uploads/unit1.pdf",
  "job_type": "study_material",
  "status": "processing",
  "subject": "COMPUTER NETWORKS",
  "current_phase": "structure",
  "celery_chain_id": "abc123",
  "created_at": "2026-03-11 14:30:00 IST",
  "updated_at": "2026-03-11 14:30:18 IST",
  "error": null,
  "overall_progress_pct": 33,
  "total_duration_sec": 18.4,
  "total_duration": "18.4s",
  "phases": [
    {
      "phase": "ingest",
      "status": "completed",
      "celery_task_id": "task-001",
      "started_at": "2026-03-11 14:30:01 IST",
      "completed_at": "2026-03-11 14:30:08 IST",
      "duration_sec": 7.0,
      "duration": "7.0s",
      "error": null,
      "progress_pct": 100,
      "progress_detail": null
    },
    {
      "phase": "structure",
      "status": "running",
      "celery_task_id": "task-002",
      "started_at": "2026-03-11 14:30:09 IST",
      "completed_at": null,
      "duration_sec": null,
      "duration": null,
      "error": null,
      "progress_pct": 40,
      "progress_detail": "Processing slide 24/62"
    },
    {
      "phase": "index",
      "status": "pending",
      "celery_task_id": null,
      "started_at": null,
      "completed_at": null,
      "duration_sec": null,
      "duration": null,
      "error": null,
      "progress_pct": 0,
      "progress_detail": null
    }
  ]
}
```

**Job status values:** `pending` | `processing` | `completed` | `failed`

**Phase status values:** `pending` | `running` | `completed` | `skipped` | `failed`

**Study material phases (in order):** `ingest` → `structure` → `index`

**PYQ phases (in order):** `ingest_pyq` → `extract` → `map`

**Errors**
| Status | When |
|---|---|
| `404` | Job not found |

---

### `GET /api/jobs/{job_id}/stream` — SSE

Real-time Server-Sent Events stream for live job status. Connect once after upload and keep listening until the `complete` event fires.

**Response** `200` — `text/event-stream`

```
event: status
data: { ...JobDetail }

event: status
data: { ...JobDetail }

event: complete
data: { ...JobDetail }
```

Three SSE event types:
| Event name | When fired | Action |
|---|---|---|
| `status` | Every time job data changes | Update UI state |
| `complete` | Job reaches `completed` or `failed` | Close EventSource, refresh data |
| `error` | Job not found mid-stream | Show error toast, close stream |

**JavaScript example:**
```javascript
function trackJob(jobId, onUpdate, onComplete) {
  const es = new EventSource(`/api/jobs/${jobId}/stream`);

  es.addEventListener("status", (e) => {
    onUpdate(JSON.parse(e.data));
  });

  es.addEventListener("complete", (e) => {
    onComplete(JSON.parse(e.data));
    es.close();
  });

  es.addEventListener("error", () => {
    es.close();
  });

  return () => es.close(); // cleanup function
}
```

> The stream sends only when data changes and auto-closes when the job finishes. Poll interval is 2 seconds on the backend.

---

## 7. API Reference — Documents

Document-level views. Students see "which file has important content?" then drill down to slides.

### `GET /api/documents/{subject}`

All documents for a subject with per-document stats.

**Response** `200`
```json
{
  "subject": "COMPUTER NETWORKS",
  "total": 3,
  "documents": [
    {
      "id": 1,
      "filename": "unit1_datalink.pptx",
      "status": "processed",
      "subject": "COMPUTER NETWORKS",
      "ai_subject": "Computer Networks",
      "summary": "Covers data link layer protocols including flow control...",
      "core_topics": "ARQ, flow control, HDLC, sliding window",
      "total_slides": 62,
      "embedded_slides": 60,
      "total_pyq_hits": 18,
      "avg_importance": 0.312,
      "high_priority_slides": 14,
      "unique_concepts": 37,
      "top_concepts": ["ARQ", "hdlc", "flow control", "sliding window"],
      "chapters": [
        { "name": "Flow Control", "slide_range": "1-20", "topics": ["stop and wait", "sliding window"] },
        { "name": "ARQ Protocols", "slide_range": "21-45", "topics": ["go-back-n", "selective repeat"] }
      ],
      "processed_at": "2026-03-11T12:05:00.000Z"
    }
  ]
}
```

---

### `GET /api/documents/{subject}/{doc_id}`

Full document detail with all slides listed.

**Response** `200`
```json
{
  "id": 1,
  "filename": "unit1_datalink.pptx",
  "status": "processed",
  "subject": "COMPUTER NETWORKS",
  "ai_subject": "Computer Networks",
  "summary": "Covers data link layer...",
  "core_topics": "ARQ, flow control, HDLC",
  "chapters": [...],
  "total_slides": 62,
  "slides": [
    {
      "slide_id": 101,
      "page_number": 1,
      "slide_type": "concept",
      "chapter": "Flow Control",
      "concepts": "stop-and-wait, efficiency",
      "summary": "Introduction to flow control and why it is needed.",
      "exam_signal": false,
      "pyq_hit_count": 0,
      "importance_score": 0.12,
      "is_embedded": true
    }
  ]
}
```

---

### `GET /api/documents/{subject}/{doc_id}/concepts`

Concepts extracted from one document with frequency and slide locations.

**Query params**
| Param | Type | Notes |
|---|---|---|
| `q` | string | Optional keyword filter |

**Response** `200`
```json
{
  "subject": "COMPUTER NETWORKS",
  "doc_id": 1,
  "filename": "unit1_datalink.pptx",
  "total": 37,
  "concepts": [
    {
      "concept": "arq",
      "frequency": 8,
      "slides": [
        { "slide_id": 105, "page_number": 22, "slide_type": "definition", "importance_score": 0.52, "pyq_hit_count": 3 }
      ]
    }
  ]
}
```

---

### `GET /api/documents/{subject}/{doc_id}/pyq`

PYQ questions that matched slides in this document.

**Response** `200`
```json
{
  "subject": "COMPUTER NETWORKS",
  "doc_id": 1,
  "filename": "unit1_datalink.pptx",
  "total_questions": 8,
  "total_matches": 22,
  "questions": [
    {
      "question_id": 3,
      "question_text": "Explain Go-Back-N ARQ protocol with an example.",
      "source_file": "exam2024.pdf",
      "matched_slides": [
        {
          "slide_id": 112,
          "page_number": 30,
          "chapter": "ARQ Protocols",
          "concepts": "go-back-n, window size, retransmission",
          "summary": "Go-Back-N ARQ: sender retransmits all frames from error frame.",
          "similarity_score": 0.8832
        }
      ]
    }
  ]
}
```

---

### `GET /api/documents/{subject}/{doc_id}/priorities`

Priority tiers for slides in one document, with chapter-level aggregation.

**Response** `200`
```json
{
  "subject": "COMPUTER NETWORKS",
  "doc_id": 1,
  "filename": "unit1_datalink.pptx",
  "high": [ { "slide_id": 112, "page_number": 30, "slide_type": "concept", "chapter": "ARQ Protocols", "concepts": "go-back-n", "summary": "...", "importance_score": 0.61, "pyq_hit_count": 3 } ],
  "medium": [...],
  "low": [...],
  "stats": {
    "high_count": 14,
    "medium_count": 24,
    "low_count": 22,
    "total": 60
  },
  "chapters_ranked": [
    {
      "chapter": "ARQ Protocols",
      "slide_count": 24,
      "high_count": 9,
      "total_importance": 11.4,
      "total_pyq_hits": 12,
      "avg_importance": 0.475
    }
  ]
}
```

---

### `GET /api/documents/{subject}/{doc_id}/summary`

AI-generated summary of the document including key stats, chapter breakdown, and exam-relevant highlights.

---

## 8. API Reference — Search & Coverage

### `POST /api/search/query`

The main AI-powered search. Student types a question and gets an answer with slide references.

**Query params**
| Param | Type | Default | Notes |
|---|---|---|---|
| `force` | bool | `false` | Bypass cache |

**Request body**
```json
{
  "query": "Explain TCP congestion control",
  "subject": "COMPUTER NETWORKS",
  "mode": "fast"
}
```

**`mode` values:**
- `"fast"` — hybrid search → single LLM call → formatted answer (< 3s typical)
- `"reasoning"` — multi-step AI agent with tools, more thorough (10–30s)

**Response** `200` — Fast mode
```json
{
  "answer": "TCP Congestion Control uses four phases: Slow Start, Congestion Avoidance, Fast Retransmit, and Fast Recovery...\n\nKey slides:\n- **Page 32 of tcp_slides.pdf** — Slow Start algorithm and threshold\n- **Page 33 of tcp_slides.pdf** — AIMD explained with graph\n- **Page 35 of tcp_slides.pdf** — Numerical example with RTT calculation",
  "slides": [
    {
      "slide_id": 201,
      "page_number": 32,
      "filename": "tcp_slides.pdf",
      "chapter": "TCP Congestion Control",
      "slide_type": "concept",
      "importance_score": 0.73,
      "pyq_hit_count": 5,
      "rrf_score": 0.0312
    },
    {
      "slide_id": 202,
      "page_number": 33,
      "filename": "tcp_slides.pdf",
      "chapter": "TCP Congestion Control",
      "slide_type": "diagram_explanation",
      "importance_score": 0.58,
      "pyq_hit_count": 4,
      "rrf_score": 0.0285
    }
  ],
  "mode": "fast",
  "model_used": "llama-3.3-70b-versatile"
}
```

**Response — Reasoning mode** returns the same structure but `answer` is more detailed and structured.

**No results case:**
```json
{
  "answer": "No relevant slides found for 'TCP congestion control' in COMPUTER NETWORKS. Make sure the material has been uploaded and fully processed.",
  "slides": [],
  "mode": "fast"
}
```

---

### `POST /api/search/coverage`

Check whether a topic is in the student's slides. Answers YES / NO / PARTIALLY with slide locations.

**Query params**
| Param | Type | Default | Notes |
|---|---|---|---|
| `force` | bool | `false` | Bypass cache |

**Request body**
```json
{
  "topic": "Selective Repeat ARQ",
  "subject": "COMPUTER NETWORKS"
}
```

**Response** `200`
```json
{
  "covered": true,
  "confidence": "high",
  "answer": "YES — Selective Repeat ARQ is well covered in your slides.\n\n- **Page 41 of unit1_datalink.pptx** — Protocol definition and working\n- **Page 42** — Window size and buffer diagram\n- **Page 43** — Numerical example with efficiency calculation",
  "slides": [
    {
      "slide_id": 115,
      "page_number": 41,
      "filename": "unit1_datalink.pptx",
      "chapter": "ARQ Protocols",
      "rrf_score": 0.0421
    }
  ],
  "model_used": "llama-3.3-70b-versatile"
}
```

**`covered`:** `true` / `false`

**`confidence`:** `"high"` | `"medium"` | `"low"` | `"none"`

Map confidence to a visual indicator:
- `high` → ✅ green badge "Covered"
- `medium` → 🟡 yellow badge "Partially Covered"
- `low` → 🟠 orange badge "Weakly Covered"
- `none` → ❌ red badge "Not Found"

---

### `GET /api/search/slides/{subject}`

Browse and filter slides across a subject by type, chapter, keyword, importance, etc.

**Path param** — `subject`: uppercase subject name

**Query params**
| Param | Type | Notes |
|---|---|---|
| `search` | string | Keyword search across summary, concepts, chapter |
| `type` | string | Exact slide type (see [Slide Type Taxonomy](#15-slide-type-taxonomy)) |
| `chapter` | string | Partial match on chapter name |
| `doc_id` | int | Filter slides from one specific document |
| `min_importance` | float | Min importance score (0.0–1.0), default `0.0` |
| `limit` | int | Max results, default `50`, max `200` |

**Response** `200`
```json
{
  "subject": "COMPUTER NETWORKS",
  "total": 24,
  "slides": [
    {
      "slide_id": 201,
      "doc_id": 1,
      "page_number": 32,
      "filename": "tcp_slides.pdf",
      "slide_type": "numerical_example",
      "chapter": "TCP Congestion Control",
      "concepts": "RTT, throughput, AIMD",
      "summary": "Calculate throughput given RTT = 20ms and packet loss = 2%",
      "exam_signal": true,
      "importance_score": 0.73,
      "pyq_hit_count": 5
    }
  ]
}
```

---

### `GET /api/search/concepts/{subject}`

Browse all concepts extracted from a subject with frequency and slide locations.

**Query params**
| Param | Type | Notes |
|---|---|---|
| `q` | string | Filter concepts by keyword |
| `doc_id` | int | Filter to concepts from one document |

**Response** `200`
```json
{
  "subject": "COMPUTER NETWORKS",
  "total": 84,
  "concepts": [
    {
      "concept": "tcp",
      "frequency": 22,
      "slides": [
        { "slide_id": 201, "doc_id": 2, "page_number": 32, "filename": "tcp_slides.pdf" }
      ]
    }
  ]
}
```

---

## 9. API Reference — Exam Intelligence

### `GET /api/exam/priorities/{subject}`

Priority tier dashboard — all embedded slides bucketed into High / Medium / Low.

**Response** `200`
```json
{
  "subject": "COMPUTER NETWORKS",
  "high": [
    {
      "slide_id": 201,
      "page_number": 32,
      "filename": "tcp_slides.pdf",
      "chapter": "TCP Congestion Control",
      "slide_type": "concept",
      "concepts": "AIMD, slow start, ssthresh",
      "summary": "Congestion window growth phases explained.",
      "importance_score": 0.73,
      "pyq_hit_count": 5,
      "exam_signal": true
    }
  ],
  "medium": [...],
  "low": [...],
  "stats": {
    "high_count": 28,
    "medium_count": 61,
    "low_count": 98,
    "total": 187
  }
}
```

---

### `POST /api/exam/study-plan`

Generate an AI-written, priority-ranked study plan.

**Query params**: `force` bool (bypass cache)

**Request body**
```json
{
  "subject": "COMPUTER NETWORKS",
  "mode": "fast"
}
```

**Response** `200`
```json
{
  "plan": "# Study Plan — COMPUTER NETWORKS\n\n## HIGH PRIORITY (28 slides)\n\n### TCP Congestion Control\nFocus on Pages 32–35 of tcp_slides.pdf...\n\n...",
  "stats": {
    "high_priority": 28,
    "medium_priority": 61,
    "low_priority": 98,
    "total_slides": 187,
    "pyq_questions": 45
  },
  "mode": "fast",
  "model_used": "llama-3.3-70b-versatile"
}
```

> **Render `plan` as Markdown.** It contains headings, bullet points, and slide references.

---

### `POST /api/exam/revision`

Generate a time-constrained revision schedule.

**Query params**: `force` bool

**Request body**
```json
{
  "subject": "COMPUTER NETWORKS",
  "hours": 3.0,
  "mode": "fast"
}
```

**`hours`** — float, must be `> 0` and `<= 24`.

**Response** `200`
```json
{
  "schedule": "# 3-Hour Revision Plan — COMPUTER NETWORKS\n\n## Total: 180 minutes\n\n1. **TCP Congestion Control** — 25 min\n   Pages 32-35 of tcp_slides.pdf\n   Key: AIMD, slow start, ssthresh\n\n2. **Flow Control** — 20 min\n   Pages 1-10 of unit1_datalink.pptx\n   ...",
  "stats": {
    "total_minutes": 180,
    "high_priority": 28,
    "numerical_slides": 12,
    "total_slides": 187
  },
  "mode": "fast",
  "model_used": "llama-3.3-70b-versatile"
}
```

> **Render `schedule` as Markdown.**

---

### `GET /api/exam/pyq-report/{subject}`

PYQ coverage report — which past-year questions map to which slides.

**Response** `200`
```json
{
  "subject": "COMPUTER NETWORKS",
  "total_questions": 45,
  "questions": [
    {
      "question_id": 3,
      "question_text": "Explain TCP Slow Start algorithm.",
      "source_file": "exam2024.pdf",
      "matched_slides": [
        {
          "slide_id": 201,
          "page_number": 32,
          "filename": "tcp_slides.pdf",
          "chapter": "TCP Congestion Control",
          "concepts": "slow start, ssthresh",
          "summary": "Congestion window grows exponentially in Slow Start.",
          "similarity_score": 0.9141
        }
      ]
    }
  ]
}
```

---

### `GET /api/exam/weak-spots/{subject}`

Chapters/topics with high PYQ frequency but potentially low slide coverage — the most critical gaps.

**Response** `200`
```json
{
  "subject": "COMPUTER NETWORKS",
  "total": 4,
  "weak_spots": [
    {
      "chapter": "TCP Congestion Control",
      "priority": "high",
      "pyq_hits": 12,
      "slide_count": 4,
      "avg_importance": 0.68
    }
  ]
}
```

---

### `GET /api/exam/readiness/{subject}`

Composite exam readiness score with verdict and actionable recommendations.

**Response** `200`
```json
{
  "subject": "COMPUTER NETWORKS",
  "readiness_score": 0.72,
  "verdict": "Well Prepared",
  "breakdown": {
    "material_coverage": 0.97,
    "pyq_alignment": 1.0,
    "high_priority_ratio": 0.15,
    "weak_spot_penalty": 0.2
  },
  "stats": {
    "total_slides": 187,
    "embedded_slides": 183,
    "pyq_questions": 45,
    "documents": 3
  },
  "recommendations": [
    "Focus on 28 high-priority slides first",
    "Address 2 critical weak spots with high PYQ frequency"
  ]
}
```

**Verdict thresholds:**
| Score | Verdict | Colour |
|---|---|---|
| `>= 0.7` | Well Prepared | 🟢 green |
| `>= 0.4` | Needs More Work | 🟡 yellow |
| `< 0.4` | Not Ready | 🔴 red |

---

## 10. API Reference — Health

### `GET /api/health`

Simple liveness check.

**Response** `200`
```json
{ "status": "ok" }
```

---

## 11. Shared Object Shapes

### `SlideCard` (returned by multiple endpoints)
```typescript
{
  slide_id: number;
  doc_id?: number;
  page_number: number;
  filename: string;
  slide_type: SlideType;
  chapter: string;
  concepts: string;          // comma-separated — split to render as chips
  summary: string;
  exam_signal: boolean;
  importance_score: number;  // 0.0 – 1.0
  pyq_hit_count: number;
  is_embedded?: boolean;
  rrf_score?: number;        // search relevance — only in search results
}
```

### `JobDetail`
```typescript
{
  id: number;
  filename: string;
  filepath: string;
  job_type: "study_material" | "pyq";
  status: "pending" | "processing" | "completed" | "failed";
  subject: string;
  current_phase: string | null;
  celery_chain_id: string | null;
  created_at: string;        // IST string
  updated_at: string;        // IST string
  error: string | null;
  overall_progress_pct: number;
  total_duration_sec: number | null;
  total_duration: string | null;
  phases: PhaseDetail[];
}
```

### `PhaseDetail`
```typescript
{
  phase: string;             // "ingest" | "structure" | "index" | "ingest_pyq" | "extract" | "map"
  status: "pending" | "running" | "completed" | "skipped" | "failed";
  celery_task_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_sec: number | null;
  duration: string | null;   // human-readable e.g. "7.0s"
  error: string | null;
  progress_pct: number;      // 0 – 100
  progress_detail: string | null;
}
```

---

## 12. Error Handling

All errors follow standard HTTP status codes with a JSON body:

```json
{ "detail": "Subject 'XYZ' not found. Create it first via POST /api/subjects" }
```

Common status codes:

| Code | Meaning | Common cause |
|---|---|---|
| `400` | Bad Request | Wrong file type, empty field |
| `404` | Not Found | Subject/document/job doesn't exist |
| `409` | Conflict | Duplicate subject, PYQ before study material |
| `500` | Server Error | Job creation failed, backend crash |
| `422` | Validation Error | Request body schema mismatch (FastAPI auto-generated) |

**Frontend pattern:**
```javascript
const res = await fetch(url, options);
if (!res.ok) {
  const err = await res.json();
  showToast(err.detail || "Something went wrong");
  return;
}
const data = await res.json();
```

---

## 13. Application Flow & Page Architecture

The intended user journey maps directly to these pages/views:

### Page 1 — Subject Dashboard (Home)
- **API**: `GET /api/subjects`
- Shows all subjects as cards with stats (documents, slides, has_pyq badge, readiness score)
- "New Subject" button → POST `/api/subjects`
- Click a subject → go to Subject Detail page

### Page 2 — Subject Detail
- **APIs**: `GET /api/subjects/{name}`, `GET /api/exam/readiness/{name}`
- Shows readiness score ring/gauge, document list, upload buttons
- "Upload Study Material" button → `POST /api/upload/study-material` → open SSE job tracker
- "Upload PYQ" button → `POST /api/upload/pyq` → open SSE job tracker
- Tabs: Documents | Exam Intelligence | Search

### Page 3 — Job Tracker (inline or modal)
- **APIs**: `GET /api/jobs/{id}` + SSE `GET /api/jobs/{id}/stream`
- Shows phase pipeline visually:
  - Study material: `[ingest] → [structure] → [index]`
  - PYQ: `[ingest_pyq] → [extract] → [map]`
- Each phase shows: status icon, duration, progress bar (`progress_pct`)
- Render `progress_detail` as a small subtitle under the active phase

### Page 4 — Documents View
- **APIs**: `GET /api/documents/{subject}`
- Card per document — shows avg_importance, pyq_hits, high_priority_slides, chapters
- Click a document → Document Detail

### Page 5 — Document Detail
- **APIs**: `GET /api/documents/{subject}/{doc_id}`, `/concepts`, `/pyq`, `/priorities`
- Four tabs:
  1. **Slides** — full slide list with type badges, importance bar, exam_signal flag
  2. **Concepts** — concept cloud/list with frequency chips
  3. **PYQ Matches** — list of matched exam questions and their slides
  4. **Priorities** — High / Medium / Low columns with chapter ranking table

### Page 6 — Search
- **APIs**: `POST /api/search/query`, `GET /api/search/slides/{subject}`, `GET /api/search/concepts/{subject}`
- Search bar at top (subject selector + query input + fast/reasoning toggle)
- On submit: POST `/api/search/query` → render `answer` as Markdown + slide reference cards
- Side panel: filter slides by type/chapter/importance
- "Is this topic in my slides?" sub-feature → `POST /api/search/coverage`

### Page 7 — Coverage Checker
- **API**: `POST /api/search/coverage`
- Single input: topic text + subject selector
- Big verdict badge (Covered / Partially / Not Found) with confidence level
- Slide references below

### Page 8 — Exam Intelligence Hub
- **APIs**: All `/api/exam/...` routes
- Four sub-sections:
  1. **Priority Dashboard** — three-column kanban (High / Medium / Low)
  2. **Study Plan** — generate button → render Markdown output
  3. **Revision Mode** — hours input → "Generate Schedule" → render Markdown
  4. **Weak Spots** — table of chapters needing attention
  5. **PYQ Report** — question list with matched slide accordions

### Page 9 — Jobs Overview
- **API**: `GET /api/jobs/overview`
- Table of all jobs with status badges, durations, progress bars

---

## 14. Priority Colour System

Use these colours consistently throughout the UI:

| Priority | Score Range | Badge Colour | Hex |
|---|---|---|---|
| **High** | `>= 0.4` | Red | `#EF4444` |
| **Medium** | `0.15 – 0.39` | Amber | `#F59E0B` |
| **Low** | `< 0.15` | Green | `#10B981` |

For the `exam_signal` flag (boolean): show a small `⚡ Exam Signal` badge in yellow when `true`.

For `pyq_hit_count > 0`: add a `🎯 PYQ` chip showing the count.

---

## 15. Slide Type Taxonomy

These are the exact values the backend uses. Use them for filter dropdowns and type badges.

| Value | Display Label | Badge Colour |
|---|---|---|
| `definition` | Definition | Blue |
| `concept` | Concept | Indigo |
| `numerical_example` | Numerical | Orange |
| `formula` | Formula | Purple |
| `comparison` | Comparison | Teal |
| `syntax/code` | Code | Gray |
| `diagram_explanation` | Diagram | Sky |
| `summary` | Summary | Green |
| `example` | Example | Yellow |
| `table` | Table | Pink |
| `other` | Other | Muted Gray |

---

## Appendix — API Cheat Sheet

```
GET    /api/health

# Subjects
GET    /api/subjects
POST   /api/subjects                        body: { name }
GET    /api/subjects/{name}

# Upload
POST   /api/upload/study-material           form: file, subject
POST   /api/upload/pyq                      form: file, subject

# Jobs
GET    /api/jobs
GET    /api/jobs/active
GET    /api/jobs/overview
GET    /api/jobs/{job_id}
GET    /api/jobs/{job_id}/stream            SSE

# Documents
GET    /api/documents/{subject}
GET    /api/documents/{subject}/{doc_id}
GET    /api/documents/{subject}/{doc_id}/concepts       ?q=
GET    /api/documents/{subject}/{doc_id}/pyq
GET    /api/documents/{subject}/{doc_id}/priorities
GET    /api/documents/{subject}/{doc_id}/summary

# Search
GET    /api/search/
POST   /api/search/query                    body: { query, subject, mode }  ?force=
POST   /api/search/coverage                 body: { topic, subject }        ?force=
GET    /api/search/slides/{subject}         ?search= &type= &chapter= &doc_id= &min_importance= &limit=
GET    /api/search/concepts/{subject}       ?q= &doc_id=

# Exam Intelligence
GET    /api/exam/
GET    /api/exam/priorities/{subject}
POST   /api/exam/study-plan                 body: { subject, mode }         ?force=
POST   /api/exam/revision                   body: { subject, hours, mode }  ?force=
GET    /api/exam/pyq-report/{subject}
GET    /api/exam/weak-spots/{subject}
GET    /api/exam/readiness/{subject}
```
