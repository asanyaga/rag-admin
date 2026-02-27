import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '@/test/test-utils'
import { EvalRunsTab } from './EvalRunsTab'
import { buildEvalRun } from '@/test/builders'

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

beforeEach(() => {
  vi.clearAllMocks()
})

const defaultProps = {
  runs: [],
  isLoading: false,
  onDelete: vi.fn().mockResolvedValue(undefined),
}

describe('EvalRunsTab — Experiment column', () => {
  it('renders Experiment column header', () => {
    render(<EvalRunsTab {...defaultProps} runs={[buildEvalRun()]} />)

    expect(screen.getByText('Experiment')).toBeInTheDocument()
  })

  it('shows experiment name for linked run', () => {
    const run = buildEvalRun({
      experimentId: 'exp-1',
      experimentName: 'My Experiment',
    })

    render(<EvalRunsTab {...defaultProps} runs={[run]} />)

    expect(screen.getByText('My Experiment')).toBeInTheDocument()
  })

  it('shows dash in experiment column for ungrouped run', () => {
    const run = buildEvalRun({
      experimentId: undefined,
      experimentName: undefined,
    })

    render(<EvalRunsTab {...defaultProps} runs={[run]} />)

    // The experiment column cell has a muted-foreground span with "—"
    const dashSpans = screen.getAllByText('—')
    // At least one should be in the experiment column (class includes text-muted-foreground)
    const experimentDash = dashSpans.find(
      (el) => el.classList.contains('text-muted-foreground') && el.closest('td')
    )
    expect(experimentDash).toBeTruthy()
  })

  it('navigates to experiment when experiment name is clicked', async () => {
    const user = userEvent.setup()
    const run = buildEvalRun({
      experimentId: 'exp-42',
      experimentName: 'Clickable Exp',
    })

    render(<EvalRunsTab {...defaultProps} runs={[run]} />)

    await user.click(screen.getByText('Clickable Exp'))

    expect(mockNavigate).toHaveBeenCalledWith('/evaluation/experiments/exp-42')
  })

  it('experiment name has clickable styling', () => {
    const run = buildEvalRun({
      experimentId: 'exp-1',
      experimentName: 'Styled Exp',
    })

    render(<EvalRunsTab {...defaultProps} runs={[run]} />)

    const expLink = screen.getByText('Styled Exp')
    expect(expLink.className).toContain('text-primary')
    expect(expLink.className).toContain('cursor-pointer')
  })
})
