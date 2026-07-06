import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('@/hooks/useParserEval', () => ({
  useParserEvalCases: () => ({
    cases: [{ id: 'c1', sourceDocumentId: 's1', dimension: 'text', sourceMethod: 'human', reviewStatus: 'draft', createdAt: '2026-07-06T00:00:00Z' }],
    isLoading: false, error: null, fetchCases: vi.fn(), createCase: vi.fn(),
  }),
}))
vi.mock('@/hooks/useSourceDocuments', () => ({
  useSourceDocuments: () => ({
    sourceDocuments: [{ id: 's1', filename: 'acme.pdf' }], isLoading: false, error: null, refresh: vi.fn(),
  }),
}))

import { ParserEvalCasesTab } from './ParserEvalCasesTab'

describe('ParserEvalCasesTab', () => {
  it('lists cases with the source filename and dimension', () => {
    render(<ParserEvalCasesTab projectId="proj-1" />)
    expect(screen.getByText('acme.pdf')).toBeInTheDocument()
    expect(screen.getByText('text')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /new case/i })).toBeInTheDocument()
  })
})
