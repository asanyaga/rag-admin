/**
 * Golden Sets API client functions
 */
import apiClient from './client'
import type {
  GoldenSet,
  GoldenSetDetail,
  GoldenSetCreate,
  GoldenSetUpdate,
  QueryCreate,
  QueryUpdate,
  GoldenSetQuery,
  SourceCreate,
  GoldenSetSource,
  GenerateRequest,
  BulkReviewRequest,
} from '@/types/golden-set'

export async function listGoldenSets(projectId: string): Promise<GoldenSet[]> {
  const response = await apiClient.get<GoldenSet[]>(
    `/projects/${projectId}/golden-sets`
  )
  return response.data
}

export async function getGoldenSet(
  projectId: string,
  goldenSetId: string
): Promise<GoldenSetDetail> {
  const response = await apiClient.get<GoldenSetDetail>(
    `/projects/${projectId}/golden-sets/${goldenSetId}`
  )
  return response.data
}

export async function createGoldenSet(
  projectId: string,
  data: GoldenSetCreate
): Promise<GoldenSet> {
  const response = await apiClient.post<GoldenSet>(
    `/projects/${projectId}/golden-sets`,
    data
  )
  return response.data
}

export async function updateGoldenSet(
  projectId: string,
  goldenSetId: string,
  data: GoldenSetUpdate
): Promise<GoldenSet> {
  const response = await apiClient.patch<GoldenSet>(
    `/projects/${projectId}/golden-sets/${goldenSetId}`,
    data
  )
  return response.data
}

export async function deleteGoldenSet(
  projectId: string,
  goldenSetId: string
): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/golden-sets/${goldenSetId}`)
}

export async function addQuery(
  projectId: string,
  goldenSetId: string,
  data: QueryCreate
): Promise<GoldenSetQuery> {
  const response = await apiClient.post<GoldenSetQuery>(
    `/projects/${projectId}/golden-sets/${goldenSetId}/queries`,
    data
  )
  return response.data
}

export async function updateQuery(
  projectId: string,
  goldenSetId: string,
  queryId: string,
  data: QueryUpdate
): Promise<GoldenSetQuery> {
  const response = await apiClient.patch<GoldenSetQuery>(
    `/projects/${projectId}/golden-sets/${goldenSetId}/queries/${queryId}`,
    data
  )
  return response.data
}

export async function deleteQuery(
  projectId: string,
  goldenSetId: string,
  queryId: string
): Promise<void> {
  await apiClient.delete(
    `/projects/${projectId}/golden-sets/${goldenSetId}/queries/${queryId}`
  )
}

export async function addSource(
  projectId: string,
  goldenSetId: string,
  queryId: string,
  data: SourceCreate
): Promise<GoldenSetSource> {
  const response = await apiClient.post<GoldenSetSource>(
    `/projects/${projectId}/golden-sets/${goldenSetId}/queries/${queryId}/sources`,
    data
  )
  return response.data
}

export async function deleteSource(
  projectId: string,
  goldenSetId: string,
  queryId: string,
  sourceId: string
): Promise<void> {
  await apiClient.delete(
    `/projects/${projectId}/golden-sets/${goldenSetId}/queries/${queryId}/sources/${sourceId}`
  )
}

export async function generateGoldenSet(
  projectId: string,
  goldenSetId: string,
  data: GenerateRequest
): Promise<GoldenSetDetail> {
  const response = await apiClient.post<GoldenSetDetail>(
    `/projects/${projectId}/golden-sets/${goldenSetId}/generate`,
    data
  )
  return response.data
}

export async function bulkReviewQueries(
  projectId: string,
  goldenSetId: string,
  data: BulkReviewRequest
): Promise<{ updated: number }> {
  const response = await apiClient.post<{ updated: number }>(
    `/projects/${projectId}/golden-sets/${goldenSetId}/queries/bulk-review`,
    data
  )
  return response.data
}
