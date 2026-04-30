/**
 * Index API client functions
 */
import apiClient from './client'
import {
  Index,
  IndexListItem,
  IndexCreate,
  IndexUpdate,
  IndexProcessingStatus,
  AddDocumentsRequest,
  ChunkPreviewRequest,
  ChunkPreviewResponse,
  Chunk,
  ChunkListResponse,
  QueryRequest,
  QueryResponse,
} from '@/types/index'

// List indexes for a project
export async function listIndexes(projectId: string): Promise<IndexListItem[]> {
  const response = await apiClient.get<IndexListItem[]>(
    `/projects/${projectId}/indexes`
  )
  return response.data
}

// Get a single index
export async function getIndex(
  projectId: string,
  indexId: string
): Promise<Index> {
  const response = await apiClient.get<Index>(
    `/projects/${projectId}/indexes/${indexId}`
  )
  return response.data
}

// Create a new index
export async function createIndex(
  projectId: string,
  data: IndexCreate
): Promise<Index> {
  const response = await apiClient.post<Index>(
    `/projects/${projectId}/indexes`,
    {
      name: data.name,
      description: data.description,
      documentIds: data.documentIds,
      config: {
        source_representation: data.config.sourceRepresentation ?? 'raw_text',
        parser: data.config.parser ?? null,
        parse_config_hash: data.config.parseConfigHash ?? null,
        chunking_strategy: data.config.chunkingStrategy,
        chunk_size: data.config.chunkSize,
        chunk_overlap: data.config.chunkOverlap,
        chunk_unit: data.config.chunkUnit,
        embedding_provider: data.config.embeddingProvider,
        embedding_model: data.config.embeddingModel,
        embedding_dimensions: data.config.embeddingDimensions,
      },
      autoProcess: data.autoProcess,
    }
  )
  return response.data
}

// Update an index
export async function updateIndex(
  projectId: string,
  indexId: string,
  data: IndexUpdate
): Promise<Index> {
  const response = await apiClient.patch<Index>(
    `/projects/${projectId}/indexes/${indexId}`,
    data
  )
  return response.data
}

// Delete an index
export async function deleteIndex(
  projectId: string,
  indexId: string
): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/indexes/${indexId}`)
}

// Start processing an index
export async function processIndex(
  projectId: string,
  indexId: string
): Promise<Index> {
  const response = await apiClient.post<Index>(
    `/projects/${projectId}/indexes/${indexId}/process`
  )
  return response.data
}

// Retry processing a failed index
export async function retryIndex(
  projectId: string,
  indexId: string
): Promise<Index> {
  const response = await apiClient.post<Index>(
    `/projects/${projectId}/indexes/${indexId}/retry`
  )
  return response.data
}

// Get processing status
export async function getProcessingStatus(
  projectId: string,
  indexId: string
): Promise<IndexProcessingStatus> {
  const response = await apiClient.get<IndexProcessingStatus>(
    `/projects/${projectId}/indexes/${indexId}/status`
  )
  return response.data
}

// Add documents to an index
export async function addDocuments(
  projectId: string,
  indexId: string,
  data: AddDocumentsRequest
): Promise<Index> {
  const response = await apiClient.post<Index>(
    `/projects/${projectId}/indexes/${indexId}/documents`,
    {
      documentIds: data.documentIds,
      parseRunIds: data.parseRunIds ?? null,
    }
  )
  return response.data
}

// Remove a document from an index
export async function removeDocument(
  projectId: string,
  indexId: string,
  documentId: string
): Promise<Index> {
  const response = await apiClient.delete<Index>(
    `/projects/${projectId}/indexes/${indexId}/documents/${documentId}`
  )
  return response.data
}

// Preview chunks
export async function previewChunks(
  projectId: string,
  data: ChunkPreviewRequest
): Promise<ChunkPreviewResponse> {
  const body: Record<string, unknown> = {
    config: {
      // Forward the full config — sourceRepresentation, parser, parseConfigHash,
      // and the markdown chunking knobs all matter for accurate preview.
      source_representation: data.config.sourceRepresentation,
      parser: data.config.parser,
      parse_config_hash: data.config.parseConfigHash,
      chunking_strategy: data.config.chunkingStrategy,
      chunk_size: data.config.chunkSize,
      chunk_overlap: data.config.chunkOverlap,
      chunk_unit: data.config.chunkUnit,
      split_heading_level: data.config.splitHeadingLevel,
      max_section_chars: data.config.maxSectionChars,
      embedding_provider: data.config.embeddingProvider,
      embedding_model: data.config.embeddingModel,
      embedding_dimensions: data.config.embeddingDimensions,
    },
    maxChunks: data.maxChunks ?? 5,
  }
  if (data.parsedDocumentId) body.parsedDocumentId = data.parsedDocumentId
  else if (data.documentId) body.documentId = data.documentId

  const response = await apiClient.post<ChunkPreviewResponse>(
    `/projects/${projectId}/indexes/preview-chunks`,
    body,
  )
  return response.data
}

// List chunks
export async function listChunks(
  projectId: string,
  indexId: string,
  page: number = 1,
  pageSize: number = 20,
  search?: string
): Promise<ChunkListResponse> {
  const response = await apiClient.get<ChunkListResponse>(
    `/projects/${projectId}/indexes/${indexId}/chunks`,
    {
      params: {
        page,
        pageSize,
        search,
      },
    }
  )
  return response.data
}

// Get a single chunk
export async function getChunk(
  projectId: string,
  indexId: string,
  chunkId: string
): Promise<Chunk> {
  const response = await apiClient.get<Chunk>(
    `/projects/${projectId}/indexes/${indexId}/chunks/${chunkId}`
  )
  return response.data
}

// ─── Query / Playground ─────────────────────────────────────────────────────

export async function queryIndex(
  projectId: string,
  indexId: string,
  params: QueryRequest,
  options?: { trace?: boolean }
): Promise<QueryResponse> {
  const response = await apiClient.post<QueryResponse>(
    `/projects/${projectId}/indexes/${indexId}/query`,
    {
      query: params.query,
      searchType: params.searchType,
      topK: params.topK,
      similarityThreshold: params.similarityThreshold,
    },
    {
      params: options?.trace ? { trace: true } : undefined,
    }
  )
  return response.data
}
