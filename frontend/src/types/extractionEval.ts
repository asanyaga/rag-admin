export type ExtractionEvalRunStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface ExtractionEvalRunConfig {
  fuzzyThreshold?: number
  numericTolerance?: number
  weights?: Record<string, number>
}

export interface ExtractionEvalRunMetrics {
  overallScoreMean: number
  overallScoreMedian: number
  fieldAccuracy: Record<string, { exactMatchRate: number; avgScore: number }>
  lineItemsF1Mean: number | null
  documentsEvaluated: number
  documentsPerfect: number
}

export interface ExtractionEvalRun {
  id: string
  projectId: string
  groundTruthSetId: string
  groundTruthSetName: string
  name: string
  config: ExtractionEvalRunConfig
  status: ExtractionEvalRunStatus
  metrics: ExtractionEvalRunMetrics | null
  errorMessage: string | null
  itemsCompleted: number
  itemsTotal: number
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface CreateExtractionEvalRunRequest {
  groundTruthSetId: string
  name?: string
  config?: ExtractionEvalRunConfig
}

export interface FieldScore {
  exact: boolean
  fuzzy_score: number | null
  score: number
}

export interface LineItemMatch {
  predictedIdx: number
  expectedIdx: number
  cost: number
}

export interface LineItemsScore {
  precision: number
  recall: number
  f1: number
  matched: number
  predicted: number
  expected: number
  matches?: LineItemMatch[]
}

export interface ExtractionEvalResult {
  id: string
  evalRunId: string
  extractionResultId: string
  groundTruthItemId: string
  documentId: string
  documentTitle: string
  overallScore: number
  fieldScores: Record<string, FieldScore>
  lineItemsScore: LineItemsScore | null
  expectedData: Record<string, unknown> | null
  predictedData: Record<string, unknown> | null
  evaluationMetadata: Record<string, unknown> | null
  createdAt: string
}
