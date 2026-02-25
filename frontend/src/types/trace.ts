/**
 * Query trace types for pipeline observability.
 */

export interface SpanMetrics {
  latencyMs?: number
  tokenCount?: number
  charCount?: number
  embeddingDimensions?: number
  resultCount?: number
  similarityThreshold?: number
  topK?: number
  promptTokens?: number
  completionTokens?: number
  totalTokens?: number
  model?: string
  provider?: string
}

export interface Span {
  id: string
  parentId?: string
  spanType: string
  name: string
  input?: unknown
  output?: unknown
  metrics: SpanMetrics
  startedAt: string
  endedAt?: string
  durationMs?: number
  order: number
  status: string
  error?: string
  children: Span[]
}

export interface QueryTrace {
  traceId: string
  query: string
  searchType: string
  totalDurationMs: number
  spans: Span[]
  createdAt: string
}
