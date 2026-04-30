/**
 * Index feature types
 */

// Index status enum
export type IndexStatus = 'created' | 'processing' | 'ready' | 'failed'

// Index document processing status
export type IndexDocumentStatus = 'pending' | 'processing' | 'completed' | 'failed'

// CDM source representation
export type SourceRepresentation = 'raw_text' | 'full_text' | 'full_markdown' | 'block'

// Chunking strategy
export type ChunkingStrategy =
  | 'fixed_size'
  | 'recursive_character'
  | 'markdown_heading'
  | 'block'
  | 'classified_block'

// Index configuration
export interface IndexConfig {
  // CDM binding
  sourceRepresentation: SourceRepresentation
  parser: string | null
  parseConfigHash: string | null
  // Chunking
  chunkingStrategy: ChunkingStrategy
  chunkSize: number
  chunkOverlap: number
  chunkUnit: 'tokens' | 'characters'
  // Markdown-specific chunking
  splitHeadingLevel: number
  maxSectionChars: number
  // Embedding
  embeddingProvider: string
  embeddingModel: string
  embeddingDimensions: number | null
}

// Index statistics
export interface IndexStats {
  totalChunks: number
  totalDocuments: number
  avgChunkSizeChars: number
  avgChunkSizeTokens: number
  minChunkSizeChars: number
  maxChunkSizeChars: number
  totalTokens: number
  embeddingDimensions: number
  processedAt: string
}

// Full index entity
export interface Index {
  id: string
  projectId: string
  name: string
  description: string | null
  config: IndexConfig
  stats: IndexStats | null
  status: IndexStatus
  version: number
  configDirty: boolean
  errorMessage: string | null
  createdBy: string
  createdAt: string
  updatedAt: string
  documentCount: number
  chunkCount: number
  documentIds: string[]
}

// Simplified index for list views
export interface IndexListItem {
  id: string
  projectId: string
  name: string
  description: string | null
  status: IndexStatus
  documentCount: number
  chunkCount: number
  embeddingModel: string | null
  chunkingStrategy: string | null
  createdAt: string
}

// Document status within an index
export interface IndexDocumentStatusItem {
  documentId: string
  status: IndexDocumentStatus
  chunksCreated: number | null
  errorMessage: string | null
  processedAt: string | null
}

// Processing status response
export interface IndexProcessingStatus {
  status: IndexStatus
  totalDocuments: number
  processedDocuments: number
  failedDocuments: number
  progressPercent: number
  startedAt: string | null
  documents: IndexDocumentStatusItem[]
}

// Create index request
export interface IndexCreate {
  name: string
  description?: string
  documentIds: string[]
  config: Partial<IndexConfig>
  autoProcess?: boolean
}

// Update index request
export interface IndexUpdate {
  name?: string
  description?: string
}

// Add documents request
export interface AddDocumentsRequest {
  documentIds: string[]
  parseRunIds?: Record<string, string>  // document_id → parse_run_id
}

// Chunk preview types
export interface ChunkPreview {
  index: number
  content: string
  charCount: number
  tokenCount: number
  overlapStartChars: number
  overlapEndChars: number
}

export interface ChunkPreviewResponse {
  totalChunksEstimate: number
  avgChunkSizeChars: number
  avgChunkSizeTokens: number
  minChunkSizeChars: number
  maxChunkSizeChars: number
  previewChunks: ChunkPreview[]
}

export interface ChunkPreviewRequest {
  documentId: string
  config: Partial<IndexConfig>
  maxChunks?: number
}

// Chunk types
export interface Chunk {
  id: string
  indexId: string
  documentId: string
  content: string
  chunkIndex: number
  tokenCount: number
  charCount: number
  metadata: Record<string, unknown>
  createdAt: string
  documentTitle: string | null
  documentFilename: string | null
}

export interface ChunkListItem {
  id: string
  documentId: string
  content: string
  contentPreview: string
  chunkIndex: number
  tokenCount: number
  charCount: number
  documentTitle: string | null
  metadata: Record<string, unknown>
}

export interface ChunkListResponse {
  items: ChunkListItem[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// Provider key types
export interface ProviderKey {
  id: string
  userId: string
  projectId: string | null
  provider: string
  apiKeyMasked: string
  createdAt: string
  updatedAt: string
}

export interface ProviderKeyCreate {
  provider: string
  apiKey: string
}

// ─── Playground / Query types ───────────────────────────────────────────────

export type SearchType = 'semantic' | 'keyword' | 'hybrid'

export interface QueryRequest {
  query: string
  searchType: SearchType
  topK: number
  similarityThreshold: number
  projectId: string
}

export interface RetrievalResultMetadata {
  documentId: string
  documentName: string
  page: number | null
  pageNumbers: number[] | null
  chunkIndex: number
  tokenCount: number
  charCount: number
  chunkMetadata: Record<string, unknown>
}

export interface RetrievalResult {
  chunkId: string
  rank: number
  score: number
  content: string
  metadata: RetrievalResultMetadata
}

export interface QueryResponse {
  query: string
  results: RetrievalResult[]
  totalResults: number
  searchType: SearchType
  executionTimeMs: number
  trace?: import('./trace').QueryTrace
}

export interface ProviderInfo {
  name: string
  displayName: string
  models: string[]
  requiresKey: boolean
}

export interface ProviderListResponse {
  providers: ProviderInfo[]
}
