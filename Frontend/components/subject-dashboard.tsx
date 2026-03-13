"use client"

import { useEffect, useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Empty } from "@/components/ui/empty"
import { getSubjects, createSubject, toTitleCase } from "@/lib/api"
import type { SubjectStats } from "@/lib/types"
import { Plus, BookOpen, FileText, HelpCircle, GraduationCap, Sparkles } from "lucide-react"
import { toast } from "sonner"

interface SubjectDashboardProps {
  onSelectSubject: (name: string) => void
}

// Gradient color pairs for subject cards
const SUBJECT_GRADIENTS = [
  { from: "from-blue-500/10", to: "to-indigo-500/10", accent: "bg-blue-500", border: "hover:border-blue-300" },
  { from: "from-emerald-500/10", to: "to-teal-500/10", accent: "bg-emerald-500", border: "hover:border-emerald-300" },
  { from: "from-violet-500/10", to: "to-purple-500/10", accent: "bg-violet-500", border: "hover:border-violet-300" },
  { from: "from-amber-500/10", to: "to-orange-500/10", accent: "bg-amber-500", border: "hover:border-amber-300" },
  { from: "from-rose-500/10", to: "to-pink-500/10", accent: "bg-rose-500", border: "hover:border-rose-300" },
  { from: "from-cyan-500/10", to: "to-sky-500/10", accent: "bg-cyan-500", border: "hover:border-cyan-300" },
]

export function SubjectDashboard({ onSelectSubject }: SubjectDashboardProps) {
  const [subjects, setSubjects] = useState<SubjectStats[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [newSubjectName, setNewSubjectName] = useState("")
  const [creating, setCreating] = useState(false)

  const fetchSubjects = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await getSubjects()
      setSubjects(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load subjects")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSubjects()
  }, [])

  const handleCreateSubject = async () => {
    if (!newSubjectName.trim()) {
      toast.error("Please enter a subject name")
      return
    }

    try {
      setCreating(true)
      await createSubject(newSubjectName.trim())
      toast.success(`Created subject: ${toTitleCase(newSubjectName.trim())}`)
      setNewSubjectName("")
      setCreateOpen(false)
      fetchSubjects()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create subject")
    } finally {
      setCreating(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <Skeleton className="h-9 w-56" />
            <Skeleton className="mt-2 h-5 w-72" />
          </div>
        </div>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-52 rounded-2xl" />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Empty
          icon={<GraduationCap className="h-12 w-12" />}
          title="Connection Error"
          description={error}
          actions={
            <Button onClick={fetchSubjects} variant="outline">
              Try Again
            </Button>
          }
        />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-foreground">Your Subjects</h2>
          <p className="mt-1 text-muted-foreground">
            {subjects.length === 0
              ? "Get started by creating your first subject"
              : `${subjects.length} subject${subjects.length !== 1 ? "s" : ""} in your library`}
          </p>
        </div>
      </div>

      {/* Subject Grid */}
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {/* Create New Subject Card */}
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Card className="group cursor-pointer border-2 border-dashed bg-gradient-to-br from-muted/50 to-muted/30 transition-all duration-300 hover:border-primary/50 hover:shadow-lg hover:shadow-primary/5">
              <CardContent className="flex h-full min-h-[220px] flex-col items-center justify-center gap-4 py-8">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary transition-transform group-hover:scale-110">
                  <Plus className="h-7 w-7" />
                </div>
                <div className="text-center">
                  <p className="text-lg font-semibold text-foreground">New Subject</p>
                  <p className="mt-1 text-sm text-muted-foreground">Add a course to get started</p>
                </div>
              </CardContent>
            </Card>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Subject</DialogTitle>
              <DialogDescription>
                Enter the name of your subject or course. You can upload materials after creating it.
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <Input
                placeholder="e.g., Computer Networks"
                value={newSubjectName}
                onChange={(e) => setNewSubjectName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreateSubject()}
                className="h-11"
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleCreateSubject} disabled={creating}>
                {creating ? "Creating..." : "Create Subject"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Subject Cards */}
        {subjects.map((subject, index) => (
          <SubjectCard
            key={subject.name}
            subject={subject}
            gradient={SUBJECT_GRADIENTS[index % SUBJECT_GRADIENTS.length]}
            onClick={() => onSelectSubject(subject.name)}
          />
        ))}
      </div>
    </div>
  )
}

interface SubjectCardProps {
  subject: SubjectStats
  gradient: typeof SUBJECT_GRADIENTS[number]
  onClick: () => void
}

function SubjectCard({ subject, gradient, onClick }: SubjectCardProps) {
  return (
    <Card
      className={`group cursor-pointer overflow-hidden p-0 gap-0 min-h-[220px] transition-all duration-300 ${gradient.border} hover:shadow-xl hover:shadow-black/5 hover:-translate-y-1`}
      onClick={onClick}
    >
      <div className={`flex-1 flex flex-col bg-gradient-to-br ${gradient.from} ${gradient.to} p-5`}>
        {/* Header: icon + name/date on left, PYQ badge on right */}
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-3 min-w-0">
            <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${gradient.accent} text-white shadow-md`}>
              <BookOpen className="h-6 w-6" />
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-bold leading-tight truncate text-foreground">{toTitleCase(subject.name)}</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {new Date(subject.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
              </p>
            </div>
          </div>
          {subject.has_pyq && (
            <Badge className="bg-amber-500/10 text-amber-600 border-amber-200 shrink-0 mt-0.5">
              <Sparkles className="mr-1 h-3 w-3" />
              PYQ
            </Badge>
          )}
        </div>

        {/* Push stats to bottom */}
        <div className="flex-1" />

        {/* Stats */}
        <div className="border-t border-border/40 pt-4 grid grid-cols-2 gap-y-3 gap-x-4">
          <StatItem icon={<FileText className="h-3.5 w-3.5" />} label="Documents" value={subject.documents} />
          <StatItem icon={<BookOpen className="h-3.5 w-3.5" />} label="Slides" value={subject.slides} />
          <StatItem icon={<GraduationCap className="h-3.5 w-3.5" />} label="PYQ Papers" value={subject.pyq_papers} />
          <StatItem icon={<HelpCircle className="h-3.5 w-3.5" />} label="Questions" value={subject.pyq_questions} />
        </div>
      </div>
    </Card>
  )
}

function StatItem({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: number
}) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-background/60 text-muted-foreground">
        {icon}
      </div>
      <div>
        <p className="text-lg font-semibold text-foreground leading-none">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  )
}
