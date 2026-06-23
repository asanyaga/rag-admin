import apiClient from './client'
import { SourceDocument } from '@/types/sourceDocument'

export async function listSourceDocuments(): Promise<SourceDocument[]> {
  const response = await apiClient.get<SourceDocument[]>('/source-documents')
  return response.data
}
