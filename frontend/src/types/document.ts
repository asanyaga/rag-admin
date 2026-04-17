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
  parserType?: string
  parseConfig?: Record<string, unknown>
}

export interface DocumentUpdate {
  title?: string
  description?: string
}

export interface DocumentTextResponse {
  text: string
}

export interface BulkDocumentUpload {
  projectId: string
  files: File[]
  parserType?: string
  parseConfig?: Record<string, unknown>
}

export interface BulkUploadItem {
  filename: string
  document: Document | null
  error: string | null
}

export interface BulkUploadResponse {
  results: BulkUploadItem[]
}

export type QueueItemStatus = 'pending' | 'uploading' | 'processing' | 'ready' | 'failed'

export interface QueueItem {
  file: File
  status: QueueItemStatus
  documentId: string | null
  error: string | null
}
