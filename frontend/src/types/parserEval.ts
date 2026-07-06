export type ParserEvalRunStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface ParserEvalCase {
  id: string
  sourceDocumentId: string
  dimension: string
  sourceMethod: string
  reviewStatus: string
  createdAt: string
}

export interface ParserEvalVariant {
  adapter: string
  config: Record<string, unknown>
}

export interface ParserEvalRun {
  id: string
  name: string
  status: ParserEvalRunStatus
  variants: ParserEvalVariant[]
  datasetId: string | null
  errorMessage: string | null
  createdAt: string
}

export interface ParserEvalResult {
  evalCaseId: string
  adapter: string
  config: Record<string, unknown>
  variantKey: string
  metrics: Record<string, number>
  primaryMetric: string | null
  details: Record<string, unknown> | null
  cost: Record<string, number> | null
  latencyMs: number | null
}

export interface CreateCaseRequest {
  sourceDocumentId: string
  dimension: string
  expected: { pages: string[] }
}

export interface CreateRunRequest {
  name?: string
  variants: ParserEvalVariant[]
  evalCaseIds: string[]
}
