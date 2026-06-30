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
  classifierType: string
  classifierConfig: Record<string, unknown>
  status: ClassificationRunStatus
  error: string | null
  inputTokens: number | null
  outputTokens: number | null
  durationMs: number | null
  createdAt: string
  regions: ClassificationRegion[]
}

export interface ClassificationRunCreateRequest {
  parseRunId: string
  labels: string[]
  classifierType?: string
  classifierConfig?: Record<string, unknown>
}

export interface AnnotatedBlock {
  blockId: string
  pageIndex: number
  role: string
  text: string
  markdown: string | null
  label: string | null
}

export interface RerunDefaults {
  labels: string[]
  classifierType: string
  classifierConfig: Record<string, unknown>
}
