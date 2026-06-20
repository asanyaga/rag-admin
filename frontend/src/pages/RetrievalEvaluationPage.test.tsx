import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import RetrievalEvaluationPage from './RetrievalEvaluationPage'

vi.mock('@/contexts/ProjectContext', () => ({
  useProject: () => ({ currentProject: { id: 'proj-1', name: 'Test Project' } }),
}))

vi.mock('@/hooks/useEvalRuns', () => ({
  useEvalRuns: () => ({ runs: [], isLoading: false, deleteRun: vi.fn() }),
}))

vi.mock('@/hooks/useExperiments', () => ({
  useExperiments: () => ({
    experiments: [],
    isLoading: false,
    createExperiment: vi.fn(),
    deleteExperiment: vi.fn(),
  }),
}))

vi.mock('@/hooks/useGoldenSets', () => ({
  useGoldenSets: () => ({
    goldenSets: [],
    isLoading: false,
    createGoldenSet: vi.fn(),
    deleteGoldenSet: vi.fn(),
  }),
}))

describe('RetrievalEvaluationPage', () => {
  it('renders page heading and all three tabs', () => {
    render(
      <MemoryRouter>
        <RetrievalEvaluationPage />
      </MemoryRouter>
    )
    expect(screen.getByText('Retrieval Evaluation')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Runs' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Experiments' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Golden Sets' })).toBeInTheDocument()
  })
})
