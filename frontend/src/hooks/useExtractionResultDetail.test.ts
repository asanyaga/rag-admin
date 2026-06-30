import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useExtractionResultDetail } from './useExtractionResultDetail'
import * as extractionApi from '@/api/extraction'
import type { ExtractionResult } from '@/types/extraction'

vi.mock('@/api/extraction')

function makeResult(overrides: Partial<ExtractionResult> = {}): ExtractionResult {
  return {
    id: 'r1',
    documentId: 'd1',
    extractionSchemaId: 's1',
    schemaDefinitionSnapshot: {},
    extractionMethod: 'llm',
    config: null,
    structuredData: null,
    extractionMetadata: null,
    citations: null,
    providerResponseRaw: null,
    sourceParseRunId: null,
    status: 'completed',
    statusMessage: null,
    startedAt: null,
    timeoutMinutes: null,
    createdBy: 'u1',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('useExtractionResultDetail', () => {
  beforeEach(() => { vi.clearAllMocks() })
  afterEach(() => { vi.useRealTimers() })

  it('fetches and returns a completed result without polling', async () => {
    vi.mocked(extractionApi.getExtractionResult).mockResolvedValue(makeResult())
    const { result } = renderHook(() => useExtractionResultDetail('r1'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.result?.id).toBe('r1')
    expect(result.current.result?.status).toBe('completed')
    expect(result.current.error).toBeNull()
  })

  it('polls while result is pending and stops when completed', async () => {
    vi.useFakeTimers()
    const pending = makeResult({ status: 'pending' })
    const completed = makeResult({ status: 'completed' })
    vi.mocked(extractionApi.getExtractionResult)
      .mockResolvedValueOnce(pending)
      .mockResolvedValueOnce(completed)

    const { result } = renderHook(() => useExtractionResultDetail('r1'))
    await act(async () => { await Promise.resolve() })
    expect(result.current.result?.status).toBe('pending')

    // Advance timer to trigger poll
    await act(async () => { vi.advanceTimersByTime(3_100) })
    await waitFor(() => expect(result.current.result?.status).toBe('completed'))

    // Polling should have stopped — no more calls after reaching 2 total
    const callCount = vi.mocked(extractionApi.getExtractionResult).mock.calls.length
    await act(async () => { vi.advanceTimersByTime(6_000) })
    expect(vi.mocked(extractionApi.getExtractionResult).mock.calls.length).toBe(callCount)
  })

  it('sets error when fetch fails', async () => {
    vi.mocked(extractionApi.getExtractionResult).mockRejectedValue(new Error('Not found'))
    const { result } = renderHook(() => useExtractionResultDetail('r1'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBe('Not found')
    expect(result.current.result).toBeNull()
  })

  it('returns null result and does not fetch when resultId is null', () => {
    const { result } = renderHook(() => useExtractionResultDetail(null))
    expect(result.current.result).toBeNull()
    expect(result.current.isLoading).toBe(false)
    expect(extractionApi.getExtractionResult).not.toHaveBeenCalled()
  })
})
