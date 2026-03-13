"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Spinner } from "@/components/ui/spinner"
import { AISettings, type AIMode } from "@/components/ai-settings"
import { searchQuery, checkCoverage, getConcepts, toTitleCase } from "@/lib/api"
import type { SearchResult, CoverageResult, Concept, Slide } from "@/lib/types"
import { Search, CheckCircle2, XCircle, AlertCircle, Sparkles, BookOpen, Hash, FileText, Target, ArrowRight } from "lucide-react"
import { toast } from "sonner"
import { SlideCard } from "@/components/slide-card"
import { SlideViewer } from "@/components/slide-viewer"
import { MarkdownRenderer } from "@/components/markdown-renderer"

interface SearchConceptsTabProps {
  subjectName: string
}

export function SearchConceptsTab({ subjectName }: SearchConceptsTabProps) {
  return (
    <Tabs defaultValue="search" className="space-y-6">
      <TabsList className="h-11 p-1">
        <TabsTrigger value="search" className="gap-2 px-4">
          <Sparkles className="h-4 w-4" />
          AI Search
        </TabsTrigger>
        <TabsTrigger value="coverage" className="gap-2 px-4">
          <CheckCircle2 className="h-4 w-4" />
          Coverage Checker
        </TabsTrigger>
        <TabsTrigger value="concepts" className="gap-2 px-4">
          <Hash className="h-4 w-4" />
          Concept Explorer
        </TabsTrigger>
      </TabsList>

      <TabsContent value="search">
        <AISearchPanel subjectName={subjectName} />
      </TabsContent>

      <TabsContent value="coverage">
        <CoveragePanel subjectName={subjectName} />
      </TabsContent>

      <TabsContent value="concepts">
        <ConceptsPanel subjectName={subjectName} />
      </TabsContent>
    </Tabs>
  )
}

