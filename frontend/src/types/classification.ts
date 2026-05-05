// frontend/src/types/classification.ts

export type ClassificationRunStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface ClassificationRegion {
  id: string
  label: string
  pageStart: number
  pageEnd: number
  blockIds: string[]
  confidence: number | null
  reasoning: string | null
  source: 'llm' | 'human'
}

export interface ClassificationRun {
  id: string
  parseRunId: string
  documentId: string
  labelsRequested: string[]
  llmProvider: string
  llmModel: string
  status: ClassificationRunStatus
  error: string | null
  batchSize: number
  batchOverlap: number
  inputTokens: number | null
  outputTokens: number | null
  durationMs: number | null
  createdAt: string
  regions: ClassificationRegion[]
}

export interface ClassificationRunCreateRequest {
  parseRunId: string
  labels: string[]
  llmProvider?: string
  llmModel?: string
  batchSize?: number
  batchOverlap?: number
}
