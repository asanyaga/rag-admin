// frontend/src/types/exportMapping.ts
export interface ExportMapping {
  id: string
  projectId: string
  dataStoreId: string
  name: string
  fieldMapping: { sourcePath: string; destinationColumn: string }[]
  createdAt: string
  updatedAt: string
}

export interface ExportMappingCreate {
  dataStoreId: string
  name: string
  fieldMapping: { sourcePath: string; destinationColumn: string }[]
}

export interface ExportMappingUpdate {
  name?: string
  fieldMapping?: { sourcePath: string; destinationColumn: string }[]
}
