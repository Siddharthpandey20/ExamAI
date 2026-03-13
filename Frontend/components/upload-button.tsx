"use client"

import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Spinner } from "@/components/ui/spinner"
import { uploadStudyMaterial, uploadPYQ, trackJob } from "@/lib/api"
import { Upload, FileText, FileQuestion, ChevronDown } from "lucide-react"
import { toast } from "sonner"

interface UploadButtonProps {
  subject: string
  onUploadComplete?: () => void
}

export function UploadButton({ subject, onUploadComplete }: UploadButtonProps) {
  const [uploading, setUploading] = useState(false)
  const studyMaterialRef = useRef<HTMLInputElement>(null)
  const pyqRef = useRef<HTMLInputElement>(null)

  const handleStudyMaterialUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file type
    const validTypes = [".pdf", ".pptx", ".ppt"]
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."))
    if (!validTypes.includes(ext)) {
      toast.error("Invalid file type. Please upload PDF, PPTX, or PPT files.")
      return
    }

    try {
      setUploading(true)
      const response = await uploadStudyMaterial(file, subject)
      toast.success(`Uploaded ${file.name}. Processing started.`)

      // Track job progress
      const cleanup = trackJob(
        response.job_id,
        (data) => {
          // Update progress toast
          if (data.current_phase) {
            toast.info(`Processing ${file.name}: ${data.current_phase} (${data.overall_progress_pct}%)`, {
              id: `job-${response.job_id}`,
            })
          }
        },
        (data) => {
          if (data.status === "completed") {
            toast.success(`${file.name} processed successfully!`, {
              id: `job-${response.job_id}`,
            })
            onUploadComplete?.()
          } else if (data.status === "failed") {
            toast.error(`Processing ${file.name} failed: ${data.error || "Unknown error"}`, {
              id: `job-${response.job_id}`,
            })
          }
        },
        () => {
          toast.error(`Lost connection while processing ${file.name}`, {
            id: `job-${response.job_id}`,
          })
        }
      )

      // Cleanup will be called when component unmounts
      return cleanup
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setUploading(false)
      // Reset input
      if (studyMaterialRef.current) {
        studyMaterialRef.current.value = ""
      }
    }
  }

  const handlePYQUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Validate file type
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      toast.error("Invalid file type. PYQ must be a PDF file.")
      return
    }

    try {
      setUploading(true)
      const response = await uploadPYQ(file, subject)
      toast.success(`Uploaded ${file.name}. Processing started.`)

      // Track job progress
      const cleanup = trackJob(
        response.job_id,
        (data) => {
          if (data.current_phase) {
            toast.info(`Processing ${file.name}: ${data.current_phase} (${data.overall_progress_pct}%)`, {
              id: `job-${response.job_id}`,
            })
          }
        },
        (data) => {
          if (data.status === "completed") {
            toast.success(`${file.name} processed successfully!`, {
              id: `job-${response.job_id}`,
            })
            onUploadComplete?.()
          } else if (data.status === "failed") {
            toast.error(`Processing ${file.name} failed: ${data.error || "Unknown error"}`, {
              id: `job-${response.job_id}`,
            })
          }
        },
        () => {
          toast.error(`Lost connection while processing ${file.name}`, {
            id: `job-${response.job_id}`,
          })
        }
      )

      return cleanup
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setUploading(false)
      if (pyqRef.current) {
        pyqRef.current.value = ""
      }
    }
  }

  return (
    <>
      <input
        ref={studyMaterialRef}
        type="file"
        accept=".pdf,.pptx,.ppt"
        onChange={handleStudyMaterialUpload}
        className="hidden"
      />
      <input
        ref={pyqRef}
        type="file"
        accept=".pdf"
        onChange={handlePYQUpload}
        className="hidden"
      />

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button disabled={uploading}>
            {uploading ? (
              <Spinner className="mr-2 h-4 w-4" />
            ) : (
              <Upload className="mr-2 h-4 w-4" />
            )}
            Upload
            <ChevronDown className="ml-2 h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => studyMaterialRef.current?.click()}>
            <FileText className="mr-2 h-4 w-4" />
            Study Material
            <span className="ml-auto text-xs text-muted-foreground">PDF, PPTX</span>
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => pyqRef.current?.click()}>
            <FileQuestion className="mr-2 h-4 w-4" />
            Past Year Questions
            <span className="ml-auto text-xs text-muted-foreground">PDF</span>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  )
}
