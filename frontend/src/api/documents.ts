import apiClient from './client'
import {
  Document,
  DocumentListItem,
  DocumentUpload,
  DocumentUpdate,
  DocumentTextResponse,
  DocumentStatus,
  BulkDocumentUpload,
  BulkUploadResponse,
  BulkMoveRequest,
  BulkMoveResponse,
} from '@/types/document'

export interface ListDocumentsParams {
  projectId: string
  status?: DocumentStatus
  folderId?: string | null
  limit?: number
  offset?: number
}

export async function uploadDocument(data: DocumentUpload): Promise<Document> {
  const formData = new FormData()
  formData.append('project_id', data.projectId)
  formData.append('title', data.title)
  if (data.description) {
    formData.append('description', data.description)
  }
  formData.append('file', data.file)
  if (data.parserType) {
    formData.append('parser_type', data.parserType)
  }
  if (data.parseConfig) {
    formData.append('parse_config', JSON.stringify(data.parseConfig))
  }
  if (data.folderId) {
    formData.append('folder_id', data.folderId)
  }

  const response = await apiClient.post<Document>('/documents', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

export async function listDocuments(
  params: ListDocumentsParams
): Promise<DocumentListItem[]> {
  const response = await apiClient.get<DocumentListItem[]>('/documents', {
    params: {
      project_id: params.projectId,
      status: params.status,
      folderId: params.folderId,
      limit: params.limit,
      offset: params.offset,
    },
  })
  return response.data
}

export async function getDocument(id: string): Promise<Document> {
  const response = await apiClient.get<Document>(`/documents/${id}`)
  return response.data
}

export async function downloadDocument(id: string): Promise<Blob> {
  const response = await apiClient.get(`/documents/${id}/file`, {
    responseType: 'blob',
  })
  return response.data
}

export async function getDocumentText(id: string): Promise<string> {
  const response = await apiClient.get<DocumentTextResponse>(
    `/documents/${id}/text`
  )
  return response.data.text
}

export async function updateDocument(
  id: string,
  data: DocumentUpdate
): Promise<Document> {
  const response = await apiClient.patch<Document>(`/documents/${id}`, data)
  return response.data
}

export async function deleteDocument(id: string): Promise<void> {
  await apiClient.delete(`/documents/${id}`)
}

export async function bulkMoveDocuments(
  data: BulkMoveRequest
): Promise<BulkMoveResponse> {
  const response = await apiClient.post<BulkMoveResponse>(
    '/documents/bulk-move',
    { document_ids: data.documentIds, folder_id: data.folderId }
  )
  return response.data
}

export interface AddFromSourceRequest {
  projectId: string
  sourceDocumentId: string
  parserType: string
  parseConfig?: Record<string, unknown>
}

export async function addDocumentFromSource(
  data: AddFromSourceRequest,
): Promise<Document> {
  const response = await apiClient.post<Document>('/documents/from-source', {
    project_id: data.projectId,
    source_document_id: data.sourceDocumentId,
    parser_type: data.parserType,
    parse_config: data.parseConfig,
  })
  return response.data
}

export async function bulkUploadDocuments(
  data: BulkDocumentUpload
): Promise<BulkUploadResponse> {
  const formData = new FormData()
  formData.append('project_id', data.projectId)
  if (data.parserType) {
    formData.append('parser_type', data.parserType)
  }
  if (data.parseConfig) {
    formData.append('parse_config', JSON.stringify(data.parseConfig))
  }
  data.files.forEach((file) => {
    formData.append('files', file)
  })
  const response = await apiClient.post<BulkUploadResponse>(
    '/documents/bulk',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return response.data
}
