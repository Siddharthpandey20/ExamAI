"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { SubjectDetail, ReadinessResult } from "@/lib/types"
import { FileText, BookOpen, HelpCircle, Target, TrendingUp, AlertTriangle, CheckCircle, Sparkles } from "lucide-react"

interface OverviewTabProps {
  subject: SubjectDetail
  readiness: ReadinessResult | null
}

export function OverviewTab({ subject, readiness }: OverviewTabProps) {
  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={<FileText className="h-5 w-5" />}
          label="Documents"
          value={subject.documents}
          description="Uploaded materials"
          color="blue"
        />
        <StatCard
          icon={<BookOpen className="h-5 w-5" />}
          label="Total Slides"
          value={subject.slides}
          description="Processed pages"
          color="indigo"
        />
        <StatCard
          icon={<Target className="h-5 w-5" />}
          label="PYQ Papers"
          value={subject.pyq_papers}
          description="Question papers"
          color="amber"
        />
        <StatCard
          icon={<HelpCircle className="h-5 w-5" />}
          label="PYQ Questions"
          value={subject.pyq_questions}
          description="Mapped to slides"
          color="emerald"
        />
      </div>

      {/* Readiness Details */}
      {readiness && (
        <Card className="overflow-hidden">
          <div className="border-b bg-gradient-to-r from-primary/10 to-transparent px-6 py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-lg shadow-primary/25">
                <TrendingUp className="h-5 w-5" />
              </div>
              <div>
                <CardTitle>Exam Readiness Analysis</CardTitle>
                <CardDescription>
                  Based on your materials and PYQ coverage
                </CardDescription>
              </div>
            </div>
          </div>
          <CardContent className="pt-6 space-y-6">
            {/* Score Breakdown */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <BreakdownItem
                label="Material Coverage"
                value={readiness.breakdown.material_coverage}
                icon={<BookOpen className="h-4 w-4" />}
              />
              <BreakdownItem
                label="PYQ Alignment"
                value={readiness.breakdown.pyq_alignment}
                icon={<Target className="h-4 w-4" />}
              />
              <BreakdownItem
                label="High Priority Ratio"
                value={readiness.breakdown.high_priority_ratio}
                icon={<Sparkles className="h-4 w-4" />}
              />
              <BreakdownItem
                label="Weak Spot Penalty"
                value={readiness.breakdown.weak_spot_penalty}
                icon={<AlertTriangle className="h-4 w-4" />}
                inverted
              />
            </div>

            {/* Recommendations */}
            {readiness.recommendations.length > 0 && (
              <div className="rounded-xl border bg-amber-500/5 border-amber-200 p-5">
                <h4 className="flex items-center gap-2 text-sm font-semibold text-foreground mb-4">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  Recommendations to Improve
                </h4>
                <ul className="space-y-3">
                  {readiness.recommendations.map((rec, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-3 text-sm text-muted-foreground"
                    >
                      <span className="mt-1.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-500/10 text-amber-600 text-xs font-medium">
                        {i + 1}
                      </span>
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Recent Documents */}
      {subject.document_list.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Recent Documents</CardTitle>
                <CardDescription>
                  Your uploaded study materials
                </CardDescription>
              </div>
              <Badge variant="secondary">{subject.document_list.length} total</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {subject.document_list.slice(0, 5).map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between rounded-xl border bg-gradient-to-r from-muted/50 to-muted/20 p-4 transition-all hover:shadow-md"
                >
                  <div className="flex items-center gap-4">
                    <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary shadow-sm">
                      <FileText className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="font-semibold text-foreground">{doc.filename}</p>
                      <p className="text-sm text-muted-foreground">
                        {doc.total_slides} slides
                        {doc.core_topics && (
                          <span className="ml-1 text-muted-foreground/70">
                            - {doc.core_topics.split(",").slice(0, 2).map(t => t.trim()).join(", ")}
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                  <Badge
                    className={
                      doc.status === "processed"
                        ? "bg-emerald-500/10 text-emerald-600 border-emerald-200"
                        : "bg-amber-500/10 text-amber-600 border-amber-200"
                    }
                  >
                    {doc.status === "processed" ? (
                      <>
                        <CheckCircle className="mr-1 h-3 w-3" />
                        Ready
                      </>
                    ) : (
                      "Processing"
                    )}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function StatCard({
  icon,
  label,
  value,
  description,
  color,
}: {
  icon: React.ReactNode
  label: string
  value: number
  description: string
  color: "blue" | "indigo" | "amber" | "emerald"
}) {
  const colorStyles = {
    blue: { bg: "bg-blue-500", light: "from-blue-500/10 to-blue-500/5", text: "text-blue-600" },
    indigo: { bg: "bg-indigo-500", light: "from-indigo-500/10 to-indigo-500/5", text: "text-indigo-600" },
    amber: { bg: "bg-amber-500", light: "from-amber-500/10 to-amber-500/5", text: "text-amber-600" },
    emerald: { bg: "bg-emerald-500", light: "from-emerald-500/10 to-emerald-500/5", text: "text-emerald-600" },
  }
  
  const styles = colorStyles[color]

  return (
    <Card className={`overflow-hidden bg-gradient-to-br ${styles.light}`}>
      <CardContent className="pt-5 pb-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-3xl font-bold text-foreground">{value}</p>
            <p className="text-sm font-medium text-foreground">{label}</p>
            <p className="text-xs text-muted-foreground">{description}</p>
          </div>
          <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${styles.bg} text-white shadow-lg`}>
            {icon}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function BreakdownItem({
  label,
  value,
  icon,
  inverted = false,
}: {
  label: string
  value: number
  icon: React.ReactNode
  inverted?: boolean
}) {
  const percentage = Math.round(value * 100)
  const displayValue = inverted ? 100 - percentage : percentage
  
  const getStyles = (v: number) => {
    if (v >= 70) return { bar: "bg-emerald-500", text: "text-emerald-600", light: "bg-emerald-500/10" }
    if (v >= 40) return { bar: "bg-amber-500", text: "text-amber-600", light: "bg-amber-500/10" }
    return { bar: "bg-red-500", text: "text-red-600", light: "bg-red-500/10" }
  }
  
  const styles = getStyles(displayValue)

  return (
    <div className="space-y-2 rounded-lg border bg-muted/30 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`${styles.light} ${styles.text} rounded-lg p-1.5`}>
            {icon}
          </span>
          <span className="text-xs font-medium text-muted-foreground">{label}</span>
        </div>
        <span className={`text-sm font-bold ${styles.text}`}>{displayValue}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full ${styles.bar} transition-all duration-500`}
          style={{ width: `${displayValue}%` }}
        />
      </div>
    </div>
  )
}
