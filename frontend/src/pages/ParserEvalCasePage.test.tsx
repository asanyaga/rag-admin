import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import ParserEvalCasePage from './ParserEvalCasePage'

vi.mock('@/contexts/ProjectContext', () => ({
  useProject: () => ({ currentProject: { id: 'p1' } }),
}))
vi.mock('@/hooks/useSourceDocuments', () => ({
  useSourceDocuments: () => ({ sourceDocuments: [{ id: 'doc1', filename: 'a.pdf' }] }),
}))
vi.mock('@/hooks/useParserEval', () => ({
  useParserEvalCases: () => ({ createCase: vi.fn(), bootstrapTableCase: vi.fn() }),
  useParserEvalCase: () => ({ caseDetail: null, isLoading: false, verify: vi.fn(), reject: vi.fn() }),
}))

describe('ParserEvalCasePage (new mode)', () => {
  it('shows the dimension selector when authoring a new case', () => {
    render(
      <MemoryRouter initialEntries={['/evaluation/parser/cases/new']}>
        <Routes><Route path="/evaluation/parser/cases/new" element={<ParserEvalCasePage />} /></Routes>
      </MemoryRouter>,
    )
    expect(screen.getByText(/New case/i)).toBeInTheDocument()
    expect(screen.getByText(/Dimension/i)).toBeInTheDocument()
  })
})
