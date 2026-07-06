import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('@/hooks/useParserEval', () => ({
  useParserEvalCases: () => ({
    cases: [{ id: 'c1', sourceDocumentId: 's1', dimension: 'text', sourceMethod: 'human', reviewStatus: 'draft', createdAt: 'x' }],
    isLoading: false, error: null, fetchCases: vi.fn(), createCase: vi.fn(),
  }),
}))
vi.mock('@/hooks/useSourceDocuments', () => ({
  useSourceDocuments: () => ({ sourceDocuments: [{ id: 's1', filename: 'acme.pdf' }], isLoading: false, error: null, refresh: vi.fn() }),
}))

import { NewRunDialog } from './NewRunDialog'

function setup(onCreate = vi.fn()) {
  render(<NewRunDialog open onOpenChange={vi.fn()} projectId="p1" onCreate={onCreate} />)
  return onCreate
}

describe('NewRunDialog', () => {
  it('enables Run once a case and a variant are added', () => {
    setup()
    const runBtn = screen.getByRole('button', { name: /^run$/i })
    expect(runBtn).toBeDisabled()
    fireEvent.click(screen.getByLabelText('acme.pdf'))
    fireEvent.click(screen.getByRole('button', { name: /add variant/i }))
    expect(runBtn).not.toBeDisabled()
  })

  it('blocks duplicate variants and re-enables after removing one', () => {
    setup()
    fireEvent.click(screen.getByLabelText('acme.pdf'))
    const addBtn = screen.getByRole('button', { name: /add variant/i })
    fireEvent.click(addBtn)
    fireEvent.click(addBtn) // two identical docling/{} variants
    expect(screen.getByText(/duplicate variant/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^run$/i })).toBeDisabled()
    fireEvent.click(screen.getAllByRole('button', { name: /remove variant/i })[0])
    expect(screen.queryByText(/duplicate variant/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^run$/i })).not.toBeDisabled()
  })

  it('submits variants as { adapter, config }', async () => {
    const onCreate = setup()
    fireEvent.click(screen.getByLabelText('acme.pdf'))
    fireEvent.click(screen.getByRole('button', { name: /add variant/i }))
    fireEvent.click(screen.getByRole('button', { name: /^run$/i }))
    await waitFor(() =>
      expect(onCreate).toHaveBeenCalledWith({
        name: undefined,
        evalCaseIds: ['c1'],
        variants: [{ adapter: 'docling', config: {} }],
      })
    )
  })
})
