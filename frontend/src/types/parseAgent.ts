export type ParseAgentRunStatus = 'running' | 'completed' | 'failed'

export interface ParseAgentRunSummary {
  id: string
  projectId: string
  sourceDocumentId: string
  status: ParseAgentRunStatus
  startedAt: string
  finishedAt: string | null
  error: string | null
}

export interface ParseAgentRunStep {
  id: string
  seq: number
  node: string
  phase: string
  status: string
  inputKeys: string[]
  outputKeys: string[]
  stateDelta: Record<string, unknown>
  message: string | null
  durationMs: number | null
  createdAt: string
}

export interface ParseAgentRunDetail {
  run: ParseAgentRunSummary
  steps: ParseAgentRunStep[]
  graphNodes: string[]
}

export interface StartParseAgentRunRequest {
  projectId: string
  file: File
  parserType?: string
  parseConfig?: string
}
