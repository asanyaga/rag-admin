import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import ProbePage from './ProbePage'

vi.mock('@/contexts/ProjectContext', () => ({ useProject: () => ({ currentProject: { id: 'p1', name: 'Proj' } }) }))
vi.mock('@/hooks/useDocuments', () => ({ useDocuments: () => ({ documents: [], isLoading: false, uploadDocument: vi.fn() }) }))
vi.mock('@/hooks/useFolders', () => ({ useFolders: () => ({ folders: [] }) }))

describe('ProbePage', () => {
  it('shows the empty state prompting document selection', () => {
    render(<MemoryRouter><ProbePage /></MemoryRouter>)
    expect(screen.getByText(/Select a document/i)).toBeInTheDocument()
  })
})
