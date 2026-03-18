export type ParseResultStatus = 'pending' | 'completed' | 'failed'

export interface ParseResult {
  id: string
  documentId: string
  parserType: string
  fidelity: string
  parserConfig: Record<string, unknown> | null
  rawText: string | null
  markdown: string | null
  pages: Array<Record<string, unknown>> | null
  documentStructure: Record<string, unknown> | null
  diagnostics: Record<string, unknown> | null
  metadata: Record<string, unknown> | null
  status: ParseResultStatus
  statusMessage: string | null
  startedAt: string | null
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface ParseResultListItem {
  id: string
  documentId: string
  parserType: string
  fidelity: string
  status: ParseResultStatus
  statusMessage: string | null
  diagnostics: Record<string, unknown> | null
  createdAt: string
}

export interface ParserInfo {
  parserType: string
  name: string
  description: string
  supportedFileTypes: string[]
  configSchema: Record<string, unknown> | null
}

export type ParseConfig = {
  tier?: string
  expand?: string[]
  [key: string]: unknown
}