function AISearchPanel({ subjectName }: { subjectName: string }) {
  const [query, setQuery] = useState("")
  const [searching, setSearching] = useState(false)
  const [result, setResult] = useState<SearchResult | null>(null)
  const [viewingSlide, setViewingSlide] = useState<Slide | null>(null)
  const [mode, setMode] = useState<AIMode>("fast")
  const [skipCache, setSkipCache] = useState(false)

  const handleSearch = async () => {
    if (!query.trim()) {
      toast.error("Please enter a search query")
      return
    }

    try {
      setSearching(true)
      const data = await searchQuery(query.trim(), subjectName, mode, skipCache)
      setResult({
        ...data,
        slides: data.slides ?? [],
      })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Search failed")
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card className="border-2 border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-lg shadow-primary/25">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>AI-Powered Search</CardTitle>
              <CardDescription>
                Ask questions about your study material and get detailed AI-generated answers
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row">
            <Input
              placeholder="e.g., Explain TCP congestion control mechanisms"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="flex-1 h-11"
            />
            <Button onClick={handleSearch} disabled={searching} className="h-11 px-6">
              {searching ? <Spinner className="h-4 w-4" /> : <Search className="h-4 w-4" />}
              <span className="ml-2">Search</span>
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

      {result && (
        <Card className="overflow-hidden">
          <div className="border-b bg-gradient-to-r from-primary/10 to-transparent px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="bg-primary/10 text-primary">
                  <Sparkles className="mr-1 h-3 w-3" />
                  AI Answer
                </Badge>
                {result.mode && (
                  <Badge variant="outline" className="text-xs">
                    {result.mode === "reasoning" ? "Reasoning Mode" : "Fast Mode"}
                  </Badge>
                )}
              </div>
              {result.model_used && (
                <span className="text-xs text-muted-foreground">
                  Powered by {result.model_used}
                </span>
              )}
            </div>
          </div>
          <CardContent className="pt-6 space-y-6">
            {/* Answer Section */}
            <div className="rounded-xl border bg-muted/30 p-6">
              <MarkdownRenderer content={result.answer} />
            </div>

            {/* Referenced Slides */}
            {result?.slides?.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-muted-foreground" />
                  <h4 className="text-sm font-semibold text-foreground">Referenced Slides</h4>
                  <Badge variant="outline" className="text-xs">
                    {result.slides.length} sources
                  </Badge>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {result.slides?.map((slide) => (
                    <SlideCard
                      key={slide.slide_id}
                      slide={slide}
                      onClick={() => setViewingSlide(slide)}
                    />
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {viewingSlide && (
        <SlideViewer slide={viewingSlide} onClose={() => setViewingSlide(null)} />
      )}
    </div>
  )
}

function CoveragePanel({ subjectName }: { subjectName: string }) {
  const [topic, setTopic] = useState("")
  const [checking, setChecking] = useState(false)
  const [result, setResult] = useState<CoverageResult | null>(null)
  const [viewingSlide, setViewingSlide] = useState<Slide | null>(null)
  const [skipCache, setSkipCache] = useState(false)

  const handleCheck = async () => {
    if (!topic.trim()) {
      toast.error("Please enter a topic")
      return
    }

    try {
      setChecking(true)
      const data = await checkCoverage(topic.trim(), subjectName, skipCache)
      setResult(data)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Check failed")
    } finally {
      setChecking(false)
    }
  }

  const getCoverageStyles = (result: CoverageResult) => {
    // Use covered + confidence together for accurate display
    if (result.covered && result.confidence === "high") {
      return {
        icon: <CheckCircle2 className="h-7 w-7" />,
        bg: "bg-emerald-500/10",
        border: "border-emerald-200",
        text: "text-emerald-600",
        label: "Well Covered",
        description: "This topic is comprehensively covered in your materials"
      }
    }
    if (result.covered && result.confidence === "medium") {
      return {
        icon: <AlertCircle className="h-7 w-7" />,
        bg: "bg-amber-500/10",
        border: "border-amber-200",
        text: "text-amber-600",
        label: "Partially Covered",
        description: "Some aspects of this topic are covered"
      }
    }
    if (!result.covered && result.confidence === "low") {
      return {
        icon: <AlertCircle className="h-7 w-7" />,
        bg: "bg-orange-500/10",
        border: "border-orange-200",
        text: "text-orange-600",
        label: "Weakly Covered",
        description: "Limited coverage — closest related content shown below"
      }
    }
    return {
      icon: <XCircle className="h-7 w-7" />,
      bg: "bg-red-500/10",
      border: "border-red-200",
      text: "text-red-600",
      label: "Not Covered",
      description: "This topic is not covered in your materials"
    }
  }

  const styles = result ? getCoverageStyles(result) : null

  return (
    <div className="space-y-6">
      <Card className="border-2 border-emerald-500/20 bg-gradient-to-br from-emerald-500/5 to-transparent">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500 text-white shadow-lg shadow-emerald-500/25">
              <Target className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>Topic Coverage Checker</CardTitle>
              <CardDescription>
                Verify if specific topics are covered in your study materials
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row">
            <Input
              placeholder="e.g., Selective Repeat ARQ, OSI Model layers"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCheck()}
              className="flex-1 h-11"
            />
            <Button onClick={handleCheck} disabled={checking} className="h-11 px-6 bg-emerald-600 hover:bg-emerald-700">
              {checking ? <Spinner className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
              <span className="ml-2">Check Coverage</span>
            </Button>
          </div>
          <div className="flex items-center gap-4 rounded-lg border bg-muted/30 px-4 py-3">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="coverage-skip-cache"
                checked={skipCache}
                onChange={(e) => setSkipCache(e.target.checked)}
                className="h-4 w-4 rounded border-muted-foreground/25"
              />
              <label htmlFor="coverage-skip-cache" className="text-sm text-muted-foreground cursor-pointer">
                Skip cache (fresh analysis)
              </label>
            </div>
          </div>
        </CardContent>
      </Card>

      {result && styles && (
        <Card className={`overflow-hidden border-2 ${styles.border}`}>
          <div className={`${styles.bg} px-6 py-4`}>
            <div className="flex items-center gap-4">
              <div className={`flex h-14 w-14 items-center justify-center rounded-2xl ${styles.bg} ${styles.text}`}>
                {styles.icon}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className={`text-lg font-semibold ${styles.text}`}>{styles.label}</h3>
                </div>
                <p className="text-sm text-muted-foreground">{styles.description}</p>
              </div>
            </div>
          </div>
          <CardContent className="pt-6 space-y-6">
            <div className="rounded-xl border bg-muted/30 p-6">
              <MarkdownRenderer content={result.answer} />
            </div>

            {result.slides.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <FileText className="h-5 w-5 text-muted-foreground" />
                  <h4 className="text-sm font-semibold text-foreground">Related Slides</h4>
                  <Badge variant="outline" className="text-xs">
                    {result.slides.length} found
                  </Badge>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {result.slides.map((slide) => (
                    <SlideCard
                      key={slide.slide_id}
                      slide={slide}
                      onClick={() => setViewingSlide(slide)}
                    />
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {viewingSlide && (
        <SlideViewer slide={viewingSlide} onClose={() => setViewingSlide(null)} />
      )}
    </div>
  )
}

function ConceptsPanel({ subjectName }: { subjectName: string }) {
  const [concepts, setConcepts] = useState<Concept[]>([])
  const [loading, setLoading] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [viewingSlide, setViewingSlide] = useState<Slide | null>(null)
  const [expandedConcept, setExpandedConcept] = useState<string | null>(null)

  const loadConcepts = async (query?: string) => {
    try {
      setLoading(true)
      const data = await getConcepts(subjectName, { q: query })
      setConcepts(data.concepts)
      setLoaded(true)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load concepts")
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    loadConcepts(searchQuery.trim() || undefined)
  }

  return (
    <div className="space-y-6">
      <Card className="border-2 border-violet-500/20 bg-gradient-to-br from-violet-500/5 to-transparent">
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500 text-white shadow-lg shadow-violet-500/25">
              <Hash className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>Concept Explorer</CardTitle>
              <CardDescription>
                Browse all concepts extracted from your study materials
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Input
              placeholder="Filter concepts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="flex-1 h-11"
            />
            <Button onClick={handleSearch} disabled={loading} className="h-11 px-6 bg-violet-600 hover:bg-violet-700">
              {loading ? <Spinner className="h-4 w-4" /> : loaded ? "Refresh" : "Load Concepts"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {loaded && concepts.length > 0 && (
        <Card>
          <CardHeader className="pb-4">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">All Concepts</CardTitle>
              <Badge variant="secondary">{concepts.length} concepts</Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {concepts.map((concept) => (
                <button
                  key={concept.concept}
                  onClick={() =>
                    setExpandedConcept(
                      expandedConcept === concept.concept ? null : concept.concept
                    )
                  }
                  className={`group inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition-all duration-200 ${
                    expandedConcept === concept.concept
                      ? "border-violet-500 bg-violet-500/10 text-violet-700 shadow-md"
                      : "hover:border-violet-300 hover:bg-violet-500/5 hover:shadow-sm"
                  }`}
                >
                  <span className="font-medium">{concept.concept}</span>
                  <Badge variant="secondary" className={`text-xs transition-colors ${
                    expandedConcept === concept.concept ? "bg-violet-200 text-violet-700" : ""
                  }`}>
                    {concept.frequency}
                  </Badge>
                  {expandedConcept !== concept.concept && (
                    <ArrowRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                  )}
                </button>
              ))}
            </div>

            {expandedConcept && (
              <div className="mt-6 space-y-4 border-t pt-6">
                <div className="flex items-center gap-2">
                  <BookOpen className="h-5 w-5 text-violet-500" />
                  <h4 className="text-sm font-semibold text-foreground">
                    Slides containing &quot;{expandedConcept}&quot;
                  </h4>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {concepts
                    .find((c) => c.concept === expandedConcept)
                    ?.slides.map((slide) => (
                      <div
                        key={slide.slide_id}
                        onClick={() =>
                          setViewingSlide({
                            slide_id: slide.slide_id,
                            page_number: slide.page_number,
                            filename: slide.filename,
                            slide_type: slide.slide_type || "other",
                            chapter: "",
                            concepts: expandedConcept,
                            summary: slide.summary || "",
                            exam_signal: false,
                            importance_score: slide.importance_score || 0,
                            pyq_hit_count: slide.pyq_hit_count || 0,
                          })
                        }
                        className="cursor-pointer rounded-xl border bg-gradient-to-br from-muted/50 to-muted/20 p-4 transition-all duration-200 hover:border-violet-300 hover:shadow-md hover:-translate-y-0.5"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-500/10 text-violet-600">
                              <BookOpen className="h-4 w-4" />
                            </div>
                            <span className="text-sm font-semibold">Page {slide.page_number}</span>
                          </div>
                          {slide.pyq_hit_count && slide.pyq_hit_count > 0 && (
                            <Badge className="bg-amber-500/10 text-amber-600 border-amber-200">
                              {slide.pyq_hit_count} PYQ
                            </Badge>
                          )}
                        </div>
                        {slide.filename && (
                          <p className="mt-2 text-xs text-muted-foreground line-clamp-1">
                            {slide.filename}
                          </p>
                        )}
                      </div>
                    ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {loaded && concepts.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
              <Hash className="h-8 w-8 text-muted-foreground" />
            </div>
            <p className="mt-4 text-lg font-medium text-foreground">No concepts found</p>
            <p className="text-sm text-muted-foreground">Try a different search term or upload more materials</p>
          </CardContent>
        </Card>
      )}

      {viewingSlide && (
        <SlideViewer slide={viewingSlide} onClose={() => setViewingSlide(null)} />
      )}
    </div>
  )
}
