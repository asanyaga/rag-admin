import apiClient from './client'
import type { ParserInfo } from '@/types/parsing'

export async function getAvailableParsers(): Promise<ParserInfo[]> {
  const response = await apiClient.get<ParserInfo[]>('/parsers')
  return response.data
}
