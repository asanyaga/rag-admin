/**
 * QueryTracePanel — collapsible panel showing pipeline step trace.
 */
import { useState } from 'react'
import { QueryTrace, Span } from '@/types/trace'
import { Badge } from '@/components/ui/badge'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { cn } from '@/lib/utils'
import {
  Activity,
  ChevronDown,
  ChevronRight,
  Database,
  FileText,
  Hash,
  Sparkles,
  Search,
  Zap,
  GitMerge,
  AlertCircle,
} from 'lucide-react'

interface QueryTracePanelProps {
  trace: QueryTrace
}

const SPAN_ICONS: Record<string, React.ElementType> = {
  query_input: FileText,
  embedding: Zap,
  vector_search: Database,
  keyword_search: Search,
  hybrid_fusion: GitMerge,
  rrf_merge: Hash,
  prompt_building: FileText,
  llm_generation: Sparkles,
}

function formatDuration(ms: number | undefined): string {
  if (ms == null) return '—'
  if (ms < 1) return '<1ms'
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function SpanRow({ span, depth = 0 }: { span: Span; depth?: number }) {
  const [expanded, setExpanded] = useState(false)
  const Icon = SPAN_ICONS[span.spanType] || Activity
  const isError = span.status === 'error'
  const hasDetails =
    span.input != null || span.output != null || span.error != null
  const hasMetrics = Object.values(span.metrics).some((v) => v != null)

  return (
    <div>
      <button
        onClick={() => hasDetails || hasMetrics ? setExpanded(!expanded) : undefined}
        className={cn(
          'w-full flex items-center gap-2 px-3 py-2 text-left text-sm hover:bg-zinc-50 rounded transition-colors',
          isError && 'bg-red-50 hover:bg-red-50',
          depth > 0 && 'ml-5 border-l border-zinc-200'
        )}
      >
        {hasDetails || hasMetrics ? (
          expanded ? (
            <ChevronDown className="h-3 w-3 text-zinc-400 flex-shrink-0" />
          ) : (
            <ChevronRight className="h-3 w-3 text-zinc-400 flex-shrink-0" />
          )
        ) : (
          <span className="w-3 flex-shrink-0" />
        )}
        <Icon
          className={cn(
            'h-3.5 w-3.5 flex-shrink-0',
            isError ? 'text-red-500' : 'text-zinc-500'
          )}
        />
        <span
          className={cn(
            'flex-1 truncate font-medium',
            isError ? 'text-red-700' : 'text-zinc-700'
          )}
        >
          {span.name}
        </span>
        {isError && (
          <AlertCircle className="h-3.5 w-3.5 text-red-500 flex-shrink-0" />
        )}
        {span.durationMs != null && (
          <Badge
            variant="secondary"
            className="text-[10px] px-1.5 py-0 font-mono"
          >
            {formatDuration(span.durationMs)}
          </Badge>
        )}
      </button>

      {expanded && (
        <div className={cn('px-3 pb-2', depth > 0 && 'ml-5 border-l border-zinc-200')}>
          <div className="ml-8 space-y-2">
            {/* Metrics table */}
            {hasMetrics && (
              <MetricsTable metrics={span.metrics} />
            )}

            {/* Input */}
            {span.input != null && (
              <DetailBlock label="Input" data={span.input} />
            )}

            {/* Output */}
            {span.output != null && (
              <DetailBlock label="Output" data={span.output} />
            )}

            {/* Error */}
            {span.error && (
              <div className="rounded bg-red-50 border border-red-200 p-2 text-xs text-red-700 font-mono">
                {span.error}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Render children */}
      {span.children.map((child) => (
        <SpanRow key={child.id} span={child} depth={depth + 1} />
      ))}
    </div>
  )
}

function MetricsTable({ metrics }: { metrics: Span['metrics'] }) {
  const entries = Object.entries(metrics).filter(
    ([, v]) => v != null
  ) as [string, string | number][]
  if (entries.length === 0) return null

  const labels: Record<string, string> = {
    latencyMs: 'Latency',
    tokenCount: 'Tokens',
    charCount: 'Characters',
    embeddingDimensions: 'Dimensions',
    resultCount: 'Results',
    similarityThreshold: 'Threshold',
    topK: 'Top K',
    promptTokens: 'Prompt Tokens',
    completionTokens: 'Completion Tokens',
    totalTokens: 'Total Tokens',
    model: 'Model',
    provider: 'Provider',
  }

  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
      {entries.map(([key, value]) => (
        <span key={key} className="text-zinc-500">
          <span className="font-medium text-zinc-600">{labels[key] || key}:</span>{' '}
          {key === 'latencyMs'
            ? formatDuration(value as number)
            : typeof value === 'number'
              ? value.toLocaleString()
              : String(value)}
        </span>
      ))}
    </div>
  )
}

function DetailBlock({ label, data }: { label: string; data: unknown }) {
  const text =
    typeof data === 'string' ? data : JSON.stringify(data, null, 2)
  const [showFull, setShowFull] = useState(false)
  const truncateAt = 500
  const isTruncated = text.length > truncateAt

  return (
    <div>
      <div className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-0.5">
        {label}
      </div>
      <pre className="rounded bg-zinc-50 border border-zinc-200 p-2 text-[11px] text-zinc-600 font-mono overflow-x-auto max-h-64 whitespace-pre-wrap">
        {showFull || !isTruncated ? text : text.slice(0, truncateAt) + '\n...'}
      </pre>
      {isTruncated && (
        <button
          onClick={() => setShowFull(!showFull)}
          className="text-[10px] text-zinc-500 hover:text-zinc-700 mt-0.5 underline"
        >
          {showFull ? 'Show less' : `Show full (${text.length} chars)`}
        </button>
      )}
    </div>
  )
}

export function QueryTracePanel({ trace }: QueryTracePanelProps) {
  const [open, setOpen] = useState(false)

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className="rounded-lg border border-zinc-200 overflow-hidden">
        <CollapsibleTrigger asChild>
          <button className="w-full flex items-center gap-2 px-4 py-2.5 bg-zinc-50 hover:bg-zinc-100 transition-colors text-left">
            {open ? (
              <ChevronDown className="h-3.5 w-3.5 text-zinc-500" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5 text-zinc-500" />
            )}
            <Activity className="h-3.5 w-3.5 text-zinc-500" />
            <span className="text-xs font-semibold text-zinc-600 uppercase tracking-wider">
              Query Trace
            </span>
            <Badge
              variant="secondary"
              className="text-[10px] px-1.5 py-0 font-mono"
            >
              {formatDuration(trace.totalDurationMs)}
            </Badge>
            <span className="text-[11px] text-zinc-400">
              {trace.spans.length} step{trace.spans.length !== 1 ? 's' : ''}
            </span>
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="border-t border-zinc-200 divide-y divide-zinc-100">
            {trace.spans.map((span) => (
              <SpanRow key={span.id} span={span} />
            ))}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  )
}
