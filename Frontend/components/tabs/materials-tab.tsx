"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Empty } from "@/components/ui/empty"
import { getDocuments, getDocument, getPriorityLevel, toTitleCase } from "@/lib/api"
import type { Document, DocumentDetail, Slide } from "@/lib/types"
import { FileText, BookOpen, Target, ChevronRight, X, Zap, Eye } from "lucide-react"
import { toast } from "sonner"
import { SlideViewer } from "@/components/slide-viewer"
import { SlideCard } from "@/components/slide-card"
import { FileViewerModal } from "@/components/file-viewer-modal"
import { getFileUrl } from "@/lib/api"

interface MaterialsTabProps {
  subjectName: string
}

export function MaterialsTab({ subjectName }: MaterialsTabProps) {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedDoc, setSelectedDoc] = useState<DocumentDetail | null>(null)
  const [loadingDoc, setLoadingDoc] = useState(false)
  const [viewingSlide, setViewingSlide] = useState<Slide | null>(null)
  const [viewingFile, setViewingFile] = useState<string | null>(null)

  useEffect(() => {
    const fetchDocuments = async () => {
      try {
        setLoading(true)
        const data = await getDocuments(subjectName)
        setDocuments(data.documents)
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Failed to load documents")
      } finally {
        setLoading(false)
      }
    }

    fetchDocuments()
  }, [subjectName])

  const handleSelectDocument = async (docId: number) => {
    try {
      setLoadingDoc(true)
      const data = await getDocument(subjectName, docId)
      setSelectedDoc(data)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load document")
    } finally {
      setLoadingDoc(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-32 w-full rounded-xl" />
        ))}
      </div>
    )
  }

  if (documents.length === 0) {
    return (
      <Empty
        icon={<FileText className="h-10 w-10" />}
        title="No Materials Yet"
        description="Upload your lecture slides and documents to get started"
      />
    )
  }

  // Document Detail View
  if (selectedDoc) {
    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" onClick={() => setSelectedDoc(null)}>
              <X className="h-5 w-5" />
            </Button>
            <div>
              <h3 className="text-lg font-semibold text-foreground">{selectedDoc.filename}</h3>
              <p className="text-sm text-muted-foreground">
                {selectedDoc.total_slides} slides · {selectedDoc.high_priority_slides} high priority
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setViewingFile(selectedDoc.filename)}
          >
            <Eye className="mr-2 h-4 w-4" />
            View Original
          </Button>
        </div>

        {/* Summary */}
        {selectedDoc.summary && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground leading-relaxed">{selectedDoc.summary}</p>
              {selectedDoc.core_topics && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {selectedDoc.core_topics.split(",").map((topic, i) => (
                    <Badge key={i} variant="secondary">
                      {topic.trim()}
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Chapters */}
        {selectedDoc.chapters && selectedDoc.chapters.length > 0 && (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Chapters</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {selectedDoc.chapters.map((chapter, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-lg border bg-muted/30 p-3"
                  >
                    <div>
                      <p className="font-medium text-foreground">{chapter.name}</p>
                      <p className="text-sm text-muted-foreground">
                        Slides {chapter.slide_range}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {(Array.isArray(chapter.topics) 
                        ? chapter.topics 
                        : typeof chapter.topics === 'string' 
                          ? chapter.topics.split(',').map(t => t.trim()).filter(Boolean)
                          : []
                      ).slice(0, 3).map((topic, j) => (
                        <Badge key={j} variant="outline" className="text-xs">
                          {topic}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Slides */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">All Slides</CardTitle>
            <CardDescription>Click a slide to view details</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {selectedDoc.slides.map((slide) => (
                <SlideCard
                  key={slide.slide_id}
                  slide={slide}
                  onClick={() => setViewingSlide(slide)}
                />
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Slide Viewer Modal */}
        {viewingSlide && (
          <SlideViewer slide={viewingSlide} onClose={() => setViewingSlide(null)} />
        )}

        {/* File Viewer Modal */}
        {viewingFile && (
          <FileViewerModal
            fileUrl={getFileUrl(subjectName, "uploads", viewingFile)}
            filename={viewingFile}
            onClose={() => setViewingFile(null)}
            variant="document"
          />
        )}
      </div>
    )
  }

  // Document List View
  return (
    <div className="space-y-4">
      {documents.map((doc) => (
        <DocumentCard
          key={doc.id}
          document={doc}
          onClick={() => handleSelectDocument(doc.id)}
          loading={loadingDoc}
        />
      ))}
    </div>
  )
}

function DocumentCard({
  document,
  onClick,
  loading,
}: {
  document: Document
  onClick: () => void
  loading: boolean
}) {
  const safeImportance = (document.avg_importance != null && !isNaN(document.avg_importance)) ? document.avg_importance : 0
  const priorityColor =
    safeImportance >= 0.4
      ? "text-[var(--priority-high)]"
      : safeImportance >= 0.15
        ? "text-[var(--priority-medium)]"
        : "text-[var(--priority-low)]"

  return (
    <Card
      className="cursor-pointer transition-all hover:border-primary hover:shadow-md"
      onClick={onClick}
    >
      <CardContent className="flex items-center justify-between p-4">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <FileText className="h-6 w-6" />
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <h3 className="font-medium text-foreground">{document.filename}</h3>
              {document.status === "pending" && (
                <Badge variant="outline" className="text-xs">Processing</Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground line-clamp-1">
              {document.summary || "No summary available"}
            </p>
            <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <BookOpen className="h-3 w-3" />
                {document.total_slides} slides
              </span>
              <span className="flex items-center gap-1">
                <Target className="h-3 w-3" />
                {document.total_pyq_hits} PYQ hits
              </span>
              <span className={`flex items-center gap-1 ${priorityColor}`}>
                <Zap className="h-3 w-3" />
                {safeImportance > 0 ? `${Math.round(safeImportance * 100)}% importance` : "Not scored yet"}
              </span>
            </div>
          </div>
        </div>
        <ChevronRight className="h-5 w-5 text-muted-foreground" />
      </CardContent>
    </Card>
  )
}
