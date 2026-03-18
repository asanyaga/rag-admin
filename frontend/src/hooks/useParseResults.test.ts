import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useParseResults } from './useParseResults'
import { buildParseResult, buildParseResultListItem } from '@/test/builders'

// Mock the API module
vi.mock('@/api/parsing', () => ({
  listParseResults: vi.fn(),
  getParseResult: vi.fn(),
  reparseDocument: vi.fn(),
}))

import * as api from '@/api/parsing'

const mockListParseResults = vi.mocked(api.listParseResults)
const mockGetParseResult = vi.mocked(api.getParseResult)
const mockReparseDocument = vi.mocked(api.reparseDocument)

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useParseResults', () => {
  it('fetches parse results on mount when documentId is set', async () => {
    const items = [
      buildParseResultListItem({ id: 'pr-1' }),
      buildParseResultListItem({ id: 'pr-2' }),
    ]
    mockListParseResults.mockResolvedValue(items)

    const { result } = renderHook(() => useParseResults('doc-1'))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })
    expect(result.current.parseResults).toHaveLength(2)
    expect(mockListParseResults).toHaveBeenCalledWith('doc-1')
  })

  it('does not fetch when documentId is null', async () => {
    const { result } = renderHook(() => useParseResults(null))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })
    expect(result.current.parseResults).toEqual([])
    expect(mockListParseResults).not.toHaveBeenCalled()
  })

  it('selectParseResult fetches full result', async () => {
    mockListParseResults.mockResolvedValue([
      buildParseResultListItem({ id: 'pr-1' }),
    ])
    const fullResult = buildParseResult({ id: 'pr-1' })
    mockGetParseResult.mockResolvedValue(fullResult)

    const { result } = renderHook(() => useParseResults('doc-1'))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    await act(async () => {
      await result.current.selectParseResult('pr-1')
    })

    expect(result.current.selectedResult).toEqual(fullResult)
    expect(mockGetParseResult).toHaveBeenCalledWith('pr-1')
  })

  it('reparseDocument calls API and refreshes list', async () => {
    mockListParseResults.mockResolvedValue([])
    const newResult = buildParseResult({ id: 'pr-new', status: 'pending' })
    mockReparseDocument.mockResolvedValue(newResult)

    const { result } = renderHook(() => useParseResults('doc-1'))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    await act(async () => {
      await result.current.reparseDocument('llamaparse', { tier: 'agentic' })
    })

    expect(mockReparseDocument).toHaveBeenCalledWith('doc-1', 'llamaparse', {
      tier: 'agentic',
    })
    // Should have refreshed the list
    expect(mockListParseResults).toHaveBeenCalledTimes(2) // initial + refresh
  })

  it('handles fetch error', async () => {
    mockListParseResults.mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useParseResults('doc-1'))

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })
    expect(result.current.error).toBe('Network error')
  })
})
