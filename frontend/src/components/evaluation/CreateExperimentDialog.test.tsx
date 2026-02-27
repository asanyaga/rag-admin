import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '@/test/test-utils'
import { CreateExperimentDialog } from './CreateExperimentDialog'

beforeEach(() => {
  vi.clearAllMocks()
})

const defaultProps = {
  open: true,
  onOpenChange: vi.fn(),
  onCreate: vi.fn().mockResolvedValue(undefined),
}

describe('CreateExperimentDialog', () => {
  it('renders dialog content when open', () => {
    render(<CreateExperimentDialog {...defaultProps} />)

    expect(screen.getByText('New Experiment')).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Description (optional)')).toBeInTheDocument()
  })

  it('does not render content when closed', () => {
    render(<CreateExperimentDialog {...defaultProps} open={false} />)

    expect(screen.queryByLabelText('Name')).not.toBeInTheDocument()
  })

  it('submit button is disabled when name is empty', () => {
    render(<CreateExperimentDialog {...defaultProps} />)

    const createButton = screen.getByRole('button', { name: 'Create' })
    expect(createButton).toBeDisabled()
  })

  it('submit button is enabled when name has text', async () => {
    const user = userEvent.setup()
    render(<CreateExperimentDialog {...defaultProps} />)

    await user.type(screen.getByLabelText('Name'), 'My Experiment')

    const createButton = screen.getByRole('button', { name: 'Create' })
    expect(createButton).toBeEnabled()
  })

  it('calls onCreate with name and description on submit', async () => {
    const user = userEvent.setup()
    render(<CreateExperimentDialog {...defaultProps} />)

    await user.type(screen.getByLabelText('Name'), 'Hypothesis A')
    await user.type(
      screen.getByLabelText('Description (optional)'),
      'Does X improve Y?'
    )
    await user.click(screen.getByRole('button', { name: 'Create' }))

    await waitFor(() => {
      expect(defaultProps.onCreate).toHaveBeenCalledWith({
        name: 'Hypothesis A',
        description: 'Does X improve Y?',
      })
    })
  })

  it('calls onCreate without description when empty', async () => {
    const user = userEvent.setup()
    render(<CreateExperimentDialog {...defaultProps} />)

    await user.type(screen.getByLabelText('Name'), 'Minimal')
    await user.click(screen.getByRole('button', { name: 'Create' }))

    await waitFor(() => {
      expect(defaultProps.onCreate).toHaveBeenCalledWith({
        name: 'Minimal',
        description: undefined,
      })
    })
  })

  it('closes dialog after successful submit', async () => {
    const user = userEvent.setup()
    render(<CreateExperimentDialog {...defaultProps} />)

    await user.type(screen.getByLabelText('Name'), 'Test')
    await user.click(screen.getByRole('button', { name: 'Create' }))

    await waitFor(() => {
      expect(defaultProps.onOpenChange).toHaveBeenCalledWith(false)
    })
  })

  it('clicking cancel closes dialog', async () => {
    const user = userEvent.setup()
    render(<CreateExperimentDialog {...defaultProps} />)

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(defaultProps.onOpenChange).toHaveBeenCalledWith(false)
  })
})
