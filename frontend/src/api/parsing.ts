import apiClient from './client'
import type {
  ParseResult,
  ParseResultListItem,
  ParserInfo,
  ParseConfig,
} from '@/types/parsing'

export async function getAvailableParsers(): Promise<ParserInfo[]> {
  const response = await apiClient.get<ParserInfo[]>('/parsers')
  return response.data
}

export async function listParseResults(
  documentId: string
): Promise<ParseResultListItem[]> {
  const response = await apiClient.get<ParseResultListItem[]>(
    `/documents/${documentId}/parse-results`
  )
  return response.data
}

export async function getParseResult(resultId: string): Promise<ParseResult> {
  const response = await apiClient.get<ParseResult>(
    `/parse-results/${resultId}`
  )
  return response.data
}

export async function reparseDocument(
  documentId: string,
  parserType: string,
  config?: ParseConfig
): Promise<ParseResult> {
  const response = await apiClient.post<ParseResult>(
    `/documents/${documentId}/parse`,
    {
      parserType,
      config: config || null,
    }
  )
  return response.data
}
