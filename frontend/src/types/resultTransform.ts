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

export interface NormalizeFieldRule {
  type: string
  // trim
  chars?: string | string[]
  // stripRegex | regexExtract
  pattern?: string
  // regexExtract
  group?: string | number
  // stripPrefix | stripSuffix
  prefix?: string
  suffix?: string
  // split
  delimiter?: string
  index?: number
  // replace
  find?: string
  replacement?: string
  // alias
  map?: Record<string, string>
  // nullifyIfIn | stripTrailingChars
  values?: string[]
}

export interface NormalizeFieldConfig {
  sourceField: string
  outputField: string
  rules: NormalizeFieldRule[]
}
