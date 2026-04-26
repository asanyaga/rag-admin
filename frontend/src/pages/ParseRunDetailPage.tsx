import { useState, useCallback, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { ChevronLeft } from 'lucide-react'
import { RunHeader } from '@/components/parse-runs/RunHeader'
import { RawPayloadViewer } from '@/components/parse-runs/RawPayloadViewer'
import { ParsedDocumentPane } from '@/components/parse-runs/ParsedDocumentPane'
import { ReParseDialog } from '@/components/documents/ReParseDialog'
import { useParseRunDetail } from '@/hooks/useParseRunDetail'
import { useParseRunRawPayload } from '@/hooks/useParseRunRawPayload'
import { useParseResults } from '@/hooks/useParseResults'
import * as parseRunsApi from '@/api/parseRuns'
import type { ParsedDocumentDetail } from '@/types/cdm'
import type { ParseConfig } from '@/types/parsing'

export function ParseRunDetailPage() {
  const { documentId, runId } = useParams<{
    documentId: string
    runId: string
  }>()
  const navigate = useNavigate()
  const [reparseOpen, setReparseOpen] = useState(false)

  const { run, isLoading: runLoading, error: runError } = useParseRunDetail(
    runId ?? null
  )
  const {
    rawPayload,
    isLoading: rawLoading,
    error: rawError,
  } = useParseRunRawPayload(runId ?? null)

  const [parsedDoc, setParsedDoc] = useState<ParsedDocumentDetail | undefined>(
    undefined
  )
  const [parsedLoading, setParsedLoading] = useState(false)
  const [parsedError, setParsedError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    if (!runId || !run) {
      setParsedDoc(undefined)
      return
    }
    if (
      run.status === 'failed' ||
      run.status === 'pending' ||
      run.status === 'running'
    ) {
      setParsedDoc(undefined)
      return
    }
    setParsedLoading(true)
    setParsedError(null)
    parseRunsApi
      .getParsedDocument(runId)
      .then((d) => {
        if (!cancelled) setParsedDoc(d)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setParsedError(
          err instanceof Error ? err.message : 'Failed to fetch parsed document'
        )
        setParsedDoc(undefined)
      })
      .finally(() => {
        if (!cancelled) setParsedLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [runId, run])

  const { reparseDocument } = useParseResults(documentId ?? null)
  const handleReparse = useCallback(
    async (parserType: string, config?: ParseConfig) => {
      if (!documentId) return
      await reparseDocument(parserType, config)
      // The new CDM ParseRun is created asynchronously by a background task,
      // so we route the user back to the document where the timeline will
      // surface the pending run as it transitions through statuses.
      navigate('/documents')
    },
    [documentId, navigate, reparseDocument]
  )

  if (runLoading) return <div className="p-6">Loading run…</div>
  if (runError) return <div className="p-6 text-destructive">{runError}</div>
  if (!run) return <div className="p-6">Run not found.</div>

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      <div className="px-4 py-2 border-b">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/documents">
            <ChevronLeft className="h-4 w-4 mr-1" /> Back to documents
          </Link>
        </Button>
      </div>

      <RunHeader run={run} onReparse={() => setReparseOpen(true)} />

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 overflow-hidden">
        <div className="border-r overflow-hidden flex flex-col">
          <RawPayloadViewer
            payload={rawPayload}
            isLoading={rawLoading}
            error={rawError}
          />
        </div>
        <div className="overflow-auto">
          <ParsedDocumentPane
            parsedDocument={parsedDoc}
            isLoading={parsedLoading}
            error={parsedError}
          />
        </div>
      </div>

      <ReParseDialog
        open={reparseOpen}
        onOpenChange={setReparseOpen}
        onReparse={handleReparse}
      />
    </div>
  )
}
