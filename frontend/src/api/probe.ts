import apiClient from './client'
import type { DocumentProfile } from '@/types/probe'

export async function probeDocument(documentId: string): Promise<DocumentProfile> {
  const response = await apiClient.post<DocumentProfile>(`/documents/${documentId}/probe`)
  return response.data
}
