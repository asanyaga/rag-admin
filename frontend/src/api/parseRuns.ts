import apiClient from './client'
import type {
  ParseRunListItem,
  ParsedDocumentDetail,
  RawPayloadResponse,
} from '@/types/cdm'
import type { ParseConfig } from '@/types/parsing'

export async function listParseRuns(
  documentId: string
): Promise<ParseRunListItem[]> {
  const response = await apiClient.get<ParseRunListItem[]>(
    `/documents/${documentId}/parse-runs`
  )
  return response.data
}

export async function getParseRun(
  parseRunId: string
): Promise<ParseRunListItem> {
  const response = await apiClient.get<ParseRunListItem>(
    `/parse-runs/${parseRunId}`
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

export async function getRawPayload(
  parseRunId: string
): Promise<RawPayloadResponse> {
  const response = await apiClient.get<RawPayloadResponse>(
    `/parse-runs/${parseRunId}/raw-payload`
  )
  return response.data
}

export async function createParseRun(
  documentId: string,
  parserType: string,
  config?: ParseConfig
): Promise<void> {
  await apiClient.post(
    `/documents/${documentId}/parse-runs`,
    { parser_type: parserType, config: config ?? null }
  )
}

export async function deleteParseRun(runId: string): Promise<void> {
  await apiClient.delete(`/parse-runs/${runId}`)
}
