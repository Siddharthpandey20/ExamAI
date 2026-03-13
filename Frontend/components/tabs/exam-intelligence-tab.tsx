"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import { AISettings, type AIMode } from "@/components/ai-settings"
import { MarkdownRenderer } from "@/components/markdown-renderer"
import {
  getPriorities,
  generateStudyPlan,
  generateRevision,
  getWeakSpots,
  getPYQReport,
} from "@/lib/api"
import type { PriorityData, StudyPlan, RevisionSchedule, WeakSpotsResult, PYQReport, Slide } from "@/lib/types"
import { LayoutGrid, BookOpen, Clock, AlertTriangle, FileQuestion, Target, Zap, TrendingUp, ChevronDown, Copy, Check } from "lucide-react"
import { toast } from "sonner"
import { SlideCard } from "@/components/slide-card"
import { SlideViewer } from "@/components/slide-viewer"

interface ExamIntelligenceTabProps {
  subjectName: string
}

export function ExamIntelligenceTab({ subjectName }: ExamIntelligenceTabProps) {
  return (
    <Tabs defaultValue="priorities" className="space-y-6">
      <TabsList className="h-12 p-1.5 grid w-full max-w-3xl grid-cols-5">
        <TabsTrigger value="priorities" className="gap-2">
          <LayoutGrid className="h-4 w-4" />
          <span className="hidden sm:inline">Priority</span>
        </TabsTrigger>
        <TabsTrigger value="study-plan" className="gap-2">
          <BookOpen className="h-4 w-4" />
          <span className="hidden sm:inline">Study Plan</span>
        </TabsTrigger>
        <TabsTrigger value="revision" className="gap-2">
          <Clock className="h-4 w-4" />
          <span className="hidden sm:inline">Revision</span>
        </TabsTrigger>
        <TabsTrigger value="weak-spots" className="gap-2">
          <AlertTriangle className="h-4 w-4" />
          <span className="hidden sm:inline">Weak Spots</span>
        </TabsTrigger>
        <TabsTrigger value="pyq-report" className="gap-2">
          <FileQuestion className="h-4 w-4" />
          <span className="hidden sm:inline">PYQ</span>
        </TabsTrigger>
      </TabsList>

      <TabsContent value="priorities">
        <PrioritiesPanel subjectName={subjectName} />
      </TabsContent>

      <TabsContent value="study-plan">
        <StudyPlanPanel subjectName={subjectName} />
      </TabsContent>

      <TabsContent value="revision">
        <RevisionPanel subjectName={subjectName} />
      </TabsContent>

      <TabsContent value="weak-spots">
        <WeakSpotsPanel subjectName={subjectName} />
      </TabsContent>

      <TabsContent value="pyq-report">
        <PYQReportPanel subjectName={subjectName} />
      </TabsContent>
    </Tabs>
  )
}

function PrioritiesPanel({ subjectName }: { subjectName: string }) {
  const [data, setData] = useState<PriorityData | null>(null)
  const [loading, setLoading] = useState(true)
  const [viewingSlide, setViewingSlide] = useState<Slide | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const result = await getPriorities(subjectName)
        setData(result)
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to load priorities")
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [subjectName])

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-96 rounded-xl" />
          ))}
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
            <LayoutGrid className="h-8 w-8 text-muted-foreground" />
          </div>
          <p className="mt-4 text-lg font-medium text-foreground">No priority data available</p>
          <p className="text-sm text-muted-foreground">Upload study materials to see priorities</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="High Priority"
          value={data.stats.high_count}
          total={data.stats.total}
          color="red"
          icon={<Zap className="h-5 w-5" />}
        />
        <StatCard
          label="Medium Priority"
          value={data.stats.medium_count}
          total={data.stats.total}
          color="amber"
          icon={<TrendingUp className="h-5 w-5" />}
        />
        <StatCard
          label="Low Priority"
          value={data.stats.low_count}
          total={data.stats.total}
          color="emerald"
          icon={<Target className="h-5 w-5" />}
        />
      </div>

      {/* Priority Columns */}
      <div className="grid gap-4 lg:grid-cols-3">
        <PriorityColumn
          title="High Priority"
          description="Focus on these first"
          slides={data.high}
          color="red"
          onViewSlide={setViewingSlide}
        />
        <PriorityColumn
          title="Medium Priority"
          description="Review after high priority"
          slides={data.medium}
          color="amber"
          onViewSlide={setViewingSlide}
        />
        <PriorityColumn
          title="Low Priority"
          description="Optional but helpful"
          slides={data.low}
          color="emerald"
          onViewSlide={setViewingSlide}
        />
      </div>

      {viewingSlide && (
        <SlideViewer slide={viewingSlide} onClose={() => setViewingSlide(null)} />
      )}
    </div>
  )
}

