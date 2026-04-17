// frontend/src/api/exportMappings.ts
import apiClient from './client'
import type { ExportMapping, ExportMappingCreate, ExportMappingUpdate } from '@/types/exportMapping'

function toSnakeCase(data: ExportMappingCreate | ExportMappingUpdate): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  if ('dataStoreId' in data && data.dataStoreId !== undefined) {
    result.data_store_id = data.dataStoreId
  }
  if (data.name !== undefined) result.name = data.name
  if (data.fieldMapping !== undefined) result.field_mapping = data.fieldMapping
  return result
}

function fromApi(raw: Record<string, unknown>): ExportMapping {
  return {
    id: raw.id as string,
    projectId: raw.project_id as string,
    dataStoreId: raw.data_store_id as string,
    name: raw.name as string,
    fieldMapping: raw.field_mapping as ExportMapping['fieldMapping'],
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  }
}

export async function listExportMappings(
  projectId: string,
  dataStoreId: string
): Promise<ExportMapping[]> {
  const response = await apiClient.get<Record<string, unknown>[]>(
    `/projects/${projectId}/export-mappings`,
    { params: { data_store_id: dataStoreId } }
  )
  return response.data.map(fromApi)
}

export async function createExportMapping(
  projectId: string,
  data: ExportMappingCreate
): Promise<ExportMapping> {
  const response = await apiClient.post<Record<string, unknown>>(
    `/projects/${projectId}/export-mappings`,
    toSnakeCase(data)
  )
  return fromApi(response.data)
}

export async function updateExportMapping(
  projectId: string,
  mappingId: string,
  data: ExportMappingUpdate
): Promise<ExportMapping> {
  const response = await apiClient.put<Record<string, unknown>>(
    `/projects/${projectId}/export-mappings/${mappingId}`,
    toSnakeCase(data)
  )
  return fromApi(response.data)
}

export async function deleteExportMapping(
  projectId: string,
  mappingId: string
): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/export-mappings/${mappingId}`)
}
