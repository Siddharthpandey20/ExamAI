// ExamPrep AI - Type Definitions

export interface SubjectStats {
  name: string
  created_at: string
  documents: number
  slides: number
  pyq_papers: number
  pyq_questions: number
  has_pyq: boolean
}

export interface DocumentListItem {
  id: number
  filename: string
  status: "pending" | "processed"
  total_slides: number
  core_topics: string
  processed_at: string
}

export interface SubjectDetail extends SubjectStats {
  document_list: DocumentListItem[]
}

export interface Document {
  id: number
  filename: string
  status: "pending" | "processed"
  subject: string
  ai_subject: string
  summary: string
  core_topics: string
  total_slides: number
  embedded_slides: number
  total_pyq_hits: number
  avg_importance: number
  high_priority_slides: number
  unique_concepts: number
  top_concepts: string[]
  chapters: Chapter[]
  processed_at: string
}

export interface Chapter {
  name: string
  slide_range: string
  topics: string[]
}

export interface Slide {
  slide_id: number
  doc_id?: number
  page_number: number
  filename?: string
  slide_type: SlideType
  chapter: string
  concepts: string
  summary: string
  exam_signal: boolean
  importance_score: number
  pyq_hit_count: number
  is_embedded?: boolean
  rrf_score?: number
}

export type SlideType =
  | "definition"
  | "concept"
  | "numerical_example"
  | "formula"
  | "comparison"
  | "syntax/code"
  | "diagram_explanation"
  | "summary"
  | "example"
  | "table"
  | "other"

export interface DocumentDetail extends Document {
  slides: Slide[]
}

export interface Concept {
  concept: string
  frequency: number
  slides: ConceptSlide[]
}

export interface ConceptSlide {
  slide_id: number
  doc_id?: number
  page_number: number
  filename?: string
  slide_type?: SlideType
  summary?:string
  importance_score?: number
  pyq_hit_count?: number
}

export interface PhaseDetail {
  phase: string
  status: "pending" | "running" | "completed" | "skipped" | "failed"
  celery_task_id: string | null
  started_at: string | null
  completed_at: string | null
  duration_sec: number | null
  duration: string | null
  error: string | null
  progress_pct: number
  progress_detail: string | null
}

export interface JobDetail {
  id: number
  filename: string
  filepath: string
  job_type: "study_material" | "pyq"
  status: "pending" | "processing" | "completed" | "failed"
  subject: string
  current_phase: string | null
  celery_chain_id: string | null
  created_at: string
  updated_at: string
  error: string | null
  overall_progress_pct: number
  total_duration_sec: number | null
  total_duration: string | null
  phases: PhaseDetail[]
}

export interface JobOverview {
  id: number
  filename: string
  job_type: "study_material" | "pyq"
  status: "pending" | "processing" | "completed" | "failed"
  subject: string
  current_phase: string
  progress: string
  overall_progress_pct: number
  progress_detail: string | null
  total_duration_sec: number | null
  total_duration: string | null
  created_at: string
  error: string | null
}

export interface SearchResult {
  answer: string
  slides: Slide[]
  mode: "fast" | "reasoning"
  model_used?: string
}

export interface CoverageResult {
  covered: boolean
  confidence: "high" | "medium" | "low" | "none"
  answer: string
  slides: Slide[]
  model_used?: string
}

export interface PriorityData {
  subject: string
  high: Slide[]
  medium: Slide[]
  low: Slide[]
  stats: {
    high_count: number
    medium_count: number
    low_count: number
    total: number
  }
}

export interface StudyPlan {
  plan?: string
  answer?: string
  stats?: {
    high_priority?: number
    medium_priority?: number
    low_priority?: number
    total_slides?: number
    pyq_questions?: number
  }
  mode: string
  model_used?: string
}

export interface RevisionSchedule {
  plan?: string
  answer?: string
  time_hours?: number
  time_minutes?: number
  stats?: {
    high_priority?: number
    medium_priority?: number
    low_priority?: number
    numerical_problems?: number
  }
  mode: string
  model_used?: string
}

export interface WeakSpot {
  chapter: string
  priority: "high" | "medium" | "low"
  pyq_hits: number
  slide_count: number
  avg_importance: number
}

export interface WeakSpotsResult {
  subject: string
  total: number
  weak_spots: WeakSpot[]
}

export interface PYQQuestion {
  question_id: number
  question_text: string
  source_file: string
  matched_slides: Array<Slide & { similarity_score?: number }>
}

export interface PYQReport {
  subject: string
  total_questions: number
  questions: PYQQuestion[]
}

export interface ReadinessResult {
  subject: string
  readiness_score: number
  verdict: string
  breakdown: {
    material_coverage: number
    pyq_alignment: number
    high_priority_ratio: number
    weak_spot_penalty: number
  }
  stats: {
    total_slides: number
    embedded_slides: number
    pyq_questions: number
    documents: number
  }
  recommendations: string[]
}

export interface UploadResponse {
  message: string
  job_id: number
  subject: string
  filepath: string
}

export interface PYQFile {
  filename: string
  size_bytes: number
  url: string
  question_count: number
}

export interface PYQFilesResponse {
  subject: string
  total: number
  files: PYQFile[]
}

