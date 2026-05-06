import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useClassificationRunBlocks } from './useClassificationRuns'
import type { AnnotatedBlock } from '@/types/classification'

vi.mock('@/api/classification', () => ({
  getClassificationRunBlocks: vi.fn(),
}))

import * as api from '@/api/classification'

const mockGetBlocks = vi.mocked(api.getClassificationRunBlocks)

const mockBlocks: AnnotatedBlock[] = [
  { blockId: 'b-1', pageIndex: 0, role: 'paragraph', text: 'Hello', markdown: null, label: 'intro' },
  { blockId: 'b-2', pageIndex: 1, role: 'paragraph', text: 'World', markdown: null, label: null },
]

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useClassificationRunBlocks', () => {
  it('fetches blocks and returns them on success', async () => {
    mockGetBlocks.mockResolvedValue(mockBlocks)
    const { result } = renderHook(() => useClassificationRunBlocks('run-1'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.blocks).toEqual(mockBlocks)
    expect(result.current.error).toBeNull()
    expect(mockGetBlocks).toHaveBeenCalledWith('run-1')
  })

  it('sets error when fetch fails', async () => {
    mockGetBlocks.mockRejectedValue(new Error('Network error'))
    const { result } = renderHook(() => useClassificationRunBlocks('run-1'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.error).toBe('Network error')
    expect(result.current.blocks).toEqual([])
  })

  it('does not fetch when runId is null', () => {
    const { result } = renderHook(() => useClassificationRunBlocks(null))
    expect(result.current.isLoading).toBe(false)
    expect(result.current.blocks).toEqual([])
    expect(mockGetBlocks).not.toHaveBeenCalled()
  })
})
