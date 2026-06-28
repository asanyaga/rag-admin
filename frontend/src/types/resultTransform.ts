export interface TransformCatalogItem {
  transform_type: string
  name: string
  description: string
  config_schema: Record<string, unknown>
}
export interface TransformPreviewRequest {
  sourceResultIds: string[]
  transformType: string
  config: Record<string, unknown>
}
export interface TransformPreview {
  rows: Record<string, unknown>[]
  flags: { rowIndex: number; flag: string }[]
}
