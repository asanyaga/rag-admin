import apiClient from './client'
import type { ParseRunListItem, ParsedDocumentDetail } from '@/types/cdm'

export async function listParseRuns(
  documentId: string
): Promise<ParseRunListItem[]> {
  const response = await apiClient.get<ParseRunListItem[]>(
    `/documents/${documentId}/parse-runs`
  )
  return response.data
}

export async function getParsedDocument(
  parseRunId: string
): Promise<ParsedDocumentDetail> {
  const response = await apiClient.get<ParsedDocumentDetail>(
    `/parse-runs/${parseRunId}/parsed-document`
  )
  return response.data
}
