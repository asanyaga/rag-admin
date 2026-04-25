import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import * as api from '@/api/parseRuns'
import { useParseRunRawPayload } from './useParseRunRawPayload'

vi.mock('@/api/parseRuns', () => ({
  getRawPayload: vi.fn(),
}))

describe('useParseRunRawPayload', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches and exposes the raw payload', async () => {
    vi.mocked(api.getRawPayload).mockResolvedValue({
      rawPayload: { hello: 'world' },
    })

    const { result } = renderHook(() => useParseRunRawPayload('run-1'))

    await waitFor(() => {
      expect(result.current.rawPayload).toEqual({ hello: 'world' })
    })
    expect(result.current.isLoading).toBe(false)
    expect(result.current.error).toBeNull()
    expect(api.getRawPayload).toHaveBeenCalledWith('run-1')
  })

  it('exposes null when the backend returns null', async () => {
    vi.mocked(api.getRawPayload).mockResolvedValue({ rawPayload: null })
    const { result } = renderHook(() => useParseRunRawPayload('run-2'))
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.rawPayload).toBeNull()
  })

  it('captures errors', async () => {
    vi.mocked(api.getRawPayload).mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => useParseRunRawPayload('run-3'))
    await waitFor(() => expect(result.current.error).toBe('boom'))
    expect(result.current.rawPayload).toBeUndefined()
  })

  it('does not fetch when parseRunId is null', () => {
    renderHook(() => useParseRunRawPayload(null))
    expect(api.getRawPayload).not.toHaveBeenCalled()
  })
})
