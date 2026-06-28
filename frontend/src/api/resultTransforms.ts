import apiClient from './client'
import type {
  TransformCatalogItem, TransformPreviewRequest, TransformPreview,
} from '@/types/resultTransform'
import type { ExtractionResult } from '@/types/extraction'

export async function getTransformCatalog(): Promise<TransformCatalogItem[]> {
  const { data } = await apiClient.get<TransformCatalogItem[]>('/result-transforms/catalog')
  return data
}

export async function previewTransform(
  projectId: string, body: TransformPreviewRequest,
): Promise<TransformPreview> {
  const { data } = await apiClient.post<TransformPreview>(
    `/projects/${projectId}/result-transforms/preview`, body)
  return data
}

export async function applyTransform(
  projectId: string, body: TransformPreviewRequest & { targetSchemaId?: string },
): Promise<ExtractionResult> {
  const { data } = await apiClient.post<ExtractionResult>(
    `/projects/${projectId}/result-transforms/apply`, body)
  return data
}
