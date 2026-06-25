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

export interface LocalPipelineToolConfig {
  tool_id: string
  config: Record<string, unknown>
}

export interface LocalPipelineParseConfig {
  tools: LocalPipelineToolConfig[]
  eviction_overlap_threshold: number
}
