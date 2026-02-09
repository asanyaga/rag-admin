/**
 * Evaluation Run feature types
 */

export type EvalRunStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface EvalRunConfig {
  searchType: 'semantic' | 'keyword' | 'hybrid'
  topK: number
  similarityThreshold: number
}

export interface EvalRunMetrics {
  avgPrecision: number
  avgRecall: number
  avgF1: number
  queriesBelowThreshold: number
}

export interface EvalRun {
  id: string
  name: string
  goldenSetId: string
  goldenSetName: string
  indexId: string
  indexName: string
  config: EvalRunConfig
  status: EvalRunStatus
  metrics: EvalRunMetrics | null
  errorMessage: string | null
  createdBy: string
  createdAt: string
}

export interface CreateEvalRunRequest {
  goldenSetId: string
  indexId: string
  name?: string
  config: EvalRunConfig
}

// Per-query results
export interface RetrievedChunk {
  chunkId: string
  rank: number
  score: number
  content: string
  documentId: string
  documentName: string
  page: number | null
  isRelevant: boolean
}

export interface ExpectedSource {
  documentId: string
  documentName: string
  locator: { type: string; pages?: number[] }
}

export interface EvalRunResult {
  id: string
  queryId: string
  queryText: string
  precision: number
  recall: number
  f1: number
  retrievedChunks: RetrievedChunk[]
  expectedSources: ExpectedSource[]
}

// Comparison types
export interface QueryComparisonMetrics {
  precision: number
  recall: number
  f1: number
}

export interface QueryComparisonItem {
  queryId: string
  queryText: string
  baseline: QueryComparisonMetrics
  challenger: QueryComparisonMetrics
  deltaF1: number
}

export interface ComparisonSummary {
  avgDeltaPrecision: number
  avgDeltaRecall: number
  avgDeltaF1: number
  improvedQueries: number
  degradedQueries: number
  unchangedQueries: number
}

export interface RunComparison {
  baselineRun: EvalRun
  challengerRun: EvalRun
  perQueryComparison: QueryComparisonItem[]
  summary: ComparisonSummary
}
