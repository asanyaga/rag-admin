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
