import { useEffect } from 'react'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useParseResults } from '@/hooks/useParseResults'
import type { ParseResultListItem } from '@/types/parsing'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'

interface ParseResultViewerProps {
  documentId: string
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'completed':
      return <Badge variant="success">Completed</Badge>
    case 'pending':
      return <Badge variant="warning">Processing...</Badge>
    case 'failed':
      return <Badge variant="destructive">Failed</Badge>
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}

function DiagnosticsView({ diagnostics }: { diagnostics: Record<string, unknown> | null }) {
  if (!diagnostics) return <p className="text-sm text-muted-foreground">No diagnostics available</p>

  return (
    <div className="space-y-2">
      {Object.entries(diagnostics).map(([key, value]) => (
        <div key={key} className="flex justify-between items-center py-1 border-b border-muted last:border-0">
          <span className="text-sm font-medium">{key.replace(/_/g, ' ')}</span>
          <span className="text-sm text-muted-foreground font-mono">
            {typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)}
          </span>
        </div>
      ))}
    </div>
  )
}

export function ParseResultViewer({ documentId }: ParseResultViewerProps) {
  const {
    parseResults,
    selectedResult,
    isLoading,
    isLoadingResult,
    error,
    selectParseResult,
  } = useParseResults(documentId)

  // Auto-select first result
  useEffect(() => {
    if (parseResults.length > 0 && !selectedResult) {
      const first = parseResults[0]
      if (first.status === 'completed') {
        selectParseResult(first.id)
      }
    }
  }, [parseResults, selectedResult, selectParseResult])

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="space-y-4">
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card className="p-6">
        <p className="text-sm text-destructive">{error}</p>
      </Card>
    )
  }

  if (parseResults.length === 0) {
    return null
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString()
  }

  const formatLabel = (item: ParseResultListItem) => {
    return `${item.parserType} (${item.fidelity}) - ${formatDate(item.createdAt)}`
  }

  return (
    <Card className="p-6">
      <div className="space-y-4">
        {/* Header with selector */}
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium">Parse Results</h3>
          {parseResults.length > 1 && (
            <Select
              value={selectedResult?.id || ''}
              onValueChange={selectParseResult}
            >
              <SelectTrigger className="w-[320px]">
                <SelectValue placeholder="Select parse result" />
              </SelectTrigger>
              <SelectContent>
                {parseResults.map((r) => (
                  <SelectItem key={r.id} value={r.id} disabled={r.status !== 'completed'}>
                    <div className="flex items-center gap-2">
                      <StatusBadge status={r.status} />
                      <span className="text-sm">{formatLabel(r)}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        {/* Pending state */}
        {parseResults.some((r) => r.status === 'pending') && !selectedResult && (
          <div className="flex items-center gap-3 py-8 justify-center">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            <span className="text-sm text-muted-foreground">Parsing in progress...</span>
          </div>
        )}

        {/* Failed state */}
        {parseResults.every((r) => r.status === 'failed') && (
          <div className="text-center py-8">
            <p className="text-sm text-destructive">
              Parse failed: {parseResults[0]?.statusMessage || 'Unknown error'}
            </p>
          </div>
        )}

        {/* Loading result detail */}
        {isLoadingResult && (
          <div className="space-y-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        )}

        {/* Result tabs */}
        {selectedResult && !isLoadingResult && (
          <Tabs defaultValue="text">
            <TabsList>
              <TabsTrigger value="text">Text</TabsTrigger>
              {selectedResult.markdown && (
                <TabsTrigger value="markdown">Markdown</TabsTrigger>
              )}
              {selectedResult.documentStructure && (
                <TabsTrigger value="structure">Structure</TabsTrigger>
              )}
              <TabsTrigger value="diagnostics">Diagnostics</TabsTrigger>
              <TabsTrigger value="config">Config</TabsTrigger>
            </TabsList>

            <TabsContent value="text" className="mt-4">
              <div className="whitespace-pre-wrap font-mono text-sm leading-relaxed bg-muted/30 p-4 rounded-lg max-h-[500px] overflow-y-auto">
                {selectedResult.rawText || 'No text content'}
              </div>
            </TabsContent>

            {selectedResult.markdown && (
              <TabsContent value="markdown" className="mt-4">
                <div className="prose prose-sm dark:prose-invert max-w-none bg-muted/30 p-4 rounded-lg max-h-[500px] overflow-y-auto">
                  <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                    {selectedResult.markdown}
                  </Markdown>
                </div>
              </TabsContent>
            )}

            {selectedResult.documentStructure && (
              <TabsContent value="structure" className="mt-4">
                <div className="space-y-3 max-h-[500px] overflow-y-auto">
                  {(() => {
                    const structure = selectedResult.documentStructure as Record<string, unknown> | null
                    const items = (structure?.items ?? []) as Array<{
                      type?: string; page?: number; value?: string; md?: string;
                      bbox?: { x: number; y: number; w: number; h: number };
                    }>
                    if (items.length === 0) {
                      return (
                        <pre className="font-mono text-sm bg-muted/30 p-4 rounded-lg overflow-x-auto">
                          {JSON.stringify(selectedResult.documentStructure, null, 2)}
                        </pre>
                      )
                    }
                    return items.map((item, i) => (
                      <div key={i} className="border rounded-lg p-3 space-y-1">
                        <div className="flex items-center gap-2">
                          <Badge variant="secondary" className="text-xs">
                            {item.type || 'unknown'}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            Page {item.page}
                          </span>
                          {item.bbox && (
                            <span className="text-xs text-muted-foreground font-mono">
                              ({item.bbox.x}, {item.bbox.y}) {item.bbox.w}x{item.bbox.h}
                            </span>
                          )}
                        </div>
                        {item.md ? (
                          <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
                            <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                              {item.md}
                            </Markdown>
                          </div>
                        ) : item.value ? (
                          <p className="text-sm text-muted-foreground">{item.value}</p>
                        ) : null}
                      </div>
                    ))
                  })()}
                </div>
              </TabsContent>
            )}

            <TabsContent value="diagnostics" className="mt-4">
              <DiagnosticsView diagnostics={selectedResult.diagnostics} />
            </TabsContent>

            <TabsContent value="config" className="mt-4">
              <pre className="font-mono text-sm bg-muted/30 p-4 rounded-lg overflow-x-auto">
                {JSON.stringify(selectedResult.parserConfig, null, 2) || 'No config'}
              </pre>
              {selectedResult.metadata && (
                <>
                  <h4 className="text-sm font-medium mt-4 mb-2">Metadata</h4>
                  <pre className="font-mono text-sm bg-muted/30 p-4 rounded-lg overflow-x-auto">
                    {JSON.stringify(selectedResult.metadata, null, 2)}
                  </pre>
                </>
              )}
            </TabsContent>
          </Tabs>
        )}
      </div>
    </Card>
  )
}
