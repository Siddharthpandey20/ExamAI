"use client"

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet"
import { ScrollArea } from "@/components/ui/scroll-area"
import { getJobsOverview, toTitleCase } from "@/lib/api"
import type { JobOverview } from "@/lib/types"
import { Activity, CheckCircle2, XCircle, Clock, Loader2 } from "lucide-react"

export function JobMonitorPanel() {
  const [jobs, setJobs] = useState<JobOverview[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)

  const fetchJobs = async () => {
    try {
      setLoading(true)
      const data = await getJobsOverview()
      setJobs(data)
    } catch (err) {
      console.error("Failed to fetch jobs:", err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) {
      fetchJobs()
      // Poll for updates while open
      const interval = setInterval(fetchJobs, 3000)
      return () => clearInterval(interval)
    }
  }, [open])

  const activeJobs = jobs.filter((j) => j.status === "processing" || j.status === "pending")
  const hasActiveJobs = activeJobs.length > 0

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="relative">
          <Activity className="mr-2 h-4 w-4" />
          Jobs
          {hasActiveJobs && (
            <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">
              {activeJobs.length}
            </span>
          )}
        </Button>
      </SheetTrigger>
      <SheetContent className="w-full sm:max-w-lg">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            Processing Jobs
            {hasActiveJobs && (
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-primary" />
              </span>
            )}
          </SheetTitle>
          <SheetDescription>
            Track your file uploads and processing status
          </SheetDescription>
        </SheetHeader>

        <ScrollArea className="mt-6 h-[calc(100vh-200px)]">
          {jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Activity className="h-12 w-12 text-muted-foreground" />
              <p className="mt-4 text-muted-foreground">No jobs yet</p>
              <p className="text-sm text-muted-foreground">
                Upload files to see processing status here
              </p>
            </div>
          ) : (
            <div className="space-y-4 pr-4">
              {jobs.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  )
}

function JobCard({ job }: { job: JobOverview }) {
  const statusConfig = {
    pending: {
      icon: <Clock className="h-4 w-4 text-muted-foreground" />,
      label: "Pending",
      className: "bg-muted text-muted-foreground",
    },
    processing: {
      icon: <Loader2 className="h-4 w-4 animate-spin text-primary" />,
      label: "Processing",
      className: "bg-primary/10 text-primary",
    },
    completed: {
      icon: <CheckCircle2 className="h-4 w-4 text-[var(--success)]" />,
      label: "Completed",
      className: "bg-[var(--success)]/10 text-[var(--success)]",
    },
    failed: {
      icon: <XCircle className="h-4 w-4 text-[var(--danger)]" />,
      label: "Failed",
      className: "bg-[var(--danger)]/10 text-[var(--danger)]",
    },
  }

  const config = statusConfig[job.status]

  // Study material phases: ingest → structure → index
  // PYQ phases: ingest_pyq → extract → map
  const phases =
    job.job_type === "study_material"
      ? ["ingest", "structure", "index"]
      : ["ingest_pyq", "extract", "map"]

  const currentPhaseIndex = job.current_phase
    ? phases.indexOf(job.current_phase)
    : job.status === "completed"
      ? phases.length
      : 0

  return (
    <div className="rounded-lg border bg-card p-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-3">
          {config.icon}
          <div className="space-y-1">
            <p className="font-medium text-foreground line-clamp-1">{job.filename}</p>
            <p className="text-xs text-muted-foreground">
              {toTitleCase(job.subject)} · {job.job_type === "study_material" ? "Study Material" : "PYQ"}
            </p>
          </div>
        </div>
        <Badge className={config.className}>{config.label}</Badge>
      </div>

      {/* Progress */}
      {(job.status === "processing" || job.status === "pending") && (
        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">
              Stage: <span className="font-medium text-foreground capitalize">{job.current_phase?.replace("_", " ") || "Waiting"}</span>
            </span>
            <span className="font-medium">{job.overall_progress_pct}%</span>
          </div>
          <Progress value={job.overall_progress_pct} className="h-2" />
          {job.progress_detail && (
            <p className="text-xs text-muted-foreground">{job.progress_detail}</p>
          )}
        </div>
      )}

      {/* Phase Pipeline */}
      <div className="mt-4 flex items-center gap-1">
        {phases.map((phase, i) => {
          const isComplete = i < currentPhaseIndex || job.status === "completed"
          const isCurrent = i === currentPhaseIndex && job.status === "processing"
          const isFailed = job.status === "failed" && i === currentPhaseIndex

          return (
            <div key={phase} className="flex flex-1 items-center">
              <div
                className={`h-2 flex-1 rounded-full transition-all ${
                  isComplete
                    ? "bg-[var(--success)]"
                    : isCurrent
                      ? "bg-primary animate-pulse"
                      : isFailed
                        ? "bg-[var(--danger)]"
                        : "bg-muted"
                }`}
              />
              {i < phases.length - 1 && <div className="w-1" />}
            </div>
          )
        })}
      </div>
      <div className="mt-1 flex justify-between text-xs text-muted-foreground">
        {phases.map((phase) => (
          <span key={phase} className="capitalize">
            {phase.replace("_", " ")}
          </span>
        ))}
      </div>

      {/* Duration / Error */}
      <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
        {job.total_duration && <span>Duration: {job.total_duration}</span>}
        {job.error && (
          <span className="text-[var(--danger)] line-clamp-1">{job.error}</span>
        )}
        {!job.total_duration && !job.error && <span>Started: {job.created_at}</span>}
      </div>
    </div>
  )
}
