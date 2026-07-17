import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import * as api from '@/api/parseAgent'
import { useParseAgentRun } from './useParseAgentRun'
import type { ParseAgentRunDetail } from '@/types/parseAgent'

vi.mock('@/api/parseAgent', () => ({
  getParseAgentRun: vi.fn(),
}))

function detail(status: 'running' | 'completed'): ParseAgentRunDetail {
  return {
    run: {
      id: 'run-1',
      projectId: 'proj-1',
      sourceDocumentId: 'src-1',
      status,
      startedAt: '2026-07-17T10:00:00Z',
      finishedAt: status === 'completed' ? '2026-07-17T10:00:05Z' : null,
      error: null,
    },
    steps: [
      {
        id: 'step-1', seq: 0, node: 'parse', phase: 'end', status: 'succeeded',
        inputKeys: ['file_path'], outputKeys: ['parse_run_id'],
        stateDelta: { parse_run_id: 'pr-1' }, message: null,
        durationMs: 4200, createdAt: '2026-07-17T10:00:04Z',
      },
    ],
    graphNodes: ['parse', 'health_check'],
  }
}

describe('useParseAgentRun', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })
  afterEach(() => vi.useRealTimers())

  it('fetches the run detail', async () => {
    vi.mocked(api.getParseAgentRun).mockResolvedValue(detail('completed'))
    const { result } = renderHook(() => useParseAgentRun('run-1'))
    await waitFor(() => expect(result.current.detail?.run.id).toBe('run-1'))
    expect(result.current.detail?.graphNodes).toEqual(['parse', 'health_check'])
    expect(result.current.error).toBeNull()
  })

  it('polls while running and stops once terminal', async () => {
    vi.mocked(api.getParseAgentRun)
      .mockResolvedValueOnce(detail('running'))
      .mockResolvedValue(detail('completed'))

    const { result } = renderHook(() => useParseAgentRun('run-1'))
    await waitFor(() => expect(result.current.detail?.run.status).toBe('running'))

    await vi.advanceTimersByTimeAsync(2000)
    await waitFor(() => expect(result.current.detail?.run.status).toBe('completed'))

    const callsAfterTerminal = vi.mocked(api.getParseAgentRun).mock.calls.length
    await vi.advanceTimersByTimeAsync(6000)
    expect(vi.mocked(api.getParseAgentRun).mock.calls.length).toBe(callsAfterTerminal)
  })

  it('does not fetch when runId is null', () => {
    renderHook(() => useParseAgentRun(null))
    expect(api.getParseAgentRun).not.toHaveBeenCalled()
  })

  it('captures errors', async () => {
    vi.mocked(api.getParseAgentRun).mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => useParseAgentRun('run-1'))
    await waitFor(() => expect(result.current.error).toBe('boom'))
  })
})
