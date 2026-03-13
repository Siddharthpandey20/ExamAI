"use client"

import { useState } from "react"
import { SubjectDashboard } from "@/components/subject-dashboard"
import { SubjectWorkspace } from "@/components/subject-workspace"
import { JobMonitorPanel } from "@/components/job-monitor-panel"
import { UploadButton } from "@/components/upload-button"
import { GraduationCap } from "lucide-react"

export default function Home() {
  const [selectedSubject, setSelectedSubject] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const handleRefresh = () => {
    setRefreshKey((prev) => prev + 1)
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
        <div className="mx-auto flex h-16 max-w-[1400px] w-full items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <GraduationCap className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-foreground">ExamPrep AI</h1>
              <p className="text-xs text-muted-foreground">Smart Study Assistant</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <JobMonitorPanel />
            {selectedSubject && (
              <UploadButton subject={selectedSubject} onUploadComplete={handleRefresh} />
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-[1400px] w-full px-4 py-6 sm:px-6 lg:px-8">
        {selectedSubject ? (
          <SubjectWorkspace
            key={`${selectedSubject}-${refreshKey}`}
            subjectName={selectedSubject}
            onBack={() => setSelectedSubject(null)}
          />
        ) : (
          <SubjectDashboard
            key={refreshKey}
            onSelectSubject={setSelectedSubject}
          />
        )}
      </main>
    </div>
  )
}
