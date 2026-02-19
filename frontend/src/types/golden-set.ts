/**
 * Golden Set feature types
 */

export type GoldenSetStatus = 'draft' | 'completed'
export type GenerationStatus = 'pending' | 'generating' | 'completed' | 'failed'
export type SourceMethod = 'manual' | 'auto_generated' | 'imported'
export type ReviewStatus = 'pending' | 'accepted' | 'rejected' | 'edited'
export type QuestionType = 'factual' | 'comparison' | 'summarization'

// Source locator — discriminated union
export interface PageLocator {
  type: 'page'
  pages: number[]
}

// Extend this union for future locator types
export type SourceLocator = PageLocator

export interface GoldenSetSource {
  id: string
  documentId: string
  documentName: string
  locator: SourceLocator
  createdAt: string
}

export interface GoldenSetQuery {
  id: string
  queryText: string
  sourceMethod: SourceMethod
  reviewStatus: ReviewStatus
  reasoning: string | null
  questionType: string | null
  referenceAnswer: string | null
  sources: GoldenSetSource[]
  createdAt: string
  updatedAt: string
}

export interface GenerationProgress {
  totalWindows: number
  completedWindows: number
  errorMessage: string | null
}

export interface GoldenSet {
  id: string
  name: string
  description: string | null
  status: GoldenSetStatus
  queryCount: number
  documentCount: number
  generationStatus: GenerationStatus | null
  generationProgress: GenerationProgress | null
  generationConfig: Record<string, unknown> | null
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface GoldenSetDetail extends GoldenSet {
  queries: GoldenSetQuery[]
}

// Request types
export interface GoldenSetCreate {
  name: string
  description?: string
}

export interface GoldenSetUpdate {
  name?: string
  description?: string
  status?: GoldenSetStatus
}

export interface QueryCreate {
  queryText: string
}

export interface QueryUpdate {
  queryText?: string
  reviewStatus?: ReviewStatus
  referenceAnswer?: string | null
}

export interface SourceCreate {
  documentId: string
  locator: SourceLocator
}

export interface GenerateRequest {
  documentIds: string[]
  llmProvider: string
  llmModel: string
  queriesPerDocument: number
  questionTypes: QuestionType[]
  temperature: number
}

export interface BulkReviewRequest {
  action: 'accept' | 'reject'
  queryIds: string[]
}

// Import types

export interface ImportParsedSource {
  documentName: string
  documentId: string | null
  pages: number[]
  resolved: boolean
}

export interface ImportValidQuery {
  row: number
  queryText: string
  sources: ImportParsedSource[]
  isDuplicate: boolean
}

export interface ImportParseError {
  row: number
  queryText: string
  error: string
}

export interface ImportDuplicate {
  row: number
  queryText: string
  existingQueryId: string | null
}

export interface ImportParseSummary {
  totalRows: number
  validCount: number
  errorCount: number
  duplicateCount: number
}

export interface ImportParseResponse {
  validQueries: ImportValidQuery[]
  errors: ImportParseError[]
  duplicates: ImportDuplicate[]
  summary: ImportParseSummary
}

export interface ImportConfirmSource {
  documentId: string
  locator: Record<string, unknown>
}

export interface ImportConfirmQuery {
  queryText: string
  sources: ImportConfirmSource[]
}

export interface ImportConfirmRequest {
  queries: ImportConfirmQuery[]
}

export interface ImportConfirmResponse {
  importedCount: number
}
