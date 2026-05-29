/**
 * Evaluation Run feature types
 */
import type { PromptConfig } from '@/types/prompt-config'

export type EvalRunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'partial_failure'

export type EvalMode = 'retrieval_only' | 'retrieval_and_answer'

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
  avgFaithfulness: number | null
  avgRelevance: number | null
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
  mode: EvalMode
  generationConfig: PromptConfig | null
  judgeConfig: PromptConfig | null
  itemsCompleted: number
  failedItemCount: number
  experimentId?: string
  experimentName?: string
  variantLabel?: string
}

export interface CreateEvalRunRequest {
  goldenSetId: string
  indexId: string
  name?: string
  config: EvalRunConfig
  mode: EvalMode
  generationConfig?: PromptConfig
  judgeConfig?: PromptConfig
  experimentId?: string
  variantLabel?: string
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

export interface ClaimItem {
  text: string
  label: 'supported' | 'unsupported' | 'unclear'
  source: string | null
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
  generatedAnswer: string | null
  faithfulnessScore: number | null
  relevanceScore: number | null
  claimBreakdown: ClaimItem[] | null
  judgeError: string | null
  generationError: string | null
  traceData?: import('../types/trace').QueryTrace | null
}

export interface EvalRunProgress {
  status: string
  itemsTotal: number
  itemsCompleted: number
  failedItemCount: number
}

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
