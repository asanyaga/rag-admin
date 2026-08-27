// --- Agent Tools ---

export interface AgentToolRuntimeInput {
  key: string
  label: string
  widget: string
}

export interface AgentTool {
  slug: string
  name: string
  category: string
  description: string
  runtimeInputs: AgentToolRuntimeInput[]
  outputs: string[]
  configSchema: Record<string, unknown>
  configPanel: string | null
}

// --- Agent Definitions ---

export interface AgentNodeDef {
  id: string
  tool: string
  config?: Record<string, unknown>
  position?: { x: number; y: number }
}

export interface AgentEdgeDef {
  source: string
  target: string
}

export interface AgentConditionalEdgeDef {
  source: string
  router: string
  targets: string[]
}

export interface AgentDefinitionData {
  nodes: AgentNodeDef[]
  edges: AgentEdgeDef[]
  conditional_edges?: AgentConditionalEdgeDef[]
}

export interface AgentDefinition {
  id: string
  projectId: string
  name: string
  description: string | null
  definition: AgentDefinitionData
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface AgentDefinitionCreate {
  name: string
  description?: string
  definition: AgentDefinitionData
}

export interface AgentDefinitionUpdate {
  name?: string
  description?: string
  definition?: AgentDefinitionData
}

// --- Agent Runs ---

export type AgentRunStatus =
  | 'pending'
  | 'running'
  | 'waiting_for_input'
  | 'completed'
  | 'failed'

export interface AgentRun {
  id: string
  projectId: string
  agentDefinitionId: string
  status: AgentRunStatus
  statusMessage: string | null
  initialState: Record<string, unknown> | null
  currentState: Record<string, unknown> | null
  currentNode: string | null
  threadId: string | null
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface AgentRunListItem {
  id: string
  agentDefinitionId: string
  status: AgentRunStatus
  statusMessage: string | null
  currentNode: string | null
  createdAt: string
}

export interface StartAgentRunRequest {
  agentDefinitionId: string
  initialState: Record<string, unknown>
}

export interface StartExtractRunRequest {
  agentDefinitionId: string
  documentId: string
  extractionSchemaId: string
}

export interface StartParseRunRequest {
  agentDefinitionId: string
  sourceDocumentId: string
  parser?: string
  representationKind?: string
  parseConfig?: Record<string, unknown>
}

export interface SubmitReviewRequest {
  action: 'approve' | 'edit' | 'reject'
  data?: Record<string, unknown>
}

export interface ResumeAgentRunRequest {
  resumeValue: Record<string, unknown>
}
