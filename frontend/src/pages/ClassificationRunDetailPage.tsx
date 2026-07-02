import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate, Link, useLocation } from 'react-router-dom'
import { ChevronLeft, RotateCw, Info } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { ClassificationRunStatusBadge } from '@/components/classification/ClassificationRunStatusBadge'
import { ClassificationResultsViewer } from '@/components/classification/ClassificationResultsViewer'
import { ClassificationRunConfigPanel } from '@/components/classification/ClassificationRunConfigPanel'
import { DocumentPdfViewer } from '@/components/parse-runs/DocumentPdfViewer'
import { useClassificationRunDetail, useClassificationRunBlocks } from '@/hooks/useClassificationRuns'
import { getParsedDocument } from '@/api/parseRuns'
import type { Block } from '@/types/cdm'
import { formatDistanceToNow } from 'date-fns'

const LABEL_COLORS = [
  'hsl(221 83% 53%)',
  'hsl(142 71% 45%)',
  'hsl(32 95% 44%)',
  'hsl(346 77% 49%)',
  'hsl(262 80% 58%)',
  'hsl(199 89% 48%)',
  'hsl(25 95% 53%)',
  'hsl(316 70% 50%)',
]

export function ClassificationRunDetailPage() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const documentTitle = (location.state as { documentTitle?: string } | null)?.documentTitle
  const { run, isLoading, error } = useClassificationRunDetail(runId ?? null)
  const { blocks: annotatedBlocks } = useClassificationRunBlocks(
    run?.status === 'completed' ? (runId ?? null) : null,
  )

  const [parseBlocks, setParseBlocks] = useState<Block[]>([])
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null)
  const [selectedPageIndex, setSelectedPageIndex] = useState<number | null>(null)

  const handleBlockSelect = (blockId: string) => {
    setSelectedBlockId(blockId)
    setSelectedPageIndex(null)
  }

  const handlePageSelect = (pageIndex: number) => {
    setSelectedPageIndex(pageIndex)
    setSelectedBlockId(null)
  }

  useEffect(() => {
    if (!run?.parseRunId) return
    getParsedDocument(run.parseRunId)
      .then((doc) => setParseBlocks(doc.content?.blocks ?? []))
      .catch(() => setParseBlocks([]))
  }, [run?.parseRunId])

  const blockColors = useMemo<Map<string, string>>(() => {
    if (!annotatedBlocks.length) return new Map()
    const labelIndex = new Map<string, number>()
    let idx = 0
    const map = new Map<string, string>()
    for (const b of annotatedBlocks) {
      if (!b.label) continue
      if (!labelIndex.has(b.label)) labelIndex.set(b.label, idx++ % LABEL_COLORS.length)
      map.set(b.blockId, LABEL_COLORS[labelIndex.get(b.label)!])
    }
    return map
  }, [annotatedBlocks])

  if (isLoading) {
    return (
      <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
        <div className="px-4 py-2 border-b shrink-0">
          <Skeleton className="h-8 w-40" />
        </div>
        <div className="p-6 space-y-3 flex-1">
          <Skeleton className="h-6 w-64" />
          <Skeleton className="h-full w-full" />
        </div>
      </div>
    )
  }

  if (error || !run) {
    return (
      <div className="-m-6 p-6">
        <Alert variant="destructive">
          <AlertDescription>{error ?? 'Run not found.'}</AlertDescription>
        </Alert>
      </div>
    )
  }

  const handleRerun = () => {
    navigate(`/classify/new?documentId=${run.documentId}`, {
      state: {
        documentTitle,
        defaults: {
          labels: run.labelsRequested,
          classifierType: run.classifierType,
          classifierConfig: run.classifierConfig,
        },
      },
    })
  }

  const modelSummary =
    run.classifierType === 'llm'
      ? `${run.classifierConfig.provider as string} / ${run.classifierConfig.model as string}`
      : run.classifierType

  return (
    <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <div className="px-4 py-2 border-b shrink-0 flex items-center gap-4">
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/classify?documentId=${run.documentId}`}>
            <ChevronLeft className="h-4 w-4 mr-1" />
            Back
          </Link>
        </Button>
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <ClassificationRunStatusBadge status={run.status} />
          {documentTitle && (
            <span className="text-sm font-medium truncate max-w-[200px]">{documentTitle}</span>
          )}
          <span className="text-sm text-muted-foreground truncate">{modelSummary}</span>
          <span className="text-xs text-muted-foreground shrink-0">
            {formatDistanceToNow(new Date(run.createdAt), { addSuffix: true })}
          </span>
          <div className="flex gap-3 text-xs text-muted-foreground ml-auto shrink-0">
            <span>
              <span className="font-medium text-foreground">{run.labelsRequested.length}</span> labels
            </span>
            <span>
              <span className="font-medium text-foreground">{run.regions.length}</span> regions
            </span>
            {run.durationMs !== null && (
              <span>
                <span className="font-medium text-foreground">{(run.durationMs / 1000).toFixed(1)}s</span>
              </span>
            )}
          </div>
        </div>
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" title="Run config">
              <Info className="h-3.5 w-3.5" />
            </Button>
          </PopoverTrigger>
          <PopoverContent align="end" className="w-80 p-4">
            <ClassificationRunConfigPanel run={run} />
          </PopoverContent>
        </Popover>
        <Button variant="outline" size="sm" className="h-7 text-xs shrink-0" onClick={handleRerun}>
          <RotateCw className="h-3.5 w-3.5 mr-1.5" />
          Re-run
        </Button>
      </div>

      {/* Body: PDF viewer | classification results */}
      <div className="flex flex-1 min-h-0">
        <div className="flex-1 min-w-0 border-r overflow-hidden">
          <DocumentPdfViewer
            documentId={run.documentId}
            blocks={parseBlocks}
            selectedBlockId={selectedBlockId}
            onBlockSelect={handleBlockSelect}
            blockColors={blockColors}
            selectedPageIndex={selectedPageIndex}
          />
        </div>
        <div className="w-80 shrink-0 overflow-y-auto p-4">
          {run.status === 'completed' ? (
            <ClassificationResultsViewer
              runId={run.id}
              labelsRequested={run.labelsRequested}
              selectedBlockId={selectedBlockId}
              onBlockSelect={handleBlockSelect}
              onPageSelect={handlePageSelect}
            />
          ) : run.status === 'running' ? (
            <p className="text-sm text-muted-foreground animate-pulse">Classification in progress…</p>
          ) : run.error ? (
            <Alert variant="destructive">
              <AlertDescription>{run.error}</AlertDescription>
            </Alert>
          ) : null}
        </div>
      </div>
    </div>
  )
}
