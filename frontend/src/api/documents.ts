import apiClient from './client'
import {
  Document,
  DocumentListItem,
  DocumentUpload,
  DocumentUpdate,
  DocumentTextResponse,
  DocumentStatus,
} from '@/types/document'

export interface ListDocumentsParams {
  projectId: string
  status?: DocumentStatus
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
