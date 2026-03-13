"use client"

import { useState, useCallback, useEffect, useRef } from "react"
import dynamic from "next/dynamic"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  ExternalLink, X, FileText, FileQuestion,
  Minus, Plus, ChevronLeft, ChevronRight,
} from "lucide-react"
import type { PdfViewerProps } from "./pdf-viewer"

// Loaded only on the client — pdfjs uses DOMMatrix which doesn't exist in Node
const PdfViewer = dynamic<PdfViewerProps>(
  () => import("./pdf-viewer").then(m => ({ default: m.PdfViewer })),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center py-32 text-sm text-muted-foreground">
        Loading viewer…
      </div>
    ),
  }
)

const MIN_SCALE = 0.5
const MAX_SCALE = 3.0
const ZOOM_STEP = 0.2

interface FileViewerModalProps {
  fileUrl: string
  filename: string
  onClose: () => void
  badgeText?: string
  variant?: "document" | "pyq"
}

export function FileViewerModal({
  fileUrl,
  filename,
  onClose,
  badgeText,
  variant = "document",
}: FileViewerModalProps) {
  const ext = filename.toLowerCase().slice(filename.lastIndexOf("."))
  const isPptx = ext === ".pptx" || ext === ".ppt"
  const isPdf = ext === ".pdf"

  // PDF state
  const [numPages, setNumPages] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [scale, setScale] = useState(1.0)
  const [pageInput, setPageInput] = useState("1")

  const scrollRef = useRef<HTMLDivElement>(null)
  const pageRefs = useRef<Array<HTMLDivElement | null>>([])

  // Escape key & scroll lock
  const handleEscape = useCallback(
    (e: KeyboardEvent) => { if (e.key === "Escape") onClose() },
    [onClose]
  )
  useEffect(() => {
    document.addEventListener("keydown", handleEscape)
    document.body.style.overflow = "hidden"
    return () => {
      document.removeEventListener("keydown", handleEscape)
      document.body.style.overflow = ""
    }
  }, [handleEscape])

  // Ctrl/Cmd + scroll → zoom
  useEffect(() => {
    const el = scrollRef.current
    if (!el || !isPdf) return
    const onWheel = (e: WheelEvent) => {
      if (!e.ctrlKey && !e.metaKey) return
      e.preventDefault()
      setScale(s =>
        Math.min(MAX_SCALE, Math.max(MIN_SCALE,
          parseFloat((s + (e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP)).toFixed(1))
        ))
      )
    }
    el.addEventListener("wheel", onWheel, { passive: false })
    return () => el.removeEventListener("wheel", onWheel)
  }, [isPdf])

  // IntersectionObserver — track which page is centred in the viewport
  useEffect(() => {
    const container = scrollRef.current
    if (!container || !numPages) return
    const obs = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const pg = Number(entry.target.getAttribute("data-page"))
            if (pg) { setCurrentPage(pg); setPageInput(String(pg)) }
          }
        }
      },
      { root: container, threshold: 0.4 }
    )
    pageRefs.current.forEach(el => { if (el) obs.observe(el) })
    return () => obs.disconnect()
  }, [numPages])

  // Stable callbacks passed into the dynamically-loaded PdfViewer
  const handlePdfLoad = useCallback((n: number) => {
    setNumPages(n)
    pageRefs.current = new Array(n).fill(null)
  }, [])

  const setPageRef = useCallback((index: number, el: HTMLDivElement | null) => {
    pageRefs.current[index] = el
  }, [])

  const scrollToPage = (pg: number) => {
    const target = Math.max(1, Math.min(pg, numPages || 1))
    pageRefs.current[target - 1]?.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  const zoomBy = (delta: number) =>
    setScale(s => Math.min(MAX_SCALE, Math.max(MIN_SCALE, parseFloat((s + delta).toFixed(1)))))

  const Icon = variant === "pyq" ? FileQuestion : FileText
  const iconColor = variant === "pyq" ? "text-amber-500" : "text-primary"

  return (
    /* Dimmed backdrop — click outside closes */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 backdrop-blur-sm"
      onClick={onClose}
    >
      {/* Modal panel */}
      <div
        className="relative flex flex-col w-[90vw] max-w-5xl h-[92vh] rounded-xl bg-background shadow-2xl border overflow-hidden"
        onClick={e => e.stopPropagation()}
      >

        {/* ── Toolbar ──────────────────────────────────────────────── */}
        <div className="flex items-center gap-2 border-b bg-card px-4 py-2 shrink-0 flex-wrap">

          {/* Left: file icon + name + badge */}
          <div className="flex items-center gap-2 min-w-0 flex-1">
            <Icon className={`h-4 w-4 shrink-0 ${iconColor}`} />
            <span className="text-sm font-medium truncate max-w-[220px]">{filename}</span>
            {badgeText && (
              <Badge variant="secondary" className="shrink-0 text-xs">{badgeText}</Badge>
            )}
          </div>

          {/* Centre: page nav + zoom (only for PDFs once loaded) */}
          {isPdf && numPages > 0 && (
            <div className="flex items-center gap-0.5 shrink-0">
              {/* Prev page */}
              <Button
                variant="ghost" size="icon" className="h-8 w-8"
                onClick={() => scrollToPage(currentPage - 1)}
                disabled={currentPage <= 1}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>

              {/* Page input / total */}
              <div className="flex items-center gap-1 px-1">
                <Input
                  className="h-7 w-12 text-center text-xs p-1"
                  value={pageInput}
                  onChange={e => {
                    setPageInput(e.target.value)
                    const pg = parseInt(e.target.value, 10)
                    if (!isNaN(pg) && pg >= 1 && pg <= numPages) scrollToPage(pg)
                  }}
                  onKeyDown={e => {
                    if (e.key === "Enter") {
                      const pg = parseInt(pageInput, 10)
                      if (!isNaN(pg)) scrollToPage(pg)
                    }
                  }}
                />
                <span className="text-xs text-muted-foreground whitespace-nowrap">/ {numPages}</span>
              </div>

              {/* Next page */}
              <Button
                variant="ghost" size="icon" className="h-8 w-8"
                onClick={() => scrollToPage(currentPage + 1)}
                disabled={currentPage >= numPages}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>

              {/* Divider */}
              <div className="w-px h-5 bg-border mx-1.5" />

              {/* Zoom out */}
              <Button
                variant="ghost" size="icon" className="h-8 w-8"
                onClick={() => zoomBy(-ZOOM_STEP)}
                disabled={scale <= MIN_SCALE}
              >
                <Minus className="h-4 w-4" />
              </Button>

              {/* Zoom % — click to reset */}
              <span
                className="w-12 text-center text-xs font-mono text-muted-foreground cursor-pointer hover:text-foreground hover:bg-accent rounded px-1 py-0.5 transition-colors select-none"
                onClick={() => setScale(1.0)}
                title="Reset zoom"
              >
                {Math.round(scale * 100)}%
              </span>

              {/* Zoom in */}
              <Button
                variant="ghost" size="icon" className="h-8 w-8"
                onClick={() => zoomBy(ZOOM_STEP)}
                disabled={scale >= MAX_SCALE}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
          )}

          {/* Right: open in new tab + close */}
          <div className="flex items-center gap-1.5 shrink-0">
            <Button
              variant="outline" size="sm"
              className="h-8 gap-1.5 text-xs"
              onClick={() => window.open(fileUrl, "_blank")}
            >
              <ExternalLink className="h-3.5 w-3.5" />
              New tab
            </Button>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* ── Document area ─────────────────────────────────────────── */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-auto bg-neutral-200 dark:bg-neutral-900"
        >
          {isPptx ? (
            /* PPTX: preview not possible */
            <div className="flex flex-col items-center justify-center h-full gap-6 p-8 text-center">
              <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-muted">
                <FileText className="h-10 w-10 text-muted-foreground" />
              </div>
              <div className="max-w-xs">
                <h3 className="text-base font-semibold">Preview Not Available</h3>
                <p className="mt-2 text-sm text-muted-foreground">
                  PowerPoint files cannot be previewed in the browser.
                  Download and open with Microsoft Office or a compatible app.
                </p>
              </div>
              <Button variant="outline" onClick={() => window.open(fileUrl, "_blank")}>
                <ExternalLink className="mr-2 h-4 w-4" />
                Open / Download File
              </Button>
            </div>

          ) : isPdf ? (
            /* PDF: custom viewer (client-only via dynamic import) */
            <PdfViewer
              fileUrl={fileUrl}
              scale={scale}
              numPages={numPages}
              onLoadSuccess={handlePdfLoad}
              setPageRef={setPageRef}
            />

          ) : (
            /* Generic fallback (non-PDF, non-PPTX) */
            <iframe
              src={`${fileUrl}#toolbar=1`}
              className="h-full w-full border-0"
              title={filename}
            />
          )}
        </div>

        {/* ── Hint bar (PDF only) ───────────────────────────────────── */}
        {isPdf && (
          <div className="border-t bg-card px-4 py-1 shrink-0 text-center">
            <p className="text-xs text-muted-foreground">
              Ctrl + scroll to zoom · Click outside or press Esc to close
            </p>
          </div>
        )}

      </div>
    </div>
  )
}


