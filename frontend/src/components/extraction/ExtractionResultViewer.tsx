import type { ExtractionResult } from '@/types/extraction'
import { ChunkingSummary } from './ChunkingSummary'
import { FormattedJson } from '@/components/shared/FormattedJson'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { Button } from '@/components/ui/button'
import { ChevronDown, Loader2 } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'

interface ExtractionResultViewerProps {
  result: ExtractionResult | null
  isLoading?: boolean
}

// ── Internal types for casting extractionMetadata and config ─────────────────

interface ExtractionMeta {
  model?: string
  provider?: string
  latency_ms?: number
  usage?: {
    prompt_tokens?: number
    completion_tokens?: number
    total_tokens?: number
  }
  chunkCount?: number
  prompt_messages?: Array<{ role: string; content: string }>
}

interface ExtractionConfig {
  structured_output_mode?: string
  inject_block_ids?: boolean
  chunking?: {
    strategy?: string
    config?: Record<string, unknown>
    citationLevel?: string
  }
}

// ── Helper components ─────────────────────────────────────────────────────────

function StructuredDataDisplay({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data)

  return (
    <div className="space-y-4">
      {entries.map(([key, value]) => {
        if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object') {
          return <ArrayTable key={key} label={key} items={value as Record<string, unknown>[]} />
        }

        if (value !== null && typeof value === 'object' && !Array.isArray(value)) {
          return (
            <Collapsible key={key}>
              <CollapsibleTrigger asChild>
                <Button variant="ghost" className="w-full justify-between px-3 py-2 h-auto">
                  <span className="font-medium text-sm">{formatLabel(key)}</span>
                  <ChevronDown className="h-4 w-4" />
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="pl-4 border-l-2 border-muted ml-3">
                <StructuredDataDisplay data={value as Record<string, unknown>} />
              </CollapsibleContent>
            </Collapsible>
          )
        }

        return (
          <div key={key} className="flex justify-between items-start py-1.5 px-3 rounded hover:bg-muted/50">
            <span className="text-sm text-muted-foreground">{formatLabel(key)}</span>
            <span className="text-sm text-right max-w-[60%]">{formatValue(value)}</span>
          </div>
        )
      })}
    </div>
  )
}

function ArrayTable({ label, items }: { label: string; items: Record<string, unknown>[] }) {
  if (items.length === 0) return null

  const columns = Object.keys(items[0])

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium px-3">{formatLabel(label)}</h4>
      <div className="rounded-md border overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((col) => (
                <TableHead key={col} className="text-xs">
                  {formatLabel(col)}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item, i) => (
              <TableRow key={i}>
                {columns.map((col) => (
                  <TableCell key={col} className="text-sm">
                    {formatValue(item[col])}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

function ConfigRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[12rem_1fr] gap-4 py-0.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span>{value ?? '—'}</span>
    </div>
  )
}

function NotAvailableChunked() {
  return (
    <span className="text-muted-foreground italic text-xs">
      Not available for chunked runs
    </span>
  )
}

function UserMessageDisplay({ content }: { content: string }) {
  const parsed = parseUserContent(content)
  if (!parsed.schema) {
    return (
      <pre className="text-xs font-mono bg-muted p-3 rounded-md border overflow-auto max-h-48 whitespace-pre-wrap">
        {content}
      </pre>
    )
  }
  let schemaJson: unknown
  try {
    schemaJson = JSON.parse(parsed.schema)
  } catch {
    schemaJson = parsed.schema
  }
  return (
    <div className="space-y-3">
      {parsed.instruction && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground mb-1">Instruction</p>
          <pre className="text-xs font-mono bg-muted p-2 rounded border whitespace-pre-wrap">
            {parsed.instruction}
          </pre>
        </div>
      )}
      <div>
        <p className="text-xs font-semibold text-muted-foreground mb-1">Schema</p>
        <FormattedJson value={schemaJson} maxHeight="12rem" />
      </div>
      {parsed.document && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground mb-1">Document</p>
          <pre className="text-xs font-mono bg-muted p-2 rounded border overflow-auto max-h-48 whitespace-pre-wrap">
            {parsed.document}
          </pre>
        </div>
      )}
    </div>
  )
}

