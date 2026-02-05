export type DocumentStatus = 'processing' | 'ready' | 'failed'

export interface Document {
  id: string
  projectId: string
  sourceType: string
  sourceIdentifier: string
  title: string
  description: string | null
  extractedText: string | null
  sourceMetadata: Record<string, unknown>
  processingMetadata: Record<string, unknown> | null
  status: DocumentStatus
  statusMessage: string | null
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface DocumentListItem {
  id: string
  projectId: string
  sourceType: string
  title: string
  description: string | null
  status: DocumentStatus
  statusMessage: string | null
  createdAt: string
  updatedAt: string
}

export interface DocumentUpload {
  projectId: string
  title: string
  description?: string
  file: File
}

export interface DocumentUpdate {
  title?: string
  description?: string
}

export interface DocumentTextResponse {
  text: string
}
