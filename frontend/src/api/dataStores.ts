// frontend/src/api/dataStores.ts
import apiClient from './client'
import type {
  DataStore,
  DataStoreCreate,
  DataStoreUpdate,
  DataStoreRow,
  DataStoreRowsResponse,
  CsvImportResponse,
  ExportPreviewRequest,
  ExportPreviewResponse,
  ExportExecuteResponse,
} from '@/types/dataStore'

// ── Store CRUD ────────────────────────────────────────────────────

export async function listDataStores(projectId: string): Promise<DataStore[]> {
  const response = await apiClient.get<DataStore[]>(
    `/projects/${projectId}/data-stores`
  )
  return response.data
}

export async function getDataStore(projectId: string, storeId: string): Promise<DataStore> {
  const response = await apiClient.get<DataStore>(
    `/projects/${projectId}/data-stores/${storeId}`
  )
  return response.data
}

export async function createDataStore(projectId: string, data: DataStoreCreate): Promise<DataStore> {
  const response = await apiClient.post<DataStore>(
    `/projects/${projectId}/data-stores`,
    data
  )
  return response.data
}

export async function updateDataStore(
  projectId: string,
  storeId: string,
  data: DataStoreUpdate
): Promise<DataStore> {
  const response = await apiClient.patch<DataStore>(
    `/projects/${projectId}/data-stores/${storeId}`,
    data
  )
  return response.data
}

export async function deleteDataStore(projectId: string, storeId: string): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/data-stores/${storeId}`)
}

// ── Row CRUD ──────────────────────────────────────────────────────

export async function listRows(
  projectId: string,
  storeId: string,
  limit = 50,
  offset = 0
): Promise<DataStoreRowsResponse> {
  const response = await apiClient.get<DataStoreRowsResponse>(
    `/projects/${projectId}/data-stores/${storeId}/rows`,
    { params: { limit, offset } }
  )
  return response.data
}

export async function getRow(
  projectId: string,
  storeId: string,
  rowId: string
): Promise<DataStoreRow> {
  const response = await apiClient.get<DataStoreRow>(
    `/projects/${projectId}/data-stores/${storeId}/rows/${rowId}`
  )
  return response.data
}

export async function insertRow(
  projectId: string,
  storeId: string,
  data: Record<string, unknown>
): Promise<DataStoreRow> {
  const response = await apiClient.post<DataStoreRow>(
    `/projects/${projectId}/data-stores/${storeId}/rows`,
    data
  )
  return response.data
}

export async function updateRow(
  projectId: string,
  storeId: string,
  rowId: string,
  data: Record<string, unknown>
): Promise<DataStoreRow> {
  const response = await apiClient.patch<DataStoreRow>(
    `/projects/${projectId}/data-stores/${storeId}/rows/${rowId}`,
    data
  )
  return response.data
}

export async function deleteRow(
  projectId: string,
  storeId: string,
  rowId: string
): Promise<void> {
  await apiClient.delete(
    `/projects/${projectId}/data-stores/${storeId}/rows/${rowId}`
  )
}

// ── CSV Import ────────────────────────────────────────────────────

export async function importCsv(
  projectId: string,
  storeId: string,
  file: File,
  columnMapping: Record<string, string>
): Promise<CsvImportResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('column_mapping', JSON.stringify(columnMapping))

  const response = await apiClient.post<CsvImportResponse>(
    `/projects/${projectId}/data-stores/${storeId}/import`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return response.data
}

// ── Export Preview/Execute ────────────────────────────────────────

export async function previewExport(
  projectId: string,
  storeId: string,
  data: ExportPreviewRequest
): Promise<ExportPreviewResponse> {
  const response = await apiClient.post<ExportPreviewResponse>(
    `/projects/${projectId}/data-stores/${storeId}/preview-export`,
    data
  )
  return response.data
}

export async function executeExport(
  projectId: string,
  storeId: string,
  data: ExportPreviewRequest
): Promise<ExportExecuteResponse> {
  const response = await apiClient.post<ExportExecuteResponse>(
    `/projects/${projectId}/data-stores/${storeId}/execute-export`,
    data
  )
  return response.data
}
