"use client"

import { useEffect, useState } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { getSubjectDetail, getReadiness, toTitleCase } from "@/lib/api"
import type { SubjectDetail, ReadinessResult } from "@/lib/types"
import { ArrowLeft, LayoutDashboard, FileText, Search, Brain, BookOpen, Sparkles, FileQuestion } from "lucide-react"
import { toast } from "sonner"
import { OverviewTab } from "@/components/tabs/overview-tab"
import { MaterialsTab } from "@/components/tabs/materials-tab"
import { SearchConceptsTab } from "@/components/tabs/search-concepts-tab"
import { ExamIntelligenceTab } from "@/components/tabs/exam-intelligence-tab"
import { PYQFilesTab } from "@/components/tabs/pyq-files-tab"
interface SubjectWorkspaceProps {
  subjectName: string
  onBack: () => void
}

export function SubjectWorkspace({ subjectName, onBack }: SubjectWorkspaceProps) {
  const [subject, setSubject] = useState<SubjectDetail | null>(null)
  const [readiness, setReadiness] = useState<ReadinessResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState("overview")

  const fetchData = async () => {
    try {
      setLoading(true)
      const [subjectData, readinessData] = await Promise.all([
        getSubjectDetail(subjectName),
        getReadiness(subjectName).catch(() => null),
      ])
      setSubject(subjectData)
      setReadiness(readinessData)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load subject")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [subjectName])

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-10 w-10 rounded-lg" />
          <div className="space-y-2">
            <Skeleton className="h-7 w-56" />
            <Skeleton className="h-4 w-40" />
          </div>
        </div>
        <Skeleton className="h-14 w-full max-w-xl" />
        <Skeleton className="h-[500px] w-full rounded-xl" />
      </div>
    )
  }

  if (!subject) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
          <BookOpen className="h-8 w-8 text-muted-foreground" />
        </div>
        <p className="mt-4 text-lg font-medium text-foreground">Subject not found</p>
        <p className="text-sm text-muted-foreground">This subject may have been deleted</p>
        <Button variant="outline" onClick={onBack} className="mt-4">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Go Back
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={onBack} className="shrink-0 hover:bg-muted">
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-lg shadow-primary/25">
              <BookOpen className="h-6 w-6" />
            </div>
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-foreground">
                {toTitleCase(subject.name)}
              </h2>
              <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <span className="flex items-center gap-1">
                  <FileText className="h-3.5 w-3.5" />
                  {subject.documents} documents
                </span>
                <span className="text-muted-foreground/50">|</span>
                <span>{subject.slides} slides</span>
                {subject.has_pyq && (
                  <>
                    <span className="text-muted-foreground/50">|</span>
                    <Badge className="bg-amber-500/10 text-amber-600 border-amber-200">
                      <Sparkles className="mr-1 h-3 w-3" />
                      {subject.pyq_questions} PYQ
                    </Badge>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 pl-14 lg:pl-0">
          {readiness && (
            <ReadinessIndicator score={readiness.readiness_score} verdict={readiness.verdict} />
          )}
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
        <TabsList className="h-12 p-1.5 grid w-full max-w-xl grid-cols-5">
          <TabsTrigger value="overview" className="gap-2 data-[state=active]:shadow-sm">
            <LayoutDashboard className="h-4 w-4" />
            <span className="hidden sm:inline">Overview</span>
          </TabsTrigger>
          <TabsTrigger value="materials" className="gap-2 data-[state=active]:shadow-sm">
            <FileText className="h-4 w-4" />
            <span className="hidden sm:inline">Materials</span>
          </TabsTrigger>
          <TabsTrigger value="pyq-files" className="gap-2 data-[state=active]:shadow-sm">
            <FileQuestion className="h-4 w-4" />
            <span className="hidden sm:inline">PYQ Files</span>
          </TabsTrigger>
          <TabsTrigger value="search" className="gap-2 data-[state=active]:shadow-sm">
            <Search className="h-4 w-4" />
            <span className="hidden sm:inline">Search</span>
          </TabsTrigger>
          <TabsTrigger value="exam" className="gap-2 data-[state=active]:shadow-sm">
            <Brain className="h-4 w-4" />
            <span className="hidden sm:inline">Exam Intel</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <OverviewTab subject={subject} readiness={readiness} />
        </TabsContent>

        <TabsContent value="materials">
          <MaterialsTab subjectName={subject.name} />
        </TabsContent>

        <TabsContent value="pyq-files">
          <PYQFilesTab subjectName={subject.name} />
        </TabsContent>

        <TabsContent value="search">
          <SearchConceptsTab subjectName={subject.name} />
        </TabsContent>

        <TabsContent value="exam">
          <ExamIntelligenceTab subjectName={subject.name} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

function ReadinessIndicator({ score, verdict }: { score: number; verdict: string }) {
  const percentage = Math.round(score * 100)
  
  const getStyles = (s: number) => {
    if (s >= 0.7) return { text: "text-emerald-600", bg: "bg-emerald-500", light: "bg-emerald-500/10", border: "border-emerald-200" }
    if (s >= 0.4) return { text: "text-amber-600", bg: "bg-amber-500", light: "bg-amber-500/10", border: "border-amber-200" }
    return { text: "text-red-600", bg: "bg-red-500", light: "bg-red-500/10", border: "border-red-200" }
  }
  
  const styles = getStyles(score)

  return (
    <div className={`flex items-center gap-3 rounded-xl border ${styles.border} ${styles.light} px-4 py-2.5`}>
      <div className="relative h-12 w-12">
        <svg className="h-12 w-12 -rotate-90" viewBox="0 0 36 36">
          <path
            className="stroke-muted"
            fill="none"
            strokeWidth="3"
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          />
          <path
            className={styles.text}
            fill="none"
            strokeWidth="3"
            strokeLinecap="round"
            strokeDasharray={`${percentage}, 100`}
            stroke="currentColor"
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
          />
        </svg>
        <span className={`absolute inset-0 flex items-center justify-center text-xs font-bold ${styles.text}`}>
          {percentage}%
        </span>
      </div>
      <div>
        <p className="text-sm font-semibold text-foreground">Exam Readiness</p>
        <p className={`text-sm font-medium ${styles.text}`}>{verdict}</p>
      </div>
    </div>
  )
}
