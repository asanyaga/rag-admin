import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

import { CitationFooter } from './CitationFooter'
import { ChunkCitation } from '@/types/index'

const baseCitation: ChunkCitation = {
  chunkId: 'c1',
  documentId: 'd1',
  documentTitle: 'Doc',
  indexId: 'i1',
  indexVersion: 3,
  parseRunId: 'p1',
  sourceType: 'block',
  startChar: null,
  endChar: null,
  pageNumbers: [],
  headingPath: null,
  blockIds: ['b1', 'b2'],
  pageIndices: [4],
  blockRoles: ['table'],
  bboxes: [{ x0: 0.1, y0: 0.2, x1: 0.9, y1: 0.4 }],
  confidence: 0.85,
}

describe('CitationFooter', () => {
  it('renders page + role for block citations', () => {
    render(<CitationFooter citation={baseCitation} />)
    expect(screen.getByText(/page 5/i)).toBeInTheDocument() // page_index 4 → page 5
    expect(screen.getByText(/table/i)).toBeInTheDocument()
  })

  it('renders heading breadcrumb for markdown citations', () => {
    render(
      <CitationFooter
        citation={{
          ...baseCitation,
          sourceType: 'full_markdown',
          blockIds: null,
          pageIndices: null,
          blockRoles: null,
          bboxes: null,
          confidence: null,
          headingPath: ['Financials', 'Q3 Results'],
        }}
      />
    )
    expect(screen.getByText('Financials')).toBeInTheDocument()
    expect(screen.getByText('Q3 Results')).toBeInTheDocument()
  })

  it('renders page number for text citations', () => {
    render(
      <CitationFooter
        citation={{
          ...baseCitation,
          sourceType: 'full_text',
          blockIds: null,
          pageIndices: null,
          blockRoles: null,
          bboxes: null,
          confidence: null,
          pageNumbers: [7],
        }}
      />
    )
    expect(screen.getByText(/page 7/i)).toBeInTheDocument()
  })

  it('shows low-confidence tag when confidence < 0.7', () => {
    render(
      <CitationFooter
        citation={{ ...baseCitation, confidence: 0.55 }}
      />
    )
    expect(screen.getByText(/low confidence/i)).toBeInTheDocument()
  })

  it('does not show low-confidence tag at or above 0.7', () => {
    render(
      <CitationFooter
        citation={{ ...baseCitation, confidence: 0.7 }}
      />
    )
    expect(screen.queryByText(/low confidence/i)).not.toBeInTheDocument()
  })

  it('always renders Index version label', () => {
    render(<CitationFooter citation={baseCitation} />)
    expect(screen.getByText(/index v3/i)).toBeInTheDocument()
  })
})
