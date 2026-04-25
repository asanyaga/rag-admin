/**
 * CDM viewer types — wire shape of the read endpoints in
 * docs/specs/cdm_viewer_backend.md.
 */

export type ParseRunStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'partial'

export interface ParseRunListItem {
  id: string
  sourceDocumentId: string
  parser: string
  parserVersion: string | null
  representationKind: string
  status: ParseRunStatus
  startedAt: string
  finishedAt: string | null
  durationMs: number | null
  inputTokens: number | null
  outputTokens: number | null
  cost: Record<string, unknown>
  warnings: string[]
  failedPages: number[]
  providerRefs: Record<string, unknown>
  error: string | null
  config: Record<string, unknown>
  createdAt: string
}

export interface ParsedDocumentDetail {
  parseRunId: string
  sourceDocumentId: string
  pageCount: number
  blockCount: number
  fullText: string | null
  fullMarkdown: string | null
  /** Full ParsedDocument round-trippable JSON. */
  content: ParsedDocumentContent
}

/**
 * Subset of fields the viewer reads from the content blob.
 * Kept loose because new parser_extras may appear over time.
 */
export interface ParsedDocumentContent {
  pages?: Page[]
  blocks?: Block[]
  [key: string]: unknown
}

export interface Page {
  index: number
  width?: number
  height?: number
  block_ids?: string[]
  quality?: { confidence?: number | null } | null
  parser_extras?: Record<string, unknown>
  [key: string]: unknown
}

export interface Block {
  id: string
  page_index: number
  role: string
  native_type?: string | null
  native_label?: string | null
  text?: string | null
  markdown?: string | null
  bbox?: Bbox | null
  quality?: { confidence?: number | null } | null
  parser_extras?: Record<string, unknown>
  [key: string]: unknown
}

export interface Bbox {
  x0: number
  y0: number
  x1: number
  y1: number
  source_space?: string | null
  source_coords?: Record<string, unknown> | null
}
