"use client"

/**
 * pdf-viewer.tsx
 *
 * Contains all react-pdf / pdfjs-dist code which uses browser-only APIs
 * (DOMMatrix, Canvas) at module evaluation time.
 *
 * This file MUST only be loaded on the client — import it via next/dynamic
 * with { ssr: false }.  Never import it directly.
 */

import { Document, Page, pdfjs } from "react-pdf"
import { Button } from "@/components/ui/button"
import { Loader2 } from "lucide-react"
import "react-pdf/dist/Page/AnnotationLayer.css"
import "react-pdf/dist/Page/TextLayer.css"

// Worker is served from /public/pdf.worker.min.mjs (copied at build time)
pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs"

export interface PdfViewerProps {
  fileUrl: string
  scale: number
  numPages: number
  onLoadSuccess: (n: number) => void
  setPageRef: (index: number, el: HTMLDivElement | null) => void
}

export function PdfViewer({
  fileUrl,
  scale,
  numPages,
  onLoadSuccess,
  setPageRef,
}: PdfViewerProps) {
  return (
    <div className="flex flex-col items-center py-5 gap-3">
      <Document
        file={fileUrl}
        onLoadSuccess={({ numPages: n }) => onLoadSuccess(n)}
        loading={
          <div className="flex flex-col items-center justify-center gap-3 py-32">
            <Loader2 className="h-9 w-9 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Loading document…</p>
          </div>
        }
        error={
          <div className="flex flex-col items-center justify-center gap-4 py-32">
            <p className="text-sm font-medium text-destructive">Failed to load PDF.</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => window.open(fileUrl, "_blank")}
            >
              Open in new tab
            </Button>
          </div>
        }
      >
        {numPages > 0 &&
          Array.from({ length: numPages }, (_, i) => (
            <div
              key={i}
              data-page={i + 1}
              ref={el => setPageRef(i, el)}
              className="shadow-xl rounded overflow-hidden mb-3"
            >
              <Page
                pageNumber={i + 1}
                scale={scale}
                renderTextLayer
                renderAnnotationLayer
              />
            </div>
          ))}
      </Document>
    </div>
  )
}
