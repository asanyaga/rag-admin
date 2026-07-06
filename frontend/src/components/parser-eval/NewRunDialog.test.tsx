import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

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

describe('NewRunDialog', () => {
  it('disables create until a case and an adapter are selected', () => {
    const onCreate = vi.fn()
    render(<NewRunDialog open onOpenChange={vi.fn()} projectId="p1" onCreate={onCreate} />)
    const createBtn = screen.getByRole('button', { name: /^run$/i })
    expect(createBtn).toBeDisabled()
    fireEvent.click(screen.getByLabelText('acme.pdf')) // select case
    fireEvent.click(screen.getByLabelText('Docling'))  // select adapter
    expect(createBtn).not.toBeDisabled()
  })
})
