// ExamPrep AI - API Client

import type {
  SubjectStats,
  SubjectDetail,
  Document,
  DocumentDetail,
  Concept,
  JobDetail,
  JobOverview,
  SearchResult,
  CoverageResult,
  PriorityData,
  StudyPlan,
  RevisionSchedule,
  WeakSpotsResult,
  PYQReport,
  ReadinessResult,
  UploadResponse,
  Slide,
  PYQFilesResponse,
} from "./types"

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Something went wrong" }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }

  return res.json()
}

// Subject APIs
export async function getSubjects(): Promise<SubjectStats[]> {
  return fetchApi<SubjectStats[]>("/api/subjects")
}

export async function createSubject(name: string): Promise<SubjectStats> {
  return fetchApi<SubjectStats>("/api/subjects", {
    method: "POST",
    body: JSON.stringify({ name: name.toUpperCase() }),
  })
}

export async function getSubjectDetail(name: string): Promise<SubjectDetail> {
  return fetchApi<SubjectDetail>(`/api/subjects/${encodeURIComponent(name.toUpperCase())}`)
}

// Document APIs
export async function getDocuments(
  subject: string
): Promise<{ subject: string; total: number; documents: Document[] }> {
  return fetchApi(`/api/documents/${encodeURIComponent(subject.toUpperCase())}`)
}

export async function getDocument(
  subject: string,
  docId: number
): Promise<DocumentDetail> {
  return fetchApi(`/api/documents/${encodeURIComponent(subject.toUpperCase())}/${docId}`)
}

export async function getDocumentConcepts(
  subject: string,
  docId: number,
  query?: string
): Promise<{ subject: string; doc_id: number; filename: string; total: number; concepts: Concept[] }> {
  const params = query ? `?q=${encodeURIComponent(query)}` : ""
  return fetchApi(`/api/documents/${encodeURIComponent(subject.toUpperCase())}/${docId}/concepts${params}`)
}

export async function getDocumentPriorities(
  subject: string,
  docId: number
): Promise<PriorityData & { doc_id: number; filename: string; chapters_ranked: unknown[] }> {
  return fetchApi(`/api/documents/${encodeURIComponent(subject.toUpperCase())}/${docId}/priorities`)
}

// Search APIs
export async function searchQuery(
  query: string,
  subject: string,
  mode: "fast" | "reasoning" = "fast",
  force = false
): Promise<SearchResult> {
  const params = force ? "?force=true" : ""
  return fetchApi<SearchResult>(`/api/search/query${params}`, {
    method: "POST",
    body: JSON.stringify({ query, subject: subject.toUpperCase(), mode }),
  })
}

export async function checkCoverage(
  topic: string,
  subject: string,
  force = false
): Promise<CoverageResult> {
  const params = force ? "?force=true" : ""
  return fetchApi<CoverageResult>(`/api/search/coverage${params}`, {
    method: "POST",
    body: JSON.stringify({ topic, subject: subject.toUpperCase() }),
  })
}

export async function searchSlides(
  subject: string,
  options?: {
    search?: string
    type?: string
    chapter?: string
    doc_id?: number
    min_importance?: number
    limit?: number
  }
): Promise<{ subject: string; total: number; slides: Slide[] }> {
  const params = new URLSearchParams()
  if (options?.search) params.set("search", options.search)
  if (options?.type) params.set("type", options.type)
  if (options?.chapter) params.set("chapter", options.chapter)
  if (options?.doc_id) params.set("doc_id", String(options.doc_id))
  if (options?.min_importance) params.set("min_importance", String(options.min_importance))
  if (options?.limit) params.set("limit", String(options.limit))
  const queryString = params.toString() ? `?${params.toString()}` : ""
  return fetchApi(`/api/search/slides/${encodeURIComponent(subject.toUpperCase())}${queryString}`)
}

export async function getConcepts(
  subject: string,
  options?: { q?: string; doc_id?: number }
): Promise<{ subject: string; total: number; concepts: Concept[] }> {
  const params = new URLSearchParams()
  if (options?.q) params.set("q", options.q)
  if (options?.doc_id) params.set("doc_id", String(options.doc_id))
  const queryString = params.toString() ? `?${params.toString()}` : ""
  return fetchApi(`/api/search/concepts/${encodeURIComponent(subject.toUpperCase())}${queryString}`)
}

// Exam Intelligence APIs
export async function getPriorities(subject: string): Promise<PriorityData> {
  return fetchApi<PriorityData>(`/api/exam/priorities/${encodeURIComponent(subject.toUpperCase())}`)
}

export async function generateStudyPlan(
  subject: string,
  mode: "fast" | "reasoning" = "fast",
  force = false
): Promise<StudyPlan> {
  const params = force ? "?force=true" : ""
  return fetchApi<StudyPlan>(`/api/exam/study-plan${params}`, {
    method: "POST",
    body: JSON.stringify({ subject: subject.toUpperCase(), mode }),
  })
}

