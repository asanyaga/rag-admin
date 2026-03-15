import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useExperiments, useExperimentDetail } from './useExperiments'
import { buildExperiment, buildExperimentDetail, buildEvalRun } from '@/test/builders'
import type { Experiment } from '@/types/experiment'

// Mock the API module
vi.mock('@/api/experiments', () => ({
  listExperiments: vi.fn(),
  createExperiment: vi.fn(),
  deleteExperiment: vi.fn(),
  getExperiment: vi.fn(),
  updateExperiment: vi.fn(),
}))

import * as api from '@/api/experiments'

const mockListExperiments = vi.mocked(api.listExperiments)
const mockCreateExperiment = vi.mocked(api.createExperiment)
const mockDeleteExperiment = vi.mocked(api.deleteExperiment)
const mockGetExperiment = vi.mocked(api.getExperiment)
const mockUpdateExperiment = vi.mocked(api.updateExperiment)

beforeEach(() => {
  vi.clearAllMocks()
})

// ---------------------------------------------------------------------------
// useExperiments
// ---------------------------------------------------------------------------

describe('useExperiments', () => {
  it('fetches experiments on mount when projectId is set', async () => {
    const exps = [buildExperiment({ id: 'e1' }), buildExperiment({ id: 'e2' })]
    mockListExperiments.mockResolvedValue(exps)

    const { result } = renderHook(() => useExperiments('proj-1'))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })
    expect(result.current.experiments).toHaveLength(2)
    expect(mockListExperiments).toHaveBeenCalledWith('proj-1')
  })

  it('does not fetch when projectId is null', async () => {
    const { result } = renderHook(() => useExperiments(null))

    // Give it a tick
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })
    expect(result.current.experiments).toEqual([])
    expect(mockListExperiments).not.toHaveBeenCalled()
  })

  it('createExperiment adds to list and returns experiment', async () => {
    mockListExperiments.mockResolvedValue([])
    const created = buildExperiment({ id: 'new-exp', name: 'New' })
    mockCreateExperiment.mockResolvedValue(created)

    const { result } = renderHook(() => useExperiments('proj-1'))

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    let returned: Experiment | undefined
    await act(async () => {
      returned = await result.current.createExperiment({ name: 'New' })
    })

    expect(returned!.id).toBe('new-exp')
    expect(result.current.experiments).toHaveLength(1)
    expect(result.current.experiments[0].name).toBe('New')
    expect(mockCreateExperiment).toHaveBeenCalledWith('proj-1', { name: 'New' })
  })

  it('deleteExperiment removes from list', async () => {
    const exps = [buildExperiment({ id: 'e1' }), buildExperiment({ id: 'e2' })]
    mockListExperiments.mockResolvedValue(exps)
    mockDeleteExperiment.mockResolvedValue(undefined)

    const { result } = renderHook(() => useExperiments('proj-1'))

    await waitFor(() => expect(result.current.experiments).toHaveLength(2))

    await act(async () => {
      await result.current.deleteExperiment('e1')
    })

    expect(result.current.experiments).toHaveLength(1)
    expect(result.current.experiments[0].id).toBe('e2')
    expect(mockDeleteExperiment).toHaveBeenCalledWith('proj-1', 'e1')
  })

  it('handles fetch error', async () => {
    mockListExperiments.mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useExperiments('proj-1'))

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBe('Network error')
    expect(result.current.experiments).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// useExperimentDetail
// ---------------------------------------------------------------------------

describe('useExperimentDetail', () => {
  it('fetches experiment detail on mount', async () => {
    const detail = buildExperimentDetail({
      id: 'exp-1',
      runs: [buildEvalRun({ id: 'r1' })],
    })
    mockGetExperiment.mockResolvedValue(detail)

    const { result } = renderHook(() => useExperimentDetail('proj-1', 'exp-1'))

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.experiment).not.toBeNull()
    expect(result.current.experiment!.runs).toHaveLength(1)
    expect(result.current.experiment!.variableDiff).toBeDefined()
    expect(mockGetExperiment).toHaveBeenCalledWith('proj-1', 'exp-1')
  })

  it('does not fetch when projectId or experimentId is null', async () => {
    const { result } = renderHook(() => useExperimentDetail(null, null))

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.experiment).toBeNull()
    expect(mockGetExperiment).not.toHaveBeenCalled()
  })

  it('updateExperiment calls API and refreshes', async () => {
    const detail = buildExperimentDetail({ id: 'exp-1', name: 'Original' })
    const updated = buildExperimentDetail({ id: 'exp-1', name: 'Updated' })

    mockGetExperiment
      .mockResolvedValueOnce(detail)   // initial fetch
      .mockResolvedValueOnce(updated)  // refresh after update

    mockUpdateExperiment.mockResolvedValue(buildExperiment({ name: 'Updated' }))

    const { result } = renderHook(() => useExperimentDetail('proj-1', 'exp-1'))

    await waitFor(() => expect(result.current.experiment?.name).toBe('Original'))

    await act(async () => {
      await result.current.updateExperiment({ name: 'Updated' })
    })

    expect(mockUpdateExperiment).toHaveBeenCalledWith('proj-1', 'exp-1', {
      name: 'Updated',
    })

    await waitFor(() => {
      expect(result.current.experiment?.name).toBe('Updated')
    })
  })

  it('sets up polling when runs are active', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })

    const detail = buildExperimentDetail({
      id: 'exp-1',
      runs: [buildEvalRun({ id: 'r1', status: 'running' })],
    })
    const completedDetail = buildExperimentDetail({
      id: 'exp-1',
      runs: [buildEvalRun({ id: 'r1', status: 'completed' })],
    })

    mockGetExperiment
      .mockResolvedValueOnce(detail)
      .mockResolvedValue(completedDetail)

    const { result } = renderHook(() => useExperimentDetail('proj-1', 'exp-1'))

    // Wait for initial fetch
    await vi.waitFor(() => {
      expect(result.current.experiment).not.toBeNull()
    })

    // Advance time to trigger the polling interval (5s)
    await act(async () => {
      vi.advanceTimersByTime(5500)
      // Let the promise resolve
      await vi.advanceTimersByTimeAsync(100)
    })

    // The polling should have triggered at least one additional fetch
    expect(mockGetExperiment.mock.calls.length).toBeGreaterThanOrEqual(2)

    vi.useRealTimers()
  })
})