function PriorityColumn({
  title,
  description,
  slides,
  color,
  onViewSlide,
}: {
  title: string
  description: string
  slides: Slide[]
  color: "red" | "amber" | "emerald"
  onViewSlide: (slide: Slide) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const INITIAL_SHOW = 20

  const colorStyles = {
    red: {
      header: "from-red-500/20 to-red-500/5",
      dot: "bg-red-500",
      border: "border-red-200",
      btn: "text-red-600 hover:bg-red-500/10",
    },
    amber: {
      header: "from-amber-500/20 to-amber-500/5",
      dot: "bg-amber-500",
      border: "border-amber-200",
      btn: "text-amber-600 hover:bg-amber-500/10",
    },
    emerald: {
      header: "from-emerald-500/20 to-emerald-500/5",
      dot: "bg-emerald-500",
      border: "border-emerald-200",
      btn: "text-emerald-600 hover:bg-emerald-500/10",
    },
  }

  const styles = colorStyles[color]
  const displaySlides = expanded ? slides : slides.slice(0, INITIAL_SHOW)
  const hasMore = slides.length > INITIAL_SHOW

  return (
    <Card className={`overflow-hidden ${styles.border}`}>
      <div className={`bg-gradient-to-b ${styles.header} px-4 py-4`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className={`h-3 w-3 rounded-full ${styles.dot} shadow-lg`} />
            <CardTitle className="text-base">{title}</CardTitle>
          </div>
          <Badge variant="secondary" className="font-semibold">
            {slides.length}
          </Badge>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      </div>
      <CardContent className="max-h-[600px] space-y-2 overflow-y-auto p-3">
        {slides.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">No slides in this category</p>
        ) : (
          <>
            {displaySlides.map((slide) => (
              <SlideCard key={slide.slide_id} slide={slide} onClick={() => onViewSlide(slide)} compact />
            ))}
            {hasMore && !expanded && (
              <Button
                variant="ghost"
                size="sm"
                className={`w-full mt-2 ${styles.btn}`}
                onClick={() => setExpanded(true)}
              >
                <ChevronDown className="mr-1 h-4 w-4" />
                Show {slides.length - INITIAL_SHOW} more slides
              </Button>
            )}
            {hasMore && expanded && (
              <Button
                variant="ghost"
                size="sm"
                className={`w-full mt-2 ${styles.btn}`}
                onClick={() => setExpanded(false)}
              >
                Show less
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

function StatCard({
  label,
  value,
  total,
  color,
  icon,
}: {
  label: string
  value: number
  total: number
  color: "red" | "amber" | "emerald"
  icon: React.ReactNode
}) {
  const percentage = total > 0 ? Math.round((value / total) * 100) : 0
  
  const colorStyles = {
    red: {
      bg: "from-red-500/10 to-red-500/5",
      iconBg: "bg-red-500",
      text: "text-red-600",
      bar: "bg-red-500",
    },
    amber: {
      bg: "from-amber-500/10 to-amber-500/5",
      iconBg: "bg-amber-500",
      text: "text-amber-600",
      bar: "bg-amber-500",
    },
    emerald: {
      bg: "from-emerald-500/10 to-emerald-500/5",
      iconBg: "bg-emerald-500",
      text: "text-emerald-600",
      bar: "bg-emerald-500",
    },
  }

  const styles = colorStyles[color]

  return (
    <Card className={`overflow-hidden bg-gradient-to-br ${styles.bg}`}>
      <CardContent className="pt-5 pb-4">
        <div className="flex items-center justify-between">
          <div>
            <p className={`text-3xl font-bold ${styles.text}`}>{value}</p>
            <p className="text-sm text-muted-foreground">{label}</p>
          </div>
          <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${styles.iconBg} text-white shadow-lg`}>
            {icon}
          </div>
        </div>
        <div className="mt-3 h-1.5 w-full rounded-full bg-muted">
          <div
            className={`h-full rounded-full ${styles.bar} transition-all duration-500`}
            style={{ width: `${percentage}%` }}
          />
        </div>
        <p className="mt-1.5 text-xs text-muted-foreground">{percentage}% of total slides</p>
      </CardContent>
    </Card>
  )
}

function StudyPlanPanel({ subjectName }: { subjectName: string }) {
  const [plan, setPlan] = useState<StudyPlan | null>(null)
  const [generating, setGenerating] = useState(false)
  const [mode, setMode] = useState<AIMode>("fast")
  const [skipCache, setSkipCache] = useState(false)

  const handleGenerate = async () => {
    try {
      setGenerating(true)
      const result = await generateStudyPlan(subjectName, mode, skipCache)
      setPlan(result)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to generate study plan")
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card className="border-2 border-blue-500/20 bg-gradient-to-br from-blue-500/5 to-transparent">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500 text-white shadow-lg shadow-blue-500/25">
              <BookOpen className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>AI Study Plan Generator</CardTitle>
              <CardDescription>
                Generate a personalized study plan based on your materials and PYQ analysis
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <AISettings
            mode={mode}
            skipCache={skipCache}
            onModeChange={setMode}
            onSkipCacheChange={setSkipCache}
          />
          <Button onClick={handleGenerate} disabled={generating} className="h-11 px-6 bg-blue-600 hover:bg-blue-700">
            {generating ? (
              <>
                <Spinner className="mr-2 h-4 w-4" />
                Generating Plan...
              </>
            ) : plan ? (
              "Regenerate Plan"
            ) : (
              "Generate Study Plan"
            )}
          </Button>
        </CardContent>
      </Card>

      {plan && (
        <Card className="overflow-hidden">
          <div className="border-b bg-gradient-to-r from-blue-500/10 to-transparent px-6 py-4">
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="secondary" className="bg-blue-500/10 text-blue-600">
                <BookOpen className="mr-1 h-3 w-3" />
                Study Plan
              </Badge>
              {plan.stats?.total_slides != null && (
                <Badge variant="outline">{plan.stats.total_slides} slides</Badge>
              )}
              {plan.stats?.high_priority != null && (
                <Badge variant="outline" className="border-red-200 text-red-600">{plan.stats.high_priority} high priority</Badge>
              )}
              {(plan.stats?.pyq_questions ?? 0) > 0 && (
                <Badge variant="outline" className="border-amber-200 text-amber-600">{plan.stats!.pyq_questions} PYQ questions</Badge>
              )}
              {plan.model_used && (
                <span className="ml-auto text-xs text-muted-foreground">Model: {plan.model_used}</span>
              )}
            </div>
          </div>
          <CardContent className="pt-6">
            <div className="select-text rounded-xl border bg-muted/30 p-6">
              <MarkdownRenderer content={plan.plan || plan.answer || ""} />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function RevisionPanel({ subjectName }: { subjectName: string }) {
  const [hours, setHours] = useState("3")
  const [schedule, setSchedule] = useState<RevisionSchedule | null>(null)
  const [generating, setGenerating] = useState(false)
  const [mode, setMode] = useState<AIMode>("fast")
  const [skipCache, setSkipCache] = useState(false)

  const handleGenerate = async () => {
    const hoursNum = parseFloat(hours)
    if (isNaN(hoursNum) || hoursNum <= 0 || hoursNum > 24) {
      toast.error("Please enter a valid number of hours (1-24)")
      return
    }

    try {
      setGenerating(true)
      const result = await generateRevision(subjectName, hoursNum, mode, skipCache)
      setSchedule(result)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to generate revision schedule")
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card className="border-2 border-orange-500/20 bg-gradient-to-br from-orange-500/5 to-transparent">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-500 text-white shadow-lg shadow-orange-500/25">
              <Clock className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>Revision Schedule Generator</CardTitle>
              <CardDescription>
                Generate a time-constrained revision schedule for last-minute preparation
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">Hours available</label>
              <Input
                type="number"
                placeholder="Hours"
                value={hours}
                onChange={(e) => setHours(e.target.value)}
                className="w-32 h-11"
                min="1"
                max="24"
              />
            </div>
            <Button onClick={handleGenerate} disabled={generating} className="h-11 px-6 bg-orange-600 hover:bg-orange-700">
              {generating ? (
                <>
                  <Spinner className="mr-2 h-4 w-4" />
                  Generating...
                </>
              ) : schedule ? (
                "Regenerate Schedule"
              ) : (
                "Generate Schedule"
              )}
            </Button>
          </div>
          <AISettings
            mode={mode}
            skipCache={skipCache}
            onModeChange={setMode}
            onSkipCacheChange={setSkipCache}
          />
        </CardContent>
      </Card>

      {schedule && (
        <Card className="overflow-hidden">
          <div className="border-b bg-gradient-to-r from-orange-500/10 to-transparent px-6 py-4">
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="secondary" className="bg-orange-500/10 text-orange-600">
                <Clock className="mr-1 h-3 w-3" />
                Revision Schedule
              </Badge>
              {schedule.time_minutes != null && (
                <Badge variant="outline">{schedule.time_minutes} minutes</Badge>
              )}
              {schedule.stats?.high_priority != null && (
                <Badge variant="outline" className="border-red-200 text-red-600">{schedule.stats.high_priority} high priority</Badge>
              )}
              {schedule.model_used && (
                <span className="ml-auto text-xs text-muted-foreground">Model: {schedule.model_used}</span>
              )}
            </div>
          </div>
          <CardContent className="pt-6">
            <div className="select-text rounded-xl border bg-muted/30 p-6">
              <MarkdownRenderer content={schedule.plan || schedule.answer || ""} />
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function WeakSpotsPanel({ subjectName }: { subjectName: string }) {
  const [data, setData] = useState<WeakSpotsResult | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const result = await getWeakSpots(subjectName)
        setData(result)
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to load weak spots")
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [subjectName])

  if (loading) {
    return <Skeleton className="h-64 w-full rounded-xl" />
  }

  if (!data || data.weak_spots.length === 0) {
    return (
      <Card className="border-2 border-emerald-500/20">
        <CardContent className="flex flex-col items-center justify-center py-16">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/10">
            <Target className="h-8 w-8 text-emerald-500" />
          </div>
          <p className="mt-4 text-lg font-semibold text-foreground">No Weak Spots Found</p>
          <p className="text-sm text-muted-foreground">Your materials have good coverage - great work!</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="overflow-hidden border-2 border-amber-500/20">
      <div className="bg-gradient-to-r from-amber-500/10 to-transparent px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500 text-white shadow-lg shadow-amber-500/25">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div>
            <CardTitle>Weak Spots Analysis</CardTitle>
            <CardDescription>
              {data.total} topics with high PYQ frequency but potentially low coverage
            </CardDescription>
          </div>
        </div>
      </div>
      <CardContent className="pt-6">
        <div className="space-y-3">
          {data.weak_spots.map((spot, i) => {
            const priorityStyles = {
              high: { bg: "bg-red-500/10", border: "border-red-200", text: "text-red-600", dot: "bg-red-500" },
              medium: { bg: "bg-amber-500/10", border: "border-amber-200", text: "text-amber-600", dot: "bg-amber-500" },
              low: { bg: "bg-emerald-500/10", border: "border-emerald-200", text: "text-emerald-600", dot: "bg-emerald-500" },
            }
            const styles = priorityStyles[spot.priority]

            return (
              <div
                key={i}
                className={`flex items-center justify-between rounded-xl border ${styles.border} ${styles.bg} p-4 transition-all hover:shadow-md`}
              >
                <div className="flex items-center gap-3">
                  <div className={`h-3 w-3 rounded-full ${styles.dot} shadow-sm`} />
                  <div>
                    <p className="font-semibold text-foreground">{spot.chapter}</p>
                    <p className="text-sm text-muted-foreground">
                      {spot.slide_count} slides · {spot.pyq_hits} PYQ hits{(spot.avg_importance != null && !isNaN(spot.avg_importance) && spot.avg_importance > 0) ? ` · ${Math.round(spot.avg_importance * 100)}% importance` : ""}
                    </p>
                  </div>
                </div>
                <Badge className={`${styles.bg} ${styles.text} border ${styles.border}`}>
                  {spot.priority} priority
                </Badge>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = (e: React.MouseEvent | React.KeyboardEvent) => {
    e.stopPropagation()
    if (navigator.clipboard?.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
      })
    } else {
      // Fallback for HTTP (non-secure context)
      const ta = document.createElement("textarea")
      ta.value = text
      ta.style.position = "fixed"
      ta.style.opacity = "0"
      document.body.appendChild(ta)
      ta.select()
      document.execCommand("copy")
      document.body.removeChild(ta)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  // Rendered as div to avoid <button> nested inside AccordionTrigger <button>
  return (
    <div
      role="button"
      tabIndex={0}
      className="flex h-7 w-7 shrink-0 cursor-pointer items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
      onClick={handleCopy}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") handleCopy(e) }}
      title="Copy question"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
    </div>
  )
}

function PYQReportPanel({ subjectName }: { subjectName: string }) {
  const [data, setData] = useState<PYQReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [viewingSlide, setViewingSlide] = useState<Slide | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const result = await getPYQReport(subjectName)
        setData(result)
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to load PYQ report")
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [subjectName])

  if (loading) {
    return <Skeleton className="h-64 w-full rounded-xl" />
  }

  if (!data || data.questions.length === 0) {
    return (
      <Card className="border-2 border-muted">
        <CardContent className="flex flex-col items-center justify-center py-16">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
            <FileQuestion className="h-8 w-8 text-muted-foreground" />
          </div>
          <p className="mt-4 text-lg font-semibold text-foreground">No PYQ Data</p>
          <p className="text-sm text-muted-foreground">Upload past year question papers to see analysis</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card className="overflow-hidden">
      <div className="border-b bg-gradient-to-r from-violet-500/10 to-transparent px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500 text-white shadow-lg shadow-violet-500/25">
            <FileQuestion className="h-5 w-5" />
          </div>
          <div>
            <CardTitle>PYQ Analysis</CardTitle>
            <CardDescription>
              {data.total_questions} past year questions mapped to your study materials
            </CardDescription>
          </div>
        </div>
      </div>
      <CardContent className="pt-6">
        <Accordion type="single" collapsible className="w-full space-y-2">
          {data.questions.map((question) => (
            <AccordionItem
              key={question.question_id}
              value={String(question.question_id)}
              className="rounded-xl border bg-muted/20 px-4"
            >
              <AccordionTrigger className="text-left py-4 hover:no-underline">
                <div className="flex items-start gap-2 flex-1 pr-4">
                  <div className="flex-1 select-text">
                    <p className="text-sm font-medium leading-relaxed select-text cursor-text">{question.question_text}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className="text-xs">
                        {question.source_file}
                      </Badge>
                      <Badge variant="secondary" className="text-xs">
                        {question.matched_slides.length} matched slides
                      </Badge>
                    </div>
                  </div>
                  <CopyButton text={question.question_text} />
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <div className="grid gap-3 pb-4 pt-2 sm:grid-cols-2">
                  {question.matched_slides.map((slide) => (
                    <SlideCard
                      key={slide.slide_id}
                      slide={slide}
                      onClick={() => setViewingSlide(slide)}
                      showSimilarity={slide.similarity_score}
                    />
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </CardContent>

      {viewingSlide && (
        <SlideViewer slide={viewingSlide} onClose={() => setViewingSlide(null)} />
      )}
    </Card>
  )
}