export async function generateRevision(
  subject: string,
  hours: number,
  mode: "fast" | "reasoning" = "fast",
  force = false
): Promise<RevisionSchedule> {
  const params = force ? "?force=true" : ""
  return fetchApi<RevisionSchedule>(`/api/exam/revision${params}`, {
    method: "POST",
    body: JSON.stringify({ subject: subject.toUpperCase(), hours, mode }),
  })
}

export async function getPYQReport(subject: string): Promise<PYQReport> {
  return fetchApi<PYQReport>(`/api/exam/pyq-report/${encodeURIComponent(subject.toUpperCase())}`)
}

export async function getWeakSpots(subject: string): Promise<WeakSpotsResult> {
  return fetchApi<WeakSpotsResult>(`/api/exam/weak-spots/${encodeURIComponent(subject.toUpperCase())}`)
}

export async function getReadiness(subject: string): Promise<ReadinessResult> {
  return fetchApi<ReadinessResult>(`/api/exam/readiness/${encodeURIComponent(subject.toUpperCase())}`)
}

// Upload APIs
export async function uploadStudyMaterial(
  file: File,
  subject: string
): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append("file", file)
  formData.append("subject", subject.toUpperCase())

  const res = await fetch(`${BASE_URL}/api/upload/study-material`, {
    method: "POST",
    body: formData,
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Upload failed" }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }

  return res.json()
}

export async function uploadPYQ(file: File, subject: string): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append("file", file)
  formData.append("subject", subject.toUpperCase())

  const res = await fetch(`${BASE_URL}/api/upload/pyq`, {
    method: "POST",
    body: formData,
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Upload failed" }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }

  return res.json()
}

// Job APIs
export async function getJobs(): Promise<JobDetail[]> {
  return fetchApi<JobDetail[]>("/api/jobs")
}

export async function getActiveJobs(): Promise<JobDetail[]> {
  return fetchApi<JobDetail[]>("/api/jobs/active")
}

export async function getJobsOverview(): Promise<JobOverview[]> {
  return fetchApi<JobOverview[]>("/api/jobs/overview")
}

export async function getJob(jobId: number): Promise<JobDetail> {
  return fetchApi<JobDetail>(`/api/jobs/${jobId}`)
}

// SSE helper for job tracking
export function trackJob(
  jobId: number,
  onUpdate: (data: JobDetail) => void,
  onComplete: (data: JobDetail) => void,
  onError?: (error: Event) => void
): () => void {
  const es = new EventSource(`${BASE_URL}/api/jobs/${jobId}/stream`)

  es.addEventListener("status", (e) => {
    try {
      const data = JSON.parse(e.data)
      onUpdate(data)
    } catch {
      console.error("Failed to parse SSE data")
    }
  })

  es.addEventListener("complete", (e) => {
    try {
      const data = JSON.parse(e.data)
      onComplete(data)
    } catch {
      console.error("Failed to parse SSE data")
    }
    es.close()
  })

  es.addEventListener("error", (e) => {
    if (onError) onError(e)
    es.close()
  })

  return () => es.close()
}

// Utility: Convert uppercase to title case for display
export function toTitleCase(str: string): string {
  return str
    .toLowerCase()
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")
}

// Utility: Get priority level from importance score
export function getPriorityLevel(score: number): "high" | "medium" | "low" {
  if (score >= 0.4) return "high"
  if (score >= 0.15) return "medium"
  return "low"
}

// File serving
export function getFileUrl(subject: string, folder: "uploads" | "pyq_uploads", filename: string): string {
  return `${BASE_URL}/api/upload/file/${encodeURIComponent(subject.toUpperCase())}/${folder}/${encodeURIComponent(filename)}`
}

// PYQ file listing
export async function getPYQFiles(subject: string): Promise<PYQFilesResponse> {
  return fetchApi<PYQFilesResponse>(
    `/api/upload/pyq-files/${encodeURIComponent(subject.toUpperCase())}`
  )
}

// Document PYQ matches
export async function getDocumentPYQ(
  subject: string,
  docId: number
): Promise<{ subject: string; doc_id: number; filename: string; total_questions: number; questions: import("./types").PYQQuestion[] }> {
  return fetchApi(`/api/documents/${encodeURIComponent(subject.toUpperCase())}/${docId}/pyq`)
}

// Document summary
export async function getDocumentSummary(
  subject: string,
  docId: number
): Promise<{ subject: string; doc_id: number; filename: string; summary: string }> {
  return fetchApi(`/api/documents/${encodeURIComponent(subject.toUpperCase())}/${docId}/summary`)
}


// Utility: Get readiness verdict from score
export function getReadinessVerdict(score: number): { verdict: string; level: "success" | "warning" | "danger" } {
  if (score >= 0.7) return { verdict: "Well Prepared", level: "success" }
  if (score >= 0.4) return { verdict: "Needs More Work", level: "warning" }
  return { verdict: "Not Ready", level: "danger" }
}
