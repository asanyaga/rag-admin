export type FontHealth = 'clean' | 'cid_corrupt' | 'mixed' | 'unknown'
export type PageType = 'text' | 'scanned' | 'mixed' | 'empty'

export interface PageProfile {
  index: number
  char_count: number
  has_text_layer: boolean
  image_count: number
  font_health: FontHealth
  table_signal: boolean
  page_type: PageType
}

export interface DocumentProfile {
  source_document_id: string
  filename: string | null
  page_count: number
  pages: PageProfile[]
  has_text_layer: boolean
  has_scanned_pages: boolean
  has_cid_corruption: boolean
  table_signal: boolean
  recommended_tools: string[]
  duration_ms: number
  probed_at: string
}
