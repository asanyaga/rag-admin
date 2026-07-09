import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { useProbe } from './useProbe'
import * as api from '@/api/probeReport'

describe('useProbe', () => {
  it('runs a probe and exposes the report', async () => {
    vi.spyOn(api, 'probeDocument').mockResolvedValue({
      document_id: 'd1', filename: 'f.pdf', page_count: 1, inspection: {},
      pages: [], suggestion: null, duration_ms: 1, probed_at: 't',
    })
    const { result } = renderHook(() => useProbe())
    await act(async () => { await result.current.run('d1') })
    await waitFor(() => expect(result.current.report?.document_id).toBe('d1'))
    expect(result.current.isLoading).toBe(false)
  })
})
