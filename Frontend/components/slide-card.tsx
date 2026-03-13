"use client"

import { Badge } from "@/components/ui/badge"
import type { Slide, SlideType } from "@/lib/types"
import { Zap, Target, BookOpen, Sparkles } from "lucide-react"

interface SlideCardProps {
  slide: Slide
  onClick?: () => void
  compact?: boolean
  showSimilarity?: number
}

const SLIDE_TYPE_CONFIG: Record<SlideType, { label: string; className: string; dotColor: string }> = {
  definition: { label: "Definition", className: "bg-blue-500/10 text-blue-600 border-blue-200", dotColor: "bg-blue-500" },
  concept: { label: "Concept", className: "bg-indigo-500/10 text-indigo-600 border-indigo-200", dotColor: "bg-indigo-500" },
  numerical_example: { label: "Numerical", className: "bg-orange-500/10 text-orange-600 border-orange-200", dotColor: "bg-orange-500" },
  formula: { label: "Formula", className: "bg-purple-500/10 text-purple-600 border-purple-200", dotColor: "bg-purple-500" },
  comparison: { label: "Comparison", className: "bg-teal-500/10 text-teal-600 border-teal-200", dotColor: "bg-teal-500" },
  "syntax/code": { label: "Code", className: "bg-slate-500/10 text-slate-600 border-slate-200", dotColor: "bg-slate-500" },
  diagram_explanation: { label: "Diagram", className: "bg-sky-500/10 text-sky-600 border-sky-200", dotColor: "bg-sky-500" },
  summary: { label: "Summary", className: "bg-emerald-500/10 text-emerald-600 border-emerald-200", dotColor: "bg-emerald-500" },
  example: { label: "Example", className: "bg-amber-500/10 text-amber-600 border-amber-200", dotColor: "bg-amber-500" },
  table: { label: "Table", className: "bg-pink-500/10 text-pink-600 border-pink-200", dotColor: "bg-pink-500" },
  other: { label: "Other", className: "bg-gray-500/10 text-gray-500 border-gray-200", dotColor: "bg-gray-500" },
}

export function SlideCard({ slide, onClick, compact = false, showSimilarity }: SlideCardProps) {
  const typeConfig = SLIDE_TYPE_CONFIG[slide.slide_type] || SLIDE_TYPE_CONFIG.other
  
  const getPriorityStyles = (score: number) => {
    if (score >= 0.4) return { bg: "bg-red-500", text: "text-red-600", light: "bg-red-500/10" }
    if (score >= 0.15) return { bg: "bg-amber-500", text: "text-amber-600", light: "bg-amber-500/10" }
    return { bg: "bg-emerald-500", text: "text-emerald-600", light: "bg-emerald-500/10" }
  }
  
  const safeImportance = (slide.importance_score != null && !isNaN(slide.importance_score)) ? slide.importance_score : 0
  const priorityStyles = getPriorityStyles(safeImportance)

  if (compact) {
    return (
      <div
        onClick={onClick}
        className="group cursor-pointer rounded-xl border bg-gradient-to-br from-card to-muted/20 p-3 transition-all duration-200 hover:border-primary/50 hover:shadow-md hover:-translate-y-0.5"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className={`flex h-7 w-7 items-center justify-center rounded-lg ${priorityStyles.light} ${priorityStyles.text} text-xs font-bold`}>
              {slide.page_number}
            </div>
            <div>
              <span className="text-sm font-medium">Page {slide.page_number}</span>
              {slide.filename && (
                <p className="text-xs text-muted-foreground line-clamp-1 max-w-[120px]">{slide.filename}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            {slide.pyq_hit_count > 0 && (
              <Badge className="bg-amber-500/10 text-amber-600 border-amber-200 text-xs">
                <Target className="mr-1 h-3 w-3" />
                {slide.pyq_hit_count}
              </Badge>
            )}
          </div>
        </div>
        {slide.chapter && (
          <p className="mt-1.5 text-xs text-muted-foreground line-clamp-1">{slide.chapter}</p>
        )}
      </div>
    )
  }

  return (
    <div
      onClick={onClick}
      className="group cursor-pointer overflow-hidden rounded-xl border bg-gradient-to-br from-card to-muted/20 transition-all duration-200 hover:border-primary/50 hover:shadow-lg hover:-translate-y-0.5"
    >
      {/* Priority indicator bar */}
      <div className={`h-1 w-full ${priorityStyles.bg}`} />
      
      <div className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-3">
            <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${priorityStyles.light} ${priorityStyles.text} font-bold shadow-sm`}>
              {slide.page_number}
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">Page {slide.page_number}</p>
              {slide.filename && (
                <p className="text-xs text-muted-foreground line-clamp-1 max-w-[150px]">{slide.filename}</p>
              )}
            </div>
          </div>
          <Badge className={`${typeConfig.className} border`}>{typeConfig.label}</Badge>
        </div>

        {/* Chapter */}
        {slide.chapter && (
          <p className="mt-3 text-sm font-medium text-foreground line-clamp-1">{slide.chapter}</p>
        )}

        {/* Summary */}
        {slide.summary && (
          <p className="mt-2 text-sm text-muted-foreground line-clamp-2 leading-relaxed">{slide.summary}</p>
        )}

        {/* Concepts */}
        {slide.concepts && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {slide.concepts
              .split(",")
              .slice(0, 3)
              .map((concept, i) => (
                <Badge key={i} variant="secondary" className="text-xs font-normal">
                  {concept.trim()}
                </Badge>
              ))}
            {slide.concepts.split(",").length > 3 && (
              <Badge variant="secondary" className="text-xs font-normal">
                +{slide.concepts.split(",").length - 3}
              </Badge>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="mt-4 flex items-center justify-between border-t pt-3">
          <div className="flex items-center gap-3 text-xs">
            {slide.importance_score != null && !isNaN(slide.importance_score) && (
              <span className={`flex items-center gap-1 font-medium ${priorityStyles.text}`}>
                <Zap className="h-3.5 w-3.5" />
                {Math.round(slide.importance_score * 100)}%
              </span>
            )}
            {slide.pyq_hit_count > 0 && (
              <span className="flex items-center gap-1 text-amber-600">
                <Target className="h-3.5 w-3.5" />
                {slide.pyq_hit_count} PYQ
              </span>
            )}
          </div>
          {slide.exam_signal && (
            <Badge className="bg-amber-500/10 text-amber-600 border-amber-200">
              <Sparkles className="mr-1 h-3 w-3" />
              Exam Signal
            </Badge>
          )}
        </div>

        {/* Similarity Score */}
        {showSimilarity !== undefined && (
          <div className="mt-3 flex items-center gap-2">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full bg-gradient-to-r from-primary to-primary/70 transition-all duration-500"
                style={{ width: `${Math.round(showSimilarity * 100)}%` }}
              />
            </div>
            <span className="text-xs font-medium text-primary">
              {Math.round(showSimilarity * 100)}%
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
