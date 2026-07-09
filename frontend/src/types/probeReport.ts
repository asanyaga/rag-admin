export type ObservationLabel =
  | 'text_image' | 'decorative_image' | 'text_covered_image' | 'uncertain' | 'table_grid'
export type PageType = 'text' | 'scanned' | 'mixed' | 'empty'

export interface BBox { x0: number; y0: number; x1: number; y1: number }
export interface Signal {
  name: string
  value: number | string
  unit: string | null
  strength: number | null
  detail: string | null
}
export interface Observation { label: ObservationLabel; confidence: number }
export interface RegionFinding {
  id: string
  page_index: number
  kind: 'image' | 'table'
  bbox: BBox
  signals: Signal[]
  observation: Observation
}
export interface PageProfile {
  index: number
  page_type: PageType
  signals: Signal[]
  regions: RegionFinding[]
}
export interface ParserSuggestion {
  authoritative: boolean
  tools: string[]
  ocr_pages: number[]
  overall_confidence: number
  rationale: string[]
}
export interface ProbeReport {
  document_id: string
  filename: string | null
  page_count: number
  inspection: Record<string, unknown>
  pages: PageProfile[]
  suggestion: ParserSuggestion | null
  duration_ms: number
  probed_at: string
}
export interface Thresholds {
  min_text_chars: number
  cid_ratio: number
  edge_density_min: number
  coverage_min: number
  table_line_min: number
  overlap_covered: number
}
export interface ProbeConfig {
  enabled_signals: string[]
  thresholds: Thresholds
  backend: 'fitz'
}
