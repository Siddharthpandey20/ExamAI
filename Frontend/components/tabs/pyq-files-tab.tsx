"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { getPYQFiles, getFileUrl } from "@/lib/api"
import type { PYQFile } from "@/lib/types"
import { FileQuestion, Eye, HelpCircle, FileText } from "lucide-react"
import { toast } from "sonner"
import { FileViewerModal } from "@/components/file-viewer-modal"

interface PYQFilesTabProps {
  subjectName: string
}

export function PYQFilesTab({ subjectName }: PYQFilesTabProps) {
  const [files, setFiles] = useState<PYQFile[]>([])
  const [loading, setLoading] = useState(true)
  const [previewFile, setPreviewFile] = useState<PYQFile | null>(null)

  useEffect(() => {
    const fetchFiles = async () => {
      try {
        setLoading(true)
        const data = await getPYQFiles(subjectName)
        setFiles(data.files)
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to load PYQ files")
      } finally {
        setLoading(false)
      }
    }

    fetchFiles()
  }, [subjectName])

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-24 w-full rounded-xl" />
        ))}
      </div>
    )
  }

  if (files.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center justify-center py-16">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
            <FileQuestion className="h-8 w-8 text-muted-foreground" />
          </div>
          <p className="mt-4 text-lg font-medium text-foreground">No PYQ Files</p>
          <p className="text-sm text-muted-foreground">Upload past year question papers to see them here</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* File Viewer Modal */}
      {previewFile && (
        <FileViewerModal
          fileUrl={getFileUrl(subjectName, "pyq_uploads", previewFile.filename)}
          filename={previewFile.filename}
          onClose={() => setPreviewFile(null)}
          badgeText={previewFile.question_count > 0 ? `${previewFile.question_count} questions extracted` : undefined}
          variant="pyq"
        />
      )}

      {/* Stats header */}
      <Card className="border-2 border-amber-500/20 bg-gradient-to-br from-amber-500/5 to-transparent">
        <CardContent className="flex items-center gap-4 py-5">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-amber-500 text-white shadow-lg shadow-amber-500/25">
            <FileQuestion className="h-6 w-6" />
          </div>
          <div>
            <p className="text-2xl font-bold text-foreground">{files.length}</p>
            <p className="text-sm text-muted-foreground">
              PYQ paper{files.length !== 1 ? "s" : ""} uploaded ·{" "}
              {files.reduce((sum, f) => sum + f.question_count, 0)} questions extracted
            </p>
          </div>
        </CardContent>
      </Card>

      {/* File list */}
      <div className="space-y-3">
        {files.map((file) => (
          <Card
            key={file.filename}
            className="cursor-pointer transition-all hover:border-amber-300 hover:shadow-md"
            onClick={() => setPreviewFile(file)}
          >
            <CardContent className="flex items-center justify-between p-4">
              <div className="flex items-center gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-amber-500/10 text-amber-600">
                  <FileText className="h-6 w-6" />
                </div>
                <div className="space-y-1">
                  <h3 className="font-medium text-foreground">{file.filename}</h3>
                  <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                    <span>{formatFileSize(file.size_bytes)}</span>
                    <span className="flex items-center gap-1">
                      <HelpCircle className="h-3 w-3" />
                      {file.question_count} questions extracted
                    </span>
                  </div>
                </div>
              </div>
              <Button variant="outline" size="sm">
                <Eye className="mr-2 h-4 w-4" />
                View
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
