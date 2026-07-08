import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import { CaseDetailView } from './CaseDetailView'

const hookState = vi.hoisted(() => ({
  saveTables: vi.fn(),
  verify: vi.fn(),
  reject: vi.fn(),
  caseDetail: {
    id: 'c1', dimension: 'table', reviewStatus: 'draft',
    sourceDocumentId: 'd1', sourceMethod: 'bootstrapped', createdAt: '',
    expected: { tables: [{ page: 1, html: '<table><tr><td>Cell A</td></tr></table>' }] },
  } as Record<string, unknown>,
}))

vi.mock('@/hooks/useParserEval', () => ({
  useParserEvalCase: () => ({
    caseDetail: hookState.caseDetail,
    isLoading: false,
    verify: hookState.verify,
    reject: hookState.reject,
    saveTables: hookState.saveTables,
  }),
}))

describe('CaseDetailView', () => {
  it('renders draft tables with edit/accept/reject actions', () => {
    render(<MemoryRouter><CaseDetailView projectId="p1" caseId="c1" /></MemoryRouter>)
    expect(screen.getByText('Cell A')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /accept/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument()
  })

  it('edits a draft table case and saves', async () => {
    render(<MemoryRouter><CaseDetailView projectId="p1" caseId="c1" /></MemoryRouter>)
    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    fireEvent.change(screen.getByLabelText('cell 0,0'), { target: { value: 'z' } })
    fireEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await waitFor(() => expect(hookState.saveTables).toHaveBeenCalled())
    const calls = hookState.saveTables.mock.calls
    const [tablesArg] = calls[calls.length - 1]
    expect((tablesArg as { html: string }[])[0].html).toContain('z')
  })
})
