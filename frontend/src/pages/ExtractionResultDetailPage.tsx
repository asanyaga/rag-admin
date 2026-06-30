import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useExtractionResultDetail } from '@/hooks/useExtractionResultDetail'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
import { useProject } from '@/contexts/ProjectContext'
import { ExtractionResultViewer } from '@/components/extraction/ExtractionResultViewer'
import { DocumentPdfViewer } from '@/components/parse-runs/DocumentPdfViewer'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { getParsedDocument } from '@/api/parseRuns'
import type { Block } from '@/types/cdm'
import { formatDistanceToNow } from 'date-fns'

const CITATION_COLOR = 'hsl(38 92% 50%)'

function hasCitationBlocks(citations: Record<string, unknown>[] | null): boolean {
  if (!citations || citations.length === 0) return false
  return citations.some((c) => typeof c.blockId === 'string' && c.blockId.length > 0)
}

export default function ExtractionResultDetailPage(): JSX.Element {
  const { resultId } = useParams<{ resultId: string }>()
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const projectId = currentProject?.id ?? null

  const { result, isLoading, error } = useExtractionResultDetail(resultId ?? null)
  const { schemas } = useExtractionSchemas(projectId)

  const [parseBlocks, setParseBlocks] = useState<Block[]>([])
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null)
  const pdfWrapperRef = useRef<HTMLDivElement>(null)

  const schemaName = schemas.find((s) => s.id === result?.extractionSchemaId)?.name

  useEffect(() => {
    if (!result?.sourceParseRunId) {
      setParseBlocks([])
      return
    }
    getParsedDocument(result.sourceParseRunId)
      .then((doc) => setParseBlocks(doc.content?.blocks ?? []))
      .catch(() => setParseBlocks([]))
  }, [result?.sourceParseRunId])

  const blockColors = useMemo<Map<string, string>>(() => {
    const citations = result?.citations ?? null
    if (!hasCitationBlocks(citations)) return new Map()
    const map = new Map<string, string>()
    for (const c of citations!) {
      const blockId = c.blockId as string | undefined
      if (blockId) map.set(blockId, CITATION_COLOR)
    }
    return map
  }, [result?.citations])

  const handlePageSelect = useCallback((pageIndex: number) => {
    const el = pdfWrapperRef.current?.querySelector(`[data-page-index="${pageIndex}"]`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  if (isLoading) {
    return (
      <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
        <div className="px-4 py-2 border-b shrink-0">
          <Skeleton className="h-8 w-48" />
        </div>
        <div className="p-6 space-y-3 flex-1">
          <Skeleton className="h-6 w-64" />
          <Skeleton className="h-full w-full" />
        </div>
      </div>
    )
  }

  if (error || !result) {
    return (
      <div className="-m-6 p-6">
        <Alert variant="destructive">
          <AlertDescription>{error ?? 'Result not found.'}</AlertDescription>
        </Alert>
      </div>
    )
  }

  const hasPdf = !!result.sourceParseRunId
  const blockLevel = hasPdf && hasCitationBlocks(result.citations)

  const statusVariant =
    result.status === 'completed'
      ? 'default'
      : result.status === 'pending'
        ? 'secondary'
        : 'destructive'

  return (
    <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <div className="px-4 py-2 border-b shrink-0 flex items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={() =>
            navigate(result.documentId ? `/extract?documentId=${result.documentId}` : '/extract')
          }
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back
        </Button>

        <div className="flex items-center gap-2 flex-1 min-w-0">
          {schemaName && (
            <span className="text-sm font-medium truncate max-w-xs">{schemaName}</span>
          )}
          <Badge variant={statusVariant} className="text-xs shrink-0">
            {result.status === 'pending' && (
              <Loader2 className="h-2.5 w-2.5 mr-1 animate-spin" />
            )}
            {result.status}
          </Badge>
          <Badge variant="outline" className="text-xs shrink-0">
            {result.extractionMethod}
          </Badge>
          <span className="text-xs text-muted-foreground shrink-0">
            {formatDistanceToNow(new Date(result.createdAt), { addSuffix: true })}
          </span>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 min-h-0">
        {/* PDF panel — only when sourceParseRunId is set */}
        {hasPdf && (
          <div
            ref={pdfWrapperRef}
            className="flex-1 min-w-0 border-r overflow-hidden"
          >
            <DocumentPdfViewer
              documentId={result.documentId}
              blocks={blockLevel ? parseBlocks : []}
              selectedBlockId={selectedBlockId}
              onBlockSelect={setSelectedBlockId}
              blockColors={blockLevel ? blockColors : undefined}
            />
          </div>
        )}

        {/* Result viewer */}
        <div
          className={
            hasPdf ? 'w-[480px] shrink-0 overflow-y-auto' : 'flex-1 overflow-y-auto'
          }
        >
          <ExtractionResultViewer
            result={result}
            schemaName={schemaName}
            selectedBlockId={selectedBlockId}
            onBlockSelect={setSelectedBlockId}
            onPageSelect={hasPdf ? handlePageSelect : undefined}
          />
        </div>
      </div>
    </div>
  )
}
