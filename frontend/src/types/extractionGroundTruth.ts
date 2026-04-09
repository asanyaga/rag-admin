export interface ExtractionGroundTruthSet {
  id: string
  projectId: string
  extractionSchemaId: string
  extractionSchemaName: string
  name: string
  description: string | null
  itemCount: number
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface ExtractionGroundTruthItem {
  id: string
  groundTruthSetId: string
  documentId: string
  documentTitle: string
  expectedData: Record<string, unknown>
  annotations: Record<string, unknown> | null
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface CreateGroundTruthSetRequest {
  extractionSchemaId: string
  name: string
  description?: string
}

export interface UpdateGroundTruthSetRequest {
  name?: string
  description?: string
}

export interface CreateGroundTruthItemRequest {
  documentId: string
  expectedData: Record<string, unknown>
  annotations?: Record<string, unknown>
}

export interface UpdateGroundTruthItemRequest {
  expectedData?: Record<string, unknown>
  annotations?: Record<string, unknown>
}

export interface BulkImportRequest {
  items: Array<{
    documentId: string
    expectedData: Record<string, unknown>
    annotations?: Record<string, unknown>
  }>
}

export interface BulkImportResponse {
  created: number
  errors: string[]
}

// ---------------------------------------------------------------------------
// CSV Import (client-side parsing)
// ---------------------------------------------------------------------------

export interface CsvParsedRow {
  row: number
  documentId: string
  expectedData: Record<string, unknown>
  annotations: Record<string, unknown> | null
}

export interface CsvParseError {
  row: number
  message: string
}

export interface CsvParseResult {
  validRows: CsvParsedRow[]
  errors: CsvParseError[]
  duplicateRows: CsvParsedRow[]
  warnings: string[]
  totalRows: number
}
