import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import { CaseDetailView } from './CaseDetailView'

vi.mock('@/hooks/useParserEval', () => ({
  useParserEvalCase: () => ({
    caseDetail: {
      id: 'c1', dimension: 'table', reviewStatus: 'draft',
      sourceDocumentId: 'd1', sourceMethod: 'bootstrapped', createdAt: '',
      expected: { tables: [{ page: 1, html: '<table><tr><td>Cell A</td></tr></table>' }] },
    },
    isLoading: false, verify: vi.fn(), reject: vi.fn(),
  }),
}))

describe('CaseDetailView', () => {
  it('renders draft tables with accept/reject actions', () => {
    render(<MemoryRouter><CaseDetailView projectId="p1" caseId="c1" /></MemoryRouter>)
    expect(screen.getByText('Cell A')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /accept/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument()
  })
})
