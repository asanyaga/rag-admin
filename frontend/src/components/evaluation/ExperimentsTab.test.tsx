import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '@/test/test-utils'
import { ExperimentsTab } from './ExperimentsTab'
import { buildExperiment, buildEvalRun, buildEvalRunMetrics } from '@/test/builders'
import type { Experiment, CreateExperimentRequest } from '@/types/experiment'

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
  experiments: [] as Experiment[],
  isLoading: false,
  onCreate: vi.fn<(data: CreateExperimentRequest) => Promise<Experiment>>().mockResolvedValue(
    buildExperiment()
  ),
  onDelete: vi.fn<(id: string) => Promise<void>>().mockResolvedValue(undefined),
}

describe('ExperimentsTab', () => {
  it('renders loading state', () => {
    render(<ExperimentsTab {...defaultProps} isLoading={true} />)
    // Loader2 spinner should be present (an SVG with animate-spin)
    const spinner = document.querySelector('.animate-spin')
    expect(spinner).toBeTruthy()
  })

  it('renders empty state', () => {
    render(<ExperimentsTab {...defaultProps} experiments={[]} />)
    expect(screen.getByText('No experiments yet.')).toBeInTheDocument()
  })

  it('renders experiments table with correct data', () => {
    const experiments = [
      buildExperiment({ id: 'e1', name: 'Exp A', runCount: 3, status: 'active' }),
      buildExperiment({ id: 'e2', name: 'Exp B', runCount: 0, status: 'concluded' }),
    ]

    render(<ExperimentsTab {...defaultProps} experiments={experiments} />)

    expect(screen.getByText('Exp A')).toBeInTheDocument()
    expect(screen.getByText('Exp B')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('active')).toBeInTheDocument()
    expect(screen.getByText('concluded')).toBeInTheDocument()
  })

  it('navigates to experiment detail when row is clicked', async () => {
    const experiments = [buildExperiment({ id: 'exp-123' })]
    const user = userEvent.setup()

    render(<ExperimentsTab {...defaultProps} experiments={experiments} />)

    const row = screen.getByText('Test Experiment').closest('tr')!
    await user.click(row)

    expect(mockNavigate).toHaveBeenCalledWith('/evaluation/experiments/exp-123')
  })

  it('opens create dialog when New Experiment is clicked', async () => {
    const user = userEvent.setup()
    render(<ExperimentsTab {...defaultProps} />)

    // The button in the toolbar
    const buttons = screen.getAllByRole('button')
    const newExpButton = buttons.find((b) => b.textContent?.includes('New Experiment'))!
    await user.click(newExpButton)

    // Dialog should now be open with a Name input
    const nameInput = await screen.findByLabelText('Name')
    expect(nameInput).toBeInTheDocument()
  })

  it('calls onDelete when delete button is clicked', async () => {
    const onDelete = vi.fn<(id: string) => Promise<void>>().mockResolvedValue(undefined)
    const experiments = [buildExperiment({ id: 'e1' })]
    const user = userEvent.setup()

    render(
      <ExperimentsTab {...defaultProps} experiments={experiments} onDelete={onDelete} />
    )

    // The delete button is the last cell in the row — find via svg icon
    const trashIcon = document.querySelector('.lucide-trash-2')
    const deleteButton = trashIcon?.closest('button')
    expect(deleteButton).toBeTruthy()
    await user.click(deleteButton!)

    expect(onDelete).toHaveBeenCalledWith('e1')
  })

  it('displays baseline F1 when present', () => {
    const experiments = [
      buildExperiment({
        id: 'e1',
        baselineRun: buildEvalRun({
          metrics: buildEvalRunMetrics({ avgF1: 0.85 }),
        }),
      }),
    ]

    render(<ExperimentsTab {...defaultProps} experiments={experiments} />)

    expect(screen.getByText('85.0%')).toBeInTheDocument()
  })

  it('displays dash for missing baseline F1', () => {
    const experiments = [buildExperiment({ id: 'e1', baselineRun: null })]

    render(<ExperimentsTab {...defaultProps} experiments={experiments} />)

    // The formatMetric should show "—" for null
    const cells = screen.getAllByRole('cell')
    const f1Cell = cells.find((c) => c.textContent === '—')
    expect(f1Cell).toBeTruthy()
  })
})
