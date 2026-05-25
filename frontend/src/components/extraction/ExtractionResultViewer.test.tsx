import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ExtractionResultViewer } from './ExtractionResultViewer'
import type { ExtractionResult } from '@/types/extraction'

function buildResult(overrides: Partial<ExtractionResult> = {}): ExtractionResult {
  return {
    id: 'result-1',
    documentId: 'doc-1',
    extractionSchemaId: 'schema-1',
    schemaDefinitionSnapshot: {},
    extractionMethod: 'llamaextract',
    config: null,
    structuredData: { invoice_number: 'INV-001' },
    extractionMetadata: { latency_ms: 1234, file_id: 'f-abc' },
    citations: null,
    providerResponseRaw: null,
    sourceParseRunId: 'run-1',
    status: 'completed',
    statusMessage: null,
    startedAt: '2026-01-01T00:00:00Z',
    createdBy: 'user-1',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('ExtractionResultViewer', () => {
  it('shows extraction metadata collapsible when extractionMetadata is present', () => {
    render(<ExtractionResultViewer result={buildResult()} />)
    expect(screen.getByText('Extraction Metadata')).toBeInTheDocument()
  })

  it('shows provider response collapsible when providerResponseRaw is present', () => {
    render(
      <ExtractionResultViewer
        result={buildResult({ providerResponseRaw: { data: { invoice_number: 'INV-001' } } })}
      />
    )
    expect(screen.getByText('Provider Response')).toBeInTheDocument()
  })

  it('does not show provider response collapsible when providerResponseRaw is null', () => {
    render(<ExtractionResultViewer result={buildResult({ providerResponseRaw: null })} />)
    expect(screen.queryByText('Provider Response')).not.toBeInTheDocument()
  })

  it('does not show old metadata label', () => {
    render(<ExtractionResultViewer result={buildResult()} />)
    expect(screen.queryByText(/citations \/ reasoning/i)).not.toBeInTheDocument()
  })
})
