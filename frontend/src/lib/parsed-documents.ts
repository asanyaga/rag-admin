import apiClient from '@/api/client'

export interface ParsedDocumentListItem {
  id: string
  parseRunId: string
  parser: string
  parseConfigHash: string
  sourceDocumentId: string
  sourceFilename: string | null
  hasFullMarkdown: boolean
  blockCount: number
  parsedAt: string
}

export interface ParseConfigOption {
  parser: string
  parseConfigHash: string
  config: Record<string, unknown>
  parsedDocumentCount: number
  hasFullMarkdown: boolean
  latestParsedAt: string
}

export async function listParseConfigs(
  projectId: string,
): Promise<ParseConfigOption[]> {
  const response = await apiClient.get<ParseConfigOption[]>(
    `/projects/${projectId}/parse-runs/configs`,
  )
  return response.data
}

export async function listParsedDocuments(
  projectId: string,
  params: {
    parser?: string
    parseConfigHash?: string
    representation?: 'full_text' | 'block'
    latestPerSource?: boolean
  } = {},
): Promise<ParsedDocumentListItem[]> {
  const response = await apiClient.get<ParsedDocumentListItem[]>(
    `/projects/${projectId}/parsed-documents`,
    { params },
  )
  return response.data
}
