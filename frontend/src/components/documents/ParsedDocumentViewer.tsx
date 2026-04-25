import { useMemo, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useParseRuns } from '@/hooks/useParseRuns'
import type { Block, ParseRunListItem, ParseRunStatus } from '@/types/cdm'

interface ParsedDocumentViewerProps {
  documentId: string
}

function StatusBadge({ status }: { status: ParseRunStatus }) {
  switch (status) {
    case 'succeeded':
      return <Badge variant="success">Succeeded</Badge>
    case 'partial':
      return <Badge variant="warning">Partial</Badge>
    case 'pending':
    case 'running':
      return <Badge variant="warning">{status === 'pending' ? 'Pending' : 'Running'}</Badge>
    case 'failed':
      return <Badge variant="destructive">Failed</Badge>
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}

function formatDuration(ms: number | null): string | null {
  if (ms === null) return null
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatRelative(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function RunMetricsStrip({ run }: { run: ParseRunListItem }) {
  const duration = formatDuration(run.durationMs)
  const tokens =
    run.inputTokens !== null || run.outputTokens !== null
      ? `${run.inputTokens ?? 0} in / ${run.outputTokens ?? 0} out`
      : null
  const costEntries = Object.entries(run.cost)

  return (
    <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
      <StatusBadge status={run.status} />
      {duration && (
        <span>
          <span className="font-medium text-foreground">{duration}</span> elapsed
        </span>
      )}
      {tokens && (
        <span>
          <span className="font-medium text-foreground">{tokens}</span> tokens
        </span>
      )}
      {costEntries.length > 0 && (
        <span>
          {costEntries.map(([k, v]) => (
            <span key={k} className="mr-2">
              <span className="font-medium text-foreground">{String(v)}</span> {k}
            </span>
          ))}
        </span>
      )}
      {run.warnings.length > 0 && (
        <Popover>
          <PopoverTrigger asChild>
            <button className="underline decoration-dotted">
              {run.warnings.length} warning{run.warnings.length === 1 ? '' : 's'}
            </button>
          </PopoverTrigger>
          <PopoverContent className="text-xs space-y-1 max-w-sm">
            {run.warnings.map((w, i) => (
              <div key={i}>{w}</div>
            ))}
          </PopoverContent>
        </Popover>
      )}
      {run.failedPages.length > 0 && (
        <Badge variant="destructive" className="text-xs">
          failed: {run.failedPages.map((p) => `p${p}`).join(', ')}
        </Badge>
      )}
    </div>
  )
}

function PageBlockList({ blocks }: { blocks: Block[] }) {
  if (blocks.length === 0) {
    return <p className="text-xs text-muted-foreground">No blocks on this page.</p>
  }
  return (
    <div className="space-y-2">
      {blocks.map((b) => {
        const preview = (b.text ?? b.markdown ?? '').slice(0, 140)
        const confidence = b.quality?.confidence
        return (
          <Collapsible key={b.id}>
            <CollapsibleTrigger asChild>
              <button className="w-full text-left border rounded-md px-2 py-1 hover:bg-muted/50">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-xs">
                    {b.role}
                  </Badge>
                  {typeof confidence === 'number' && (
                    <Badge variant="outline" className="text-xs">
                      {confidence.toFixed(2)}
                    </Badge>
                  )}
                  <span className="text-xs text-muted-foreground truncate flex-1">
                    {preview || <em>empty</em>}
                  </span>
                </div>
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent className="border border-t-0 rounded-b-md px-3 py-2 space-y-2 -mt-px">
              {b.markdown ? (
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                    {b.markdown}
                  </Markdown>
                </div>
              ) : b.text ? (
                <pre className="whitespace-pre-wrap font-mono text-xs">{b.text}</pre>
              ) : (
                <p className="text-xs text-muted-foreground">No text/markdown.</p>
              )}
              <div className="text-xs text-muted-foreground space-y-0.5">
                {b.native_type && <div>native_type: {b.native_type}</div>}
                {b.bbox && (
                  <div>
                    bbox: ({b.bbox.x0.toFixed(3)}, {b.bbox.y0.toFixed(3)}) →
                    ({b.bbox.x1.toFixed(3)}, {b.bbox.y1.toFixed(3)})
                  </div>
                )}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )
      })}
    </div>
  )
}

function MetricsTab({ run }: { run: ParseRunListItem }) {
  const rows: Array<[string, unknown]> = [
    ['Status', run.status],
    ['Parser', run.parser],
    ['Parser version', run.parserVersion ?? '—'],
    ['Representation', run.representationKind],
    ['Started at', formatRelative(run.startedAt)],
    ['Finished at', run.finishedAt ? formatRelative(run.finishedAt) : '—'],
    ['Duration', formatDuration(run.durationMs) ?? '—'],
    ['Input tokens', run.inputTokens ?? '—'],
    ['Output tokens', run.outputTokens ?? '—'],
    ['Cost', JSON.stringify(run.cost)],
    ['Warnings', run.warnings.length > 0 ? run.warnings.join('; ') : '—'],
    [
      'Failed pages',
      run.failedPages.length > 0 ? run.failedPages.join(', ') : '—',
    ],
    ['Provider refs', JSON.stringify(run.providerRefs)],
    ['Config', JSON.stringify(run.config)],
    ['Error', run.error ?? '—'],
  ]
  return (
    <div className="space-y-1 text-sm">
      {rows.map(([label, value]) => (
        <div
          key={label}
          className="flex justify-between gap-3 py-1 border-b border-muted last:border-0"
        >
          <span className="font-medium">{label}</span>
          <span className="text-muted-foreground font-mono text-xs text-right break-all">
            {String(value)}
          </span>
        </div>
      ))}
    </div>
  )
}

export function ParsedDocumentViewer({
  documentId,
}: ParsedDocumentViewerProps) {
  const {
    parseRuns,
    selectedRun,
    parsedDocument,
    isLoading,
    isLoadingContent,
    error,
    selectRun,
  } = useParseRuns(documentId)

  const blocksByPage = useMemo<Map<number, Block[]>>(() => {
    const map = new Map<number, Block[]>()
    const blocks = parsedDocument?.content?.blocks ?? []
    for (const b of blocks) {
      const arr = map.get(b.page_index) ?? []
      arr.push(b)
      map.set(b.page_index, arr)
    }
    return map
  }, [parsedDocument])

  const [tab, setTab] = useState('markdown')

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

  if (parseRuns.length === 0) return null

  const isPending =
    selectedRun?.status === 'pending' || selectedRun?.status === 'running'
  const isFailed = selectedRun?.status === 'failed'
  const pages = parsedDocument?.content?.pages ?? []

  return (
    <Card className="p-6">
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-lg font-medium">CDM Parse</h3>
          {parseRuns.length > 1 && selectedRun && (
            <Select value={selectedRun.id} onValueChange={selectRun}>
              <SelectTrigger className="w-[360px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {parseRuns.map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    <div className="flex items-center gap-2 text-xs">
                      <StatusBadge status={r.status} />
                      <span>
                        {r.parser} / {r.representationKind} ·{' '}
                        {formatRelative(r.startedAt)}
                      </span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>

        {selectedRun && <RunMetricsStrip run={selectedRun} />}

        {isPending && (
          <div className="flex items-center gap-3 py-8 justify-center">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            <span className="text-sm text-muted-foreground">
              Parse in progress…
            </span>
          </div>
        )}

        {isFailed && selectedRun && (
          <div className="text-sm text-destructive">
            {selectedRun.error || 'Parse failed.'}
          </div>
        )}

        {!isPending && !isFailed && selectedRun && (
          <>
            {isLoadingContent && (
              <div className="space-y-3">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-64 w-full" />
              </div>
            )}
            {parsedDocument && (
              <Tabs value={tab} onValueChange={setTab}>
                <TabsList>
                  <TabsTrigger value="markdown">Markdown</TabsTrigger>
                  <TabsTrigger value="text">Text</TabsTrigger>
                  <TabsTrigger value="pages">
                    Pages ({parsedDocument.pageCount})
                  </TabsTrigger>
                  <TabsTrigger value="metrics">Metrics</TabsTrigger>
                  <TabsTrigger value="raw">Raw JSON</TabsTrigger>
                </TabsList>

                <TabsContent value="markdown" className="mt-4">
                  <div className="prose prose-sm dark:prose-invert max-w-none bg-muted/30 p-4 rounded-lg max-h-[500px] overflow-y-auto">
                    {parsedDocument.fullMarkdown ? (
                      <Markdown
                        remarkPlugins={[remarkGfm]}
                        rehypePlugins={[rehypeRaw]}
                      >
                        {parsedDocument.fullMarkdown}
                      </Markdown>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        No markdown produced.
                      </p>
                    )}
                  </div>
                </TabsContent>

                <TabsContent value="text" className="mt-4">
                  <div className="whitespace-pre-wrap font-mono text-sm leading-relaxed bg-muted/30 p-4 rounded-lg max-h-[500px] overflow-y-auto">
                    {parsedDocument.fullText || 'No text content.'}
                  </div>
                </TabsContent>

                <TabsContent value="pages" className="mt-4">
                  <div className="space-y-3 max-h-[500px] overflow-y-auto">
                    {pages.length === 0 && (
                      <p className="text-sm text-muted-foreground">
                        No pages.
                      </p>
                    )}
                    {pages.map((p) => {
                      const blocks = blocksByPage.get(p.index) ?? []
                      const confidence = p.quality?.confidence
                      return (
                        <Collapsible key={p.index} defaultOpen>
                          <CollapsibleTrigger asChild>
                            <button className="w-full text-left border rounded-md px-3 py-2 hover:bg-muted/50">
                              <div className="flex items-center gap-3 text-sm">
                                <span className="font-medium">
                                  Page {p.index + 1}
                                </span>
                                <span className="text-muted-foreground text-xs">
                                  {blocks.length} block
                                  {blocks.length === 1 ? '' : 's'}
                                </span>
                                {typeof confidence === 'number' && (
                                  <Badge
                                    variant="outline"
                                    className="text-xs ml-auto"
                                  >
                                    confidence {confidence.toFixed(2)}
                                  </Badge>
                                )}
                              </div>
                            </button>
                          </CollapsibleTrigger>
                          <CollapsibleContent className="border border-t-0 rounded-b-md p-3 -mt-px">
                            <PageBlockList blocks={blocks} />
                          </CollapsibleContent>
                        </Collapsible>
                      )
                    })}
                  </div>
                </TabsContent>

                <TabsContent value="metrics" className="mt-4">
                  <MetricsTab run={selectedRun} />
                </TabsContent>

                <TabsContent value="raw" className="mt-4">
                  <pre className="font-mono text-xs bg-muted/30 p-4 rounded-lg overflow-auto max-h-[500px]">
                    {JSON.stringify(parsedDocument.content, null, 2)}
                  </pre>
                </TabsContent>
              </Tabs>
            )}
          </>
        )}
      </div>
    </Card>
  )
}
