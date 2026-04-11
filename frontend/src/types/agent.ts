// --- Agent Tools ---

export interface AgentTool {
  slug: string
  name: string
  category: string
  description: string
  inputKeys: string[]
  outputKeys: string[]
  configSchema: Record<string, unknown>
}

// --- Flow Definitions ---

export interface FlowNodeDef {
  id: string
  tool: string
  config?: Record<string, unknown>
  position?: { x: number; y: number }
}

export interface FlowEdgeDef {
  source: string
  target: string
}

export interface FlowConditionalEdgeDef {
  source: string
  router: string
  targets: string[]
}

export interface FlowDefinitionData {
  nodes: FlowNodeDef[]
  edges: FlowEdgeDef[]
  conditional_edges?: FlowConditionalEdgeDef[]
}

export interface FlowDefinition {
  id: string
  projectId: string
  name: string
  description: string | null
  definition: FlowDefinitionData
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface FlowDefinitionCreate {
  name: string
  description?: string
  definition: FlowDefinitionData
}

export interface FlowDefinitionUpdate {
  name?: string
  description?: string
  definition?: FlowDefinitionData
}

// --- Agent Types & Configs ---

export interface AgentType {
  slug: string
  name: string
  description: string
  nodes: { name: string; label: string }[]
  configSchema: Record<string, unknown>
}

export interface AgentConfig {
  id: string
  projectId: string
  agentType: string
  config: Record<string, unknown> | null
  enabled: boolean
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface AgentConfigCreate {
  agentType: string
  config?: Record<string, unknown>
}

// --- Receipt Processing ---

export type AgentReceiptStatus =
  | 'pending'
  | 'extracting'
  | 'reviewing'
  | 'approved'
  | 'exported'
  | 'failed'

export interface AgentReceipt {
  id: string
  projectId: string
  documentId: string
  extractionSchemaId: string
  status: AgentReceiptStatus
  statusMessage: string | null
  extractedData: Record<string, unknown> | null
  reviewedData: Record<string, unknown> | null
  threadId: string | null
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface AgentReceiptListItem {
  id: string
  documentId: string
  status: AgentReceiptStatus
  statusMessage: string | null
  extractedData: Record<string, unknown> | null
  createdAt: string
}

export interface StartProcessingRequest {
  documentId: string
  extractionSchemaId: string
}

export interface SubmitReviewRequest {
  action: 'approve' | 'edit' | 'reject'
  data?: Record<string, unknown>
}

// --- Flow Runs ---

export type FlowRunStatus =
  | 'pending'
  | 'running'
  | 'waiting_for_input'
  | 'completed'
  | 'failed'

export interface FlowRun {
  id: string
  projectId: string
  flowDefinitionId: string
  status: FlowRunStatus
  statusMessage: string | null
  initialState: Record<string, unknown> | null
  currentState: Record<string, unknown> | null
  currentNode: string | null
  threadId: string | null
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface FlowRunListItem {
  id: string
  flowDefinitionId: string
  status: FlowRunStatus
  statusMessage: string | null
  currentNode: string | null
  createdAt: string
}

export interface StartFlowRunRequest {
  flowDefinitionId: string
  initialState: Record<string, unknown>
}

export interface StartExtractRunRequest {
  flowDefinitionId: string
  documentId: string
  extractionSchemaId: string
}

export interface ResumeFlowRunRequest {
  resumeValue: Record<string, unknown>
}
