import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { BlockConfigPanel } from './BlockConfigPanel'

describe('BlockConfigPanel', () => {
  const baseConfig = {
    groupByHeading: true,
    maxBlocksPerChunk: 10,
    blockRoleFilter: null,
  }

  it('renders group-by-heading toggle, max-blocks slider, and role-filter section', () => {
    render(<BlockConfigPanel config={baseConfig} onUpdate={vi.fn()} />)
    expect(screen.getByLabelText(/group by heading/i)).toBeChecked()
    expect(screen.getByText(/max blocks per chunk/i)).toBeInTheDocument()
    expect(screen.getByText(/block role filter/i)).toBeInTheDocument()
  })

  it('calls onUpdate when group-by-heading is toggled', async () => {
    const onUpdate = vi.fn()
    render(<BlockConfigPanel config={baseConfig} onUpdate={onUpdate} />)
    await userEvent.click(screen.getByLabelText(/group by heading/i))
    expect(onUpdate).toHaveBeenCalledWith('groupByHeading', false)
  })

  it('calls onUpdate with role list when a role chip is selected', async () => {
    const onUpdate = vi.fn()
    render(<BlockConfigPanel config={baseConfig} onUpdate={onUpdate} />)
    await userEvent.click(screen.getByRole('button', { name: /^table$/i }))
    expect(onUpdate).toHaveBeenCalledWith('blockRoleFilter', ['table'])
  })

  it('shows existing role filter as selected', () => {
    render(
      <BlockConfigPanel
        config={{ ...baseConfig, blockRoleFilter: ['table', 'paragraph'] }}
        onUpdate={vi.fn()}
      />
    )
    expect(screen.getByRole('button', { name: /^table$/i })).toHaveAttribute(
      'aria-pressed', 'true'
    )
    expect(screen.getByRole('button', { name: /^paragraph$/i })).toHaveAttribute(
      'aria-pressed', 'true'
    )
  })
})
