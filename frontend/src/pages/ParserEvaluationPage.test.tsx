import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ParserEvaluationPage from './ParserEvaluationPage'

vi.mock('@/contexts/ProjectContext', () => ({
  useProject: () => ({ currentProject: { id: 'proj-1', name: 'Test Project' } }),
}))
vi.mock('@/components/parser-eval/ParserEvalCasesTab', () => ({
  ParserEvalCasesTab: () => <div>cases-tab</div>,
}))
vi.mock('@/components/parser-eval/ParserEvalRunsTab', () => ({
  ParserEvalRunsTab: () => <div>runs-tab</div>,
}))

describe('ParserEvaluationPage', () => {
  it('renders heading and both tabs', () => {
    render(<MemoryRouter><ParserEvaluationPage /></MemoryRouter>)
    expect(screen.getByText('Parser Evaluation')).toBeInTheDocument()
    expect(screen.getByText('Cases')).toBeInTheDocument()
    expect(screen.getByText('Runs')).toBeInTheDocument()
  })
})