// ── Pure helpers ──────────────────────────────────────────────────────────────

function formatLabel(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .replace(/^\w/, (c) => c.toUpperCase())
    .trim()
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

interface ParsedUserContent {
  instruction: string
  schema: string | null
  document: string | null
}

function parseUserContent(content: string): ParsedUserContent {
  const schemaOpen = '<schema>'
  const schemaClose = '</schema>'
  const docOpen = '<document>'
  const docClose = '</document>'
  const s0 = content.indexOf(schemaOpen)
  const s1 = content.indexOf(schemaClose)
  const d0 = content.indexOf(docOpen)
  const d1 = content.indexOf(docClose)
  if (s0 === -1 || d0 === -1) {
    return { instruction: content, schema: null, document: null }
  }
  return {
    instruction: content.slice(0, s0).trim(),
    schema: content.slice(s0 + schemaOpen.length, s1).trim(),
    document: content.slice(d0 + docOpen.length, d1).trim(),
  }
}

// ── Main component ────────────────────────────────────────────────────────────

export function ExtractionResultViewer({
  result,
  isLoading,
}: ExtractionResultViewerProps) {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!result) return null

  const meta = result.extractionMetadata as ExtractionMeta | null
  const cfg = result.config as ExtractionConfig | null
  const chunkingConfig = cfg?.chunking
  const promptMessages = meta?.prompt_messages
  const systemMessage = promptMessages?.[0]
  const userMessage = promptMessages?.[1]

  const hasProviderResponse =
    result.providerResponseRaw !== null &&
    result.providerResponseRaw !== undefined &&
    Object.keys(result.providerResponseRaw).length > 0
  const isRawContent =
    typeof result.providerResponseRaw?.['raw_content'] === 'string'

  const statusColor =
    result.status === 'completed'
      ? 'default'
      : result.status === 'pending'
        ? 'secondary'
        : 'destructive'

  return (
    <div className="space-y-4">
      <ChunkingSummary metadata={result.extractionMetadata} />

      {/* ── Result card ─────────────────────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Extraction Result</CardTitle>
            <div className="flex items-center gap-2">
              <Badge variant={statusColor}>
                {result.status === 'pending' && (
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                )}
                {result.status}
              </Badge>
              <Badge variant="outline">{result.extractionMethod}</Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {result.status === 'pending' && (
            <p className="text-sm text-muted-foreground">Extraction is in progress...</p>
          )}

          {result.status === 'failed' && (
            <div className="space-y-3">
              {result.statusMessage && (
                <p className="text-sm text-destructive">{result.statusMessage}</p>
              )}
              {isRawContent && (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-muted-foreground">LLM Response</p>
                  <pre className="text-xs bg-muted p-3 rounded-md overflow-x-auto whitespace-pre-wrap max-h-64">
                    {result.providerResponseRaw!['raw_content'] as string}
                  </pre>
                </div>
              )}
            </div>
          )}

          {result.status === 'completed' && result.structuredData && (
            <StructuredDataDisplay data={result.structuredData} />
          )}
        </CardContent>
      </Card>

      {/* ── Run Config panel ─────────────────────────────────────────────── */}
      <Collapsible>
        <CollapsibleTrigger asChild>
          <Button variant="outline" size="sm" className="w-full justify-between">
            <span>Run Config</span>
            <ChevronDown className="h-4 w-4" />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <Card className="mt-2">
            <CardContent className="pt-4 space-y-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Model
              </p>
              <div className="space-y-0.5">
                <ConfigRow
                  label="Model"
                  value={meta?.model ?? <NotAvailableChunked />}
                />
                <ConfigRow
                  label="Provider"
                  value={meta?.provider ?? <NotAvailableChunked />}
                />
                <ConfigRow
                  label="Latency"
                  value={
                    meta?.latency_ms !== undefined
                      ? `${meta.latency_ms.toLocaleString()} ms`
                      : <NotAvailableChunked />
                  }
                />
              </div>
              <Separator />
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Tokens
              </p>
              <div className="space-y-0.5">
                <ConfigRow
                  label="Prompt tokens"
                  value={meta?.usage?.prompt_tokens?.toLocaleString() ?? '—'}
                />
                <ConfigRow
                  label="Completion tokens"
                  value={meta?.usage?.completion_tokens?.toLocaleString() ?? '—'}
                />
                <ConfigRow
                  label="Total tokens"
                  value={meta?.usage?.total_tokens?.toLocaleString() ?? '—'}
                />
              </div>
              <Separator />
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Settings
              </p>
              <div className="space-y-0.5">
                <ConfigRow label="Extraction method" value={result.extractionMethod} />
                <ConfigRow
                  label="Structured output mode"
                  value={cfg?.structured_output_mode ?? '—'}
                />
                <ConfigRow
                  label="Inject block IDs"
                  value={
                    typeof cfg?.inject_block_ids === 'boolean'
                      ? cfg.inject_block_ids
                        ? 'Yes'
                        : 'No'
                      : '—'
                  }
                />
                <ConfigRow
                  label="Chunking strategy"
                  value={chunkingConfig?.strategy ?? '—'}
                />
                {chunkingConfig?.strategy && chunkingConfig.strategy !== 'none' && (
                  <ConfigRow
                    label="Max input tokens"
                    value={
                      (chunkingConfig.config?.['maxInputTokens'] as number | undefined)?.toLocaleString() ??
                      '—'
                    }
                  />
                )}
                <ConfigRow
                  label="Citation level"
                  value={chunkingConfig?.citationLevel ?? '—'}
                />
                {meta?.chunkCount !== undefined && (
                  <ConfigRow label="Chunk count" value={String(meta.chunkCount)} />
                )}
              </div>
            </CardContent>
          </Card>
        </CollapsibleContent>
      </Collapsible>

      {/* ── Prompt panel ─────────────────────────────────────────────────── */}
      <Collapsible>
        <CollapsibleTrigger asChild>
          <Button variant="outline" size="sm" className="w-full justify-between">
            <span>Prompt</span>
            <ChevronDown className="h-4 w-4" />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <Card className="mt-2">
            <CardContent className="pt-4">
              {!promptMessages ? (
                <p className="text-sm text-muted-foreground italic">
                  Prompt not available — this run used chunking. Individual chunk prompts
                  are not yet preserved.
                </p>
              ) : (
                <Tabs defaultValue="system">
                  <TabsList>
                    <TabsTrigger value="system">System</TabsTrigger>
                    <TabsTrigger value="user">User</TabsTrigger>
                  </TabsList>
                  <TabsContent value="system" className="mt-3">
                    <pre className="text-xs font-mono bg-muted p-3 rounded-md border overflow-auto max-h-48 whitespace-pre-wrap">
                      {systemMessage?.content ?? '—'}
                    </pre>
                  </TabsContent>
                  <TabsContent value="user" className="mt-3">
                    {userMessage ? (
                      <UserMessageDisplay content={userMessage.content} />
                    ) : (
                      <p className="text-sm text-muted-foreground">—</p>
                    )}
                  </TabsContent>
                </Tabs>
              )}
            </CardContent>
          </Card>
        </CollapsibleContent>
      </Collapsible>

      {/* ── LLM Response panel (hidden for chunked/null) ──────────────────── */}
      {hasProviderResponse && (
        <Collapsible>
          <CollapsibleTrigger asChild>
            <Button variant="outline" size="sm" className="w-full justify-between">
              <span>LLM Response</span>
              <ChevronDown className="h-4 w-4" />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <Card className="mt-2">
              <CardContent className="pt-4">
                {isRawContent ? (
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">Raw (non-JSON) response</p>
                    <pre className="text-xs font-mono bg-muted p-3 rounded-md border overflow-auto max-h-96 whitespace-pre-wrap">
                      {result.providerResponseRaw!['raw_content'] as string}
                    </pre>
                  </div>
                ) : (
                  <FormattedJson value={result.providerResponseRaw} maxHeight="24rem" />
                )}
              </CardContent>
            </Card>
          </CollapsibleContent>
        </Collapsible>
      )}
    </div>
  )
}
