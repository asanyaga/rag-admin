import { useState, useCallback, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ChevronLeft } from 'lucide-react'
import { RunHeader } from '@/components/parse-runs/RunHeader'
import { RawPayloadViewer } from '@/components/parse-runs/RawPayloadViewer'
import { ParsedDocumentPane } from '@/components/parse-runs/ParsedDocumentPane'
import { DocumentPdfViewer } from '@/components/parse-runs/DocumentPdfViewer'
import { MetricsTab } from '@/components/documents/ParsedDocumentViewer'
import { ReParseDialog } from '@/components/documents/ReParseDialog'
import { ParseRunDeleteDialog } from '@/components/parse-runs/ParseRunDeleteDialog'
import { useParseRunDetail } from '@/hooks/useParseRunDetail'
import { useParseRunRawPayload } from '@/hooks/useParseRunRawPayload'
import * as parseRunsApi from '@/api/parseRuns'
import type { ParsedDocumentDetail } from '@/types/cdm'
import type { ParseConfig } from '@/types/parsing'

export function ParseRunDetailPage() {
  const { documentId, runId } = useParams<{
    documentId?: string
    runId: string
  }>()
  const navigate = useNavigate()
  const [reparseOpen, setReparseOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('pages')

  const { run, isLoading: runLoading, error: runError } = useParseRunDetail(
    runId ?? null,
  )
  const {
    rawPayload,
    isLoading: rawLoading,
    error: rawError,
  } = useParseRunRawPayload(runId ?? null)

  const [parsedDoc, setParsedDoc] = useState<ParsedDocumentDetail | undefined>(
    undefined,
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
          err instanceof Error ? err.message : 'Failed to fetch parsed document',
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

  const handleBlockSelectFromPdf = useCallback((blockId: string) => {
    setSelectedBlockId(blockId)
    setActiveTab('pages')
  }, [])

  const handleReparse = useCallback(
    async (parserType: string, config?: ParseConfig) => {
      if (!documentId) return
      await parseRunsApi.createParseRun(documentId, parserType, config)
      // The new CDM ParseRun is created asynchronously by a background task,
      // so we route the user back to the document where the timeline will
      // surface the pending run as it transitions through statuses.
      navigate('/parse')
    },
    [documentId, navigate],
  )

  if (runLoading) return <div className="p-6">Loading run…</div>
  if (runError) return <div className="p-6 text-destructive">{runError}</div>
  if (!run) return <div className="p-6">Run not found.</div>

  const blocks = parsedDoc?.content?.blocks ?? []

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden">
      <div className="px-4 py-2 border-b shrink-0">
        <Button variant="ghost" size="sm" asChild>
          {documentId ? (
            <Link to={`/parse?documentId=${documentId}`}>
              <ChevronLeft className="h-4 w-4 mr-1" /> Back to documents
            </Link>
          ) : (
            <Link to="/parse-agent">
              <ChevronLeft className="h-4 w-4 mr-1" /> Back to parse agent
            </Link>
          )}
        </Button>
      </div>

      <RunHeader
        run={run}
        canReparse={Boolean(documentId)}
        onReparse={() => setReparseOpen(true)}
        onDelete={() => setDeleteOpen(true)}
      />

      <div
        className="flex-1 grid overflow-hidden"
        style={{ gridTemplateColumns: '55% 45%' }}
      >
        {/* Left: PDF viewer */}
        <div className="border-r overflow-hidden">
          {documentId ? (
            <DocumentPdfViewer
              documentId={documentId}
              blocks={blocks}
              selectedBlockId={selectedBlockId}
              onBlockSelect={handleBlockSelectFromPdf}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-muted-foreground">
              No document ID.
            </div>
          )}
        </div>

        {/* Right: tabs */}
        <div className="overflow-hidden flex flex-col">
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="flex flex-col h-full"
          >
            <TabsList className="shrink-0 mx-3 mt-2 justify-start flex-wrap h-auto gap-1">
              <TabsTrigger value="pages">
                Pages{parsedDoc ? ` (${parsedDoc.pageCount})` : ''}
              </TabsTrigger>
              <TabsTrigger value="markdown">Markdown</TabsTrigger>
              <TabsTrigger value="text">Text</TabsTrigger>
              <TabsTrigger value="json">JSON</TabsTrigger>
              <TabsTrigger value="raw-payload">Raw Payload</TabsTrigger>
              <TabsTrigger value="metrics">Metrics</TabsTrigger>
            </TabsList>

            <div className="flex-1 overflow-auto">
              <TabsContent value="pages" className="mt-0 h-full">
                <ParsedDocumentPane
                  parsedDocument={parsedDoc}
                  isLoading={parsedLoading}
                  error={parsedError}
                  selectedBlockId={selectedBlockId}
                  onBlockSelect={setSelectedBlockId}
                />
              </TabsContent>

              <TabsContent value="markdown" className="mt-0 p-4">
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  {parsedDoc?.fullMarkdown ? (
                    <Markdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeRaw]}
                    >
                      {parsedDoc.fullMarkdown}
                    </Markdown>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      No markdown produced.
                    </p>
                  )}
                </div>
              </TabsContent>

              <TabsContent value="text" className="mt-0 p-4">
                <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed">
                  {parsedDoc?.fullText || 'No text content.'}
                </pre>
              </TabsContent>

              <TabsContent value="json" className="mt-0 p-4">
                <pre className="font-mono text-xs">
                  {parsedDoc
                    ? JSON.stringify(parsedDoc.content, null, 2)
                    : 'No data.'}
                </pre>
              </TabsContent>

              <TabsContent value="raw-payload" className="mt-0 h-full">
                <RawPayloadViewer
                  payload={rawPayload}
                  isLoading={rawLoading}
                  error={rawError}
                />
              </TabsContent>

              <TabsContent value="metrics" className="mt-0 p-4">
                <MetricsTab run={run} />
              </TabsContent>
            </div>
          </Tabs>
        </div>
      </div>

      <ReParseDialog
        open={reparseOpen}
        onOpenChange={setReparseOpen}
        onReparse={handleReparse}
      />
      {runId && (
        <ParseRunDeleteDialog
          open={deleteOpen}
          onOpenChange={setDeleteOpen}
          runId={runId}
          onDeleted={() => navigate('/parse')}
        />
      )}
    </div>
  )
}
