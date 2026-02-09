/**
 * Golden Set feature types
 */

export type GoldenSetStatus = 'draft' | 'completed'

// Source locator — discriminated union
export interface PageLocator {
  type: 'page'
  pages: number[]
}

// Extend this union for future locator types
export type SourceLocator = PageLocator

export interface GoldenSetSource {
  id: string
  documentId: string
  documentName: string
  locator: SourceLocator
  createdAt: string
}

export interface GoldenSetQuery {
  id: string
  queryText: string
  sources: GoldenSetSource[]
  createdAt: string
  updatedAt: string
}

export interface GoldenSet {
  id: string
  name: string
  description: string | null
  status: GoldenSetStatus
  queryCount: number
  documentCount: number
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface GoldenSetDetail extends GoldenSet {
  queries: GoldenSetQuery[]
}

// Request types
export interface GoldenSetCreate {
  name: string
  description?: string
}

export interface GoldenSetUpdate {
  name?: string
  description?: string
  status?: GoldenSetStatus
}

export interface QueryCreate {
  queryText: string
}

export interface QueryUpdate {
  queryText: string
}

export interface SourceCreate {
  documentId: string
  locator: SourceLocator
}
