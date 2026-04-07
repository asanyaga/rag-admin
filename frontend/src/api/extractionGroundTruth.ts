import apiClient from './client'
import type {
  ExtractionGroundTruthSet,
  ExtractionGroundTruthItem,
  CreateGroundTruthSetRequest,
  UpdateGroundTruthSetRequest,
  CreateGroundTruthItemRequest,
  UpdateGroundTruthItemRequest,
  BulkImportRequest,
  BulkImportResponse,
} from '@/types/extractionGroundTruth'

// --- Sets ---

export async function createGroundTruthSet(
  projectId: string,
  data: CreateGroundTruthSetRequest
): Promise<ExtractionGroundTruthSet> {
  const response = await apiClient.post<ExtractionGroundTruthSet>(
    `/projects/${projectId}/extraction-ground-truth-sets`,
    data
  )
  return response.data
}

export async function listGroundTruthSets(
  projectId: string,
  extractionSchemaId?: string
): Promise<ExtractionGroundTruthSet[]> {
  const params = extractionSchemaId ? { extractionSchemaId } : undefined
  const response = await apiClient.get<ExtractionGroundTruthSet[]>(
    `/projects/${projectId}/extraction-ground-truth-sets`,
    { params }
  )
  return response.data
}

export async function getGroundTruthSet(
  setId: string
): Promise<ExtractionGroundTruthSet> {
  const response = await apiClient.get<ExtractionGroundTruthSet>(
    `/extraction-ground-truth-sets/${setId}`
  )
  return response.data
}

export async function updateGroundTruthSet(
  setId: string,
  data: UpdateGroundTruthSetRequest
): Promise<ExtractionGroundTruthSet> {
  const response = await apiClient.put<ExtractionGroundTruthSet>(
    `/extraction-ground-truth-sets/${setId}`,
    data
  )
  return response.data
}

export async function deleteGroundTruthSet(
  setId: string
): Promise<void> {
  await apiClient.delete(`/extraction-ground-truth-sets/${setId}`)
}

// --- Items ---

export async function createGroundTruthItem(
  setId: string,
  data: CreateGroundTruthItemRequest
): Promise<ExtractionGroundTruthItem> {
  const response = await apiClient.post<ExtractionGroundTruthItem>(
    `/extraction-ground-truth-sets/${setId}/items`,
    data
  )
  return response.data
}

export async function bulkCreateGroundTruthItems(
  setId: string,
  data: BulkImportRequest
): Promise<BulkImportResponse> {
  const response = await apiClient.post<BulkImportResponse>(
    `/extraction-ground-truth-sets/${setId}/items/bulk`,
    data
  )
  return response.data
}

export async function listGroundTruthItems(
  setId: string
): Promise<ExtractionGroundTruthItem[]> {
  const response = await apiClient.get<ExtractionGroundTruthItem[]>(
    `/extraction-ground-truth-sets/${setId}/items`
  )
  return response.data
}

export async function getGroundTruthItem(
  itemId: string
): Promise<ExtractionGroundTruthItem> {
  const response = await apiClient.get<ExtractionGroundTruthItem>(
    `/extraction-ground-truth-items/${itemId}`
  )
  return response.data
}

export async function updateGroundTruthItem(
  itemId: string,
  data: UpdateGroundTruthItemRequest
): Promise<ExtractionGroundTruthItem> {
  const response = await apiClient.put<ExtractionGroundTruthItem>(
    `/extraction-ground-truth-items/${itemId}`,
    data
  )
  return response.data
}

export async function deleteGroundTruthItem(
  itemId: string
): Promise<void> {
  await apiClient.delete(`/extraction-ground-truth-items/${itemId}`)
}
