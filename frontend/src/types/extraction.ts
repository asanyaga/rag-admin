import type { PromptConfig } from '@/types/prompt-config'

export type ExtractionResultStatus = 'pending' | 'completed' | 'failed'

export interface ExtractionSchema {
  id: string
  projectId: string
  name: string
  description: string | null
  schemaDefinition: Record<string, unknown>
  extractionTarget: string
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface ExtractionSchemaCreate {
  name: string
  description?: string
  schemaDefinition: Record<string, unknown>
  extractionTarget?: string
}

export interface ExtractionSchemaUpdate {
  name?: string
  description?: string
  schemaDefinition?: Record<string, unknown>
  extractionTarget?: string
}

export interface ExtractionResult {
  id: string
  documentId: string
  extractionSchemaId: string
  schemaDefinitionSnapshot: Record<string, unknown>
  extractionMethod: string
  config: Record<string, unknown> | null
  structuredData: Record<string, unknown> | null
  extractionMetadata: Record<string, unknown> | null
  citations: Record<string, unknown>[] | null
  providerResponseRaw: Record<string, unknown> | null
  sourceParseRunId: string | null
  status: ExtractionResultStatus
  statusMessage: string | null
  startedAt: string | null
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface ExtractionResultListItem {
  id: string
  documentId: string
  extractionSchemaId: string
  extractionMethod: string
  status: ExtractionResultStatus
  statusMessage: string | null
  createdAt: string
}

export interface ChunkingConfig {
  strategy: string
  config?: Record<string, unknown>
  citationLevel?: 'auto' | 'full' | 'page_only' | 'off'
  maxTokensPerMinute?: number
}

export interface PreprocessStage {
  stage: string
  config: Record<string, unknown>
}

export interface RunExtractionRequest {
  parseRunId: string
  extractionSchemaId: string
  extractionMethod: string
  config?: Record<string, unknown>
  llmConfig?: PromptConfig
  userPromptTemplate?: string
  chunking?: ChunkingConfig
  preprocess?: PreprocessStage[]
}

export interface ExtractorInfo {
  extractionMethod: string
  name: string
  description: string
  configSchema: Record<string, unknown> | null
  configured: boolean
}

export type ExtractionPhase = 'idle' | 'parsing' | 'extracting' | 'done' | 'failed'

export interface RunWithParseRequest {
  parseConfig: {
    parser: string
    /** Parser-specific fields (tier, expand, model, etc.) — does NOT include representationKind */
    config: Record<string, unknown>
    representationKind: string
  }
  extractionConfig: {
    extractionSchemaId: string
    extractionMethod: string
    config?: Record<string, unknown>
    llmConfig?: PromptConfig
    userPromptTemplate?: string
    chunking?: ChunkingConfig
    preprocess?: PreprocessStage[]
  }
}
