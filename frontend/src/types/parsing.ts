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
  model?: string
  [key: string]: unknown
}
