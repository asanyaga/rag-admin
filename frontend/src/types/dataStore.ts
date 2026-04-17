// frontend/src/types/dataStore.ts

export interface ColumnDefinition {
  name: string
  type: 'text' | 'integer' | 'numeric' | 'boolean' | 'timestamptz'
  nullable: boolean
  description: string
}

export interface DataStore {
  id: string
  projectId: string
  name: string
  description: string | null
  tableName: string
  schemaDefinition: ColumnDefinition[]
  rowCount: number
  createdAt: string
  updatedAt: string
}

export interface DataStoreCreate {
  name: string
  description?: string
  schema_definition: ColumnDefinition[]
}

export interface DataStoreUpdate {
  name?: string
  description?: string
  schema_definition?: ColumnDefinition[]
}

export interface DataStoreRow {
  id: string
  data: Record<string, unknown>
  sourceMetadata: Record<string, unknown> | null
  createdAt: string
  updatedAt: string
}

export interface DataStoreRowsResponse {
  rows: DataStoreRow[]
  total: number
  limit: number
  offset: number
}

export interface CsvImportResponse {
  rowsImported: number
}

export interface ExportPreviewRequest {
  sourceData: Record<string, unknown>
  fieldMapping: Record<string, string>
}

export interface ExportPreviewResponse {
  rows: Record<string, unknown>[]
  rowCount: number
}

export interface ExportExecuteResponse {
  rowsImported: number
}
