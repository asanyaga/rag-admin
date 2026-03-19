import apiClient from './client'
import type {
  ExtractionSchema,
  ExtractionSchemaCreate,
  ExtractionSchemaUpdate,
  ExtractionResult,
  ExtractionResultListItem,
  RunExtractionRequest,
  ExtractorInfo,
} from '@/types/extraction'

// --- Schema endpoints ---

export async function createExtractionSchema(
  projectId: string,
  data: ExtractionSchemaCreate
): Promise<ExtractionSchema> {
  const response = await apiClient.post<ExtractionSchema>(
    `/projects/${projectId}/extraction-schemas`,
    data
  )
  return response.data
}

export async function listExtractionSchemas(
  projectId: string
): Promise<ExtractionSchema[]> {
  const response = await apiClient.get<ExtractionSchema[]>(
    `/projects/${projectId}/extraction-schemas`
  )
  return response.data
}

export async function getExtractionSchema(
  schemaId: string
): Promise<ExtractionSchema> {
  const response = await apiClient.get<ExtractionSchema>(
    `/extraction-schemas/${schemaId}`
  )
  return response.data
}

export async function updateExtractionSchema(
  schemaId: string,
  data: ExtractionSchemaUpdate
): Promise<ExtractionSchema> {
  const response = await apiClient.put<ExtractionSchema>(
    `/extraction-schemas/${schemaId}`,
    data
  )
  return response.data
}

export async function deleteExtractionSchema(
  schemaId: string
): Promise<void> {
  await apiClient.delete(`/extraction-schemas/${schemaId}`)
}

// --- Extraction endpoints ---

export async function runExtraction(
  data: RunExtractionRequest
): Promise<ExtractionResult> {
  const response = await apiClient.post<ExtractionResult>(
    '/extractions/run',
    data
  )
  return response.data
}

export async function listExtractionResults(
  documentId: string
): Promise<ExtractionResultListItem[]> {
  const response = await apiClient.get<ExtractionResultListItem[]>(
    `/documents/${documentId}/extraction-results`
  )
  return response.data
}

export async function getExtractionResult(
  resultId: string
): Promise<ExtractionResult> {
  const response = await apiClient.get<ExtractionResult>(
    `/extraction-results/${resultId}`
  )
  return response.data
}

// --- Extractor info ---

export async function listExtractors(): Promise<ExtractorInfo[]> {
  const response = await apiClient.get<ExtractorInfo[]>('/extractors')
  return response.data
}
