import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import * as api from '@/api/parseAgent'
import { useParseAgentRuns } from './useParseAgentRuns'
import type { ParseAgentRunSummary } from '@/types/parseAgent'

vi.mock('@/api/parseAgent', () => ({
  listParseAgentRuns: vi.fn(),
  startParseAgentRun: vi.fn(),
}))

function summary(id = 'run-1'): ParseAgentRunSummary {
  return {
    id,
    projectId: 'proj-1',
    sourceDocumentId: 'src-1',
    status: 'completed',
    startedAt: '2026-07-17T10:00:00Z',
    finishedAt: '2026-07-17T10:00:05Z',
    error: null,
  }
}

describe('useParseAgentRuns', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('lists runs for a projectId', async () => {
    vi.mocked(api.listParseAgentRuns).mockImplementation(async () => [
      summary('run-1'),
    ])
    const { result } = renderHook(() => useParseAgentRuns('proj-1'))
    await waitFor(() => expect(result.current.runs).toHaveLength(1))
    expect(result.current.runs[0].id).toBe('run-1')
    expect(api.listParseAgentRuns).toHaveBeenCalledWith('proj-1')
  })

  it('does not fetch when projectId is null', () => {
    renderHook(() => useParseAgentRuns(null))
    expect(api.listParseAgentRuns).not.toHaveBeenCalled()
  })

  it('startRun returns the new runId and triggers a list refetch', async () => {
    vi.mocked(api.listParseAgentRuns).mockImplementation(async () => [])
    vi.mocked(api.startParseAgentRun).mockImplementation(async () => ({
      runId: 'run-new',
    }))
    const { result } = renderHook(() => useParseAgentRuns('proj-1'))
    await waitFor(() =>
      expect(api.listParseAgentRuns).toHaveBeenCalledTimes(1)
    )

    const file = new File(['content'], 'doc.pdf')
    let runId = ''
    await act(async () => {
      runId = await result.current.startRun(file)
    })

    expect(runId).toBe('run-new')
    await waitFor(() =>
      expect(api.listParseAgentRuns).toHaveBeenCalledTimes(2)
    )
  })

  it('surfaces an error when startParseAgentRun rejects', async () => {
    vi.mocked(api.listParseAgentRuns).mockImplementation(async () => [])
    vi.mocked(api.startParseAgentRun).mockImplementation(async () => {
      throw new Error('upload failed')
    })
    const { result } = renderHook(() => useParseAgentRuns('proj-1'))
    await waitFor(() =>
      expect(api.listParseAgentRuns).toHaveBeenCalledTimes(1)
    )

    const file = new File(['content'], 'doc.pdf')
    await act(async () => {
      await expect(result.current.startRun(file)).rejects.toThrow(
        'upload failed'
      )
    })

    await waitFor(() => expect(result.current.error).toBe('upload failed'))
  })
})
