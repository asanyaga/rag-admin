import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ExtractionEvaluationPage from './ExtractionEvaluationPage'

vi.mock('@/contexts/ProjectContext', () => ({
  useProject: () => ({ currentProject: { id: 'proj-1', name: 'Test Project' } }),
}))

vi.mock('@/components/extraction-eval/ExtractionEvalRunsTab', () => ({
  ExtractionEvalRunsTab: () => <div>runs-tab</div>,
}))

vi.mock('@/components/extraction-ground-truth/ExtractionGroundTruthTab', () => ({
  ExtractionGroundTruthTab: () => <div>ground-truth-tab</div>,
}))

describe('ExtractionEvaluationPage', () => {
  it('renders page heading and both tabs', () => {
    render(
      <MemoryRouter>
        <ExtractionEvaluationPage />
      </MemoryRouter>
    )
    expect(screen.getByText('Extraction Evaluation')).toBeInTheDocument()
    expect(screen.getByText('Runs')).toBeInTheDocument()
    expect(screen.getByText('Ground Truth')).toBeInTheDocument()
  })
})
