import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axios from 'axios'
import { ParseRunDeleteDialog } from './ParseRunDeleteDialog'

vi.mock('@/api/parseRuns', () => ({
  deleteParseRun: vi.fn(),
}))

import * as parseRunsApi from '@/api/parseRuns'

describe('ParseRunDeleteDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the confirm message when open', () => {
    render(
      <ParseRunDeleteDialog
        open={true}
        onOpenChange={vi.fn()}
        runId="r1"
        onDeleted={vi.fn()}
      />
    )
    expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^delete$/i })).toBeInTheDocument()
  })

  it('calls onDeleted and closes on successful delete', async () => {
    vi.mocked(parseRunsApi.deleteParseRun).mockResolvedValueOnce(undefined)
    const onDeleted = vi.fn()
    const onOpenChange = vi.fn()
    render(
      <ParseRunDeleteDialog
        open={true}
        onOpenChange={onOpenChange}
        runId="r1"
        onDeleted={onDeleted}
      />
    )
    await userEvent.click(screen.getByRole('button', { name: /^delete$/i }))
    expect(parseRunsApi.deleteParseRun).toHaveBeenCalledWith('r1')
    expect(onDeleted).toHaveBeenCalled()
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('shows blocker counts when the API returns 409', async () => {
    const err = new axios.AxiosError('Conflict')
    Object.assign(err, {
      response: {
        status: 409,
        data: {
          detail: {
            message: 'Parse run has dependent entities.',
            blockers: { index_documents: 2, classification_runs: 0, extraction_results: 0 },
          },
        },
        headers: {},
        config: {},
        statusText: 'Conflict',
      },
    })
    vi.mocked(parseRunsApi.deleteParseRun).mockRejectedValueOnce(err)

    render(
      <ParseRunDeleteDialog
        open={true}
        onOpenChange={vi.fn()}
        runId="r1"
        onDeleted={vi.fn()}
      />
    )
    await userEvent.click(screen.getByRole('button', { name: /^delete$/i }))
    expect(await screen.findByText(/2 index document/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^delete$/i })).not.toBeInTheDocument()
  })
})
