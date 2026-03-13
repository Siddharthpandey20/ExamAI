"use client"

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import type { Slide, SlideType } from "@/lib/types"
import { BookOpen, Zap, Target, FileText } from "lucide-react"

interface SlideViewerProps {
  slide: Slide
  onClose: () => void
}

const SLIDE_TYPE_CONFIG: Record<SlideType, { label: string; className: string }> = {
  definition: { label: "Definition", className: "bg-blue-500/10 text-blue-600 dark:text-blue-400" },
  concept: { label: "Concept", className: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400" },
  numerical_example: { label: "Numerical", className: "bg-orange-500/10 text-orange-600 dark:text-orange-400" },
  formula: { label: "Formula", className: "bg-purple-500/10 text-purple-600 dark:text-purple-400" },
  comparison: { label: "Comparison", className: "bg-teal-500/10 text-teal-600 dark:text-teal-400" },
  "syntax/code": { label: "Code", className: "bg-gray-500/10 text-gray-600 dark:text-gray-400" },
  diagram_explanation: { label: "Diagram", className: "bg-sky-500/10 text-sky-600 dark:text-sky-400" },
  summary: { label: "Summary", className: "bg-green-500/10 text-green-600 dark:text-green-400" },
  example: { label: "Example", className: "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400" },
  table: { label: "Table", className: "bg-pink-500/10 text-pink-600 dark:text-pink-400" },
  other: { label: "Other", className: "bg-gray-500/10 text-gray-500" },
}

export function SlideViewer({ slide, onClose }: SlideViewerProps) {
  const typeConfig = SLIDE_TYPE_CONFIG[slide.slide_type] || SLIDE_TYPE_CONFIG.other
  const safeImportance = (slide.importance_score != null && !isNaN(slide.importance_score)) ? slide.importance_score : 0
  const priorityColor =
    safeImportance >= 0.4
      ? "var(--priority-high)"
      : safeImportance >= 0.15
        ? "var(--priority-medium)"
        : "var(--priority-low)"

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div
              className="flex h-10 w-10 items-center justify-center rounded-lg text-sm font-semibold"
              style={{ backgroundColor: `color-mix(in oklab, ${priorityColor} 15%, transparent)`, color: priorityColor }}
            >
              {slide.page_number}
            </div>
            <div>
              <DialogTitle>Page {slide.page_number}</DialogTitle>
              {slide.filename && (
                <DialogDescription className="flex items-center gap-1">
                  <FileText className="h-3 w-3" />
                  {slide.filename}
                </DialogDescription>
              )}
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-6">
          {/* Badges Row */}
          <div className="flex flex-wrap items-center gap-2">
            <Badge className={typeConfig.className}>{typeConfig.label}</Badge>
            {slide.exam_signal && (
              <Badge className="bg-yellow-500/10 text-yellow-600 dark:text-yellow-400">
                Exam Signal
              </Badge>
            )}
            {slide.pyq_hit_count > 0 && (
              <Badge variant="outline" className="flex items-center gap-1">
                <Target className="h-3 w-3" />
                {slide.pyq_hit_count} PYQ Hits
              </Badge>
            )}
          </div>

          {/* Chapter */}
          {slide.chapter && (
            <div>
              <h4 className="text-sm font-medium text-muted-foreground">Chapter</h4>
              <p className="mt-1 text-foreground">{slide.chapter}</p>
            </div>
          )}

          {/* Summary */}
          {slide.summary && (
            <div>
              <h4 className="text-sm font-medium text-muted-foreground">Summary</h4>
              <p className="mt-1 text-foreground leading-relaxed">{slide.summary}</p>
            </div>
          )}

          {/* Concepts */}
          {slide.concepts && (
            <div>
              <h4 className="text-sm font-medium text-muted-foreground">Concepts</h4>
              <div className="mt-2 flex flex-wrap gap-2">
                {slide.concepts.split(",").map((concept, i) => (
                  <Badge key={i} variant="secondary">
                    {concept.trim()}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Stats */}
          <div className="flex items-center gap-6 rounded-lg bg-muted/50 p-4">
            <div className="flex items-center gap-2">
              <Zap className="h-5 w-5" style={{ color: priorityColor }} />
              <div>
                <p className="text-sm font-medium" style={{ color: priorityColor }}>
                  {safeImportance > 0 ? `${Math.round(safeImportance * 100)}%` : "N/A"}
                </p>
                <p className="text-xs text-muted-foreground">Importance</p>
              </div>
            </div>
            <div className="h-8 w-px bg-border" />
            <div className="flex items-center gap-2">
              <Target className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium text-foreground">{slide.pyq_hit_count}</p>
                <p className="text-xs text-muted-foreground">PYQ Matches</p>
              </div>
            </div>
            <div className="h-8 w-px bg-border" />
            <div className="flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-muted-foreground" />
              <div>
                <p className="text-sm font-medium text-foreground">
                  {slide.is_embedded !== false ? "Yes" : "No"}
                </p>
                <p className="text-xs text-muted-foreground">Indexed</p>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
