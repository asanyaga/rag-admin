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

export interface RunExtractionRequest {
  documentId: string
  extractionSchemaId: string
  extractionMethod: string
  config?: Record<string, unknown>
}

export interface ExtractorInfo {
  extractionMethod: string
  name: string
  description: string
  configSchema: Record<string, unknown> | null
}
