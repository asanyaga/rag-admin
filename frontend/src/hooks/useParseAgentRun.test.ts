import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import * as api from '@/api/parseAgent'
import { useParseAgentRun } from './useParseAgentRun'
import type { ParseAgentRunDetail } from '@/types/parseAgent'

vi.mock('@/api/parseAgent', () => ({
  getParseAgentRun: vi.fn(),
}))

function detail(
  status: 'running' | 'completed',
  id = 'run-1'
): ParseAgentRunDetail {
  return {
    run: {
      id,
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

  it('stops polling once the timeout elapses even if the run never finishes', async () => {
    // mockImplementation (not mockResolvedValue) so every poll resolves to a NEW object,
    // as the real axios-backed api does. With a single shared reference React bails out of
    // the re-render, the polling effect never re-runs, and this test cannot detect a
    // timeout guard that resets its start time on each tick.
    vi.mocked(api.getParseAgentRun).mockImplementation(async () => detail('running'))
    const { result } = renderHook(() => useParseAgentRun('run-1'))
    await waitFor(() => expect(result.current.detail?.run.status).toBe('running'))

    await vi.advanceTimersByTimeAsync(10 * 60 * 1000 + 4000)
    const callsAfterTimeout = vi.mocked(api.getParseAgentRun).mock.calls.length

    await vi.advanceTimersByTimeAsync(6000)
    expect(vi.mocked(api.getParseAgentRun).mock.calls.length).toBe(callsAfterTimeout)
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

  it('reports loading immediately on mount', () => {
    // Asserts on the FIRST render, not `result.current` — renderHook flushes effects
    // inside act(), so by the time `result.current` is readable `refetch` has already
    // set isLoading=true. The bug is the frame before that: the detail page's guard
    // runs on the first render, sees isLoading=false + detail=null, and flashes
    // "Run not found." on a perfectly valid run. Capture per-render to see it.
    vi.mocked(api.getParseAgentRun).mockImplementation(
      () => new Promise<ParseAgentRunDetail>(() => {})
    )
    const loadingByRender: boolean[] = []
    renderHook(() => {
      const hook = useParseAgentRun('run-1')
      loadingByRender.push(hook.isLoading)
      return hook
    })
    expect(loadingByRender[0]).toBe(true)
  })

  it('clears the previous run detail when runId changes', async () => {
    // React Router does not remount on a param-only change, so without an explicit
    // reset the previous run's detail stays on screen while the new one is in flight.
    // mockImplementation (not mockResolvedValue) so each call yields a fresh object.
    vi.mocked(api.getParseAgentRun).mockImplementation((id: string) =>
      id === 'run-1'
        ? Promise.resolve(detail('completed', 'run-1'))
        : new Promise<ParseAgentRunDetail>(() => {})
    )

    const { result, rerender } = renderHook(
      ({ runId }) => useParseAgentRun(runId),
      { initialProps: { runId: 'run-1' } }
    )
    await waitFor(() => expect(result.current.detail?.run.id).toBe('run-1'))

    rerender({ runId: 'run-2' })

    expect(result.current.detail).toBeNull()
  })
})
