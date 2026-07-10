import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { useProbe } from './useProbe'
import * as api from '@/api/probeReport'
import type { ProbeReport } from '@/types/probeReport'

function makeReport(documentId: string): ProbeReport {
  return {
    document_id: documentId, filename: 'f.pdf', page_count: 1, inspection: {},
    pages: [], suggestion: null, duration_ms: 1, probed_at: 't',
  }
}

describe('useProbe', () => {
  it('runs a probe and exposes the report', async () => {
    vi.spyOn(api, 'probeDocument').mockResolvedValue(makeReport('d1'))
    const { result } = renderHook(() => useProbe())
    await act(async () => { await result.current.run('d1') })
    await waitFor(() => expect(result.current.report?.document_id).toBe('d1'))
    expect(result.current.isLoading).toBe(false)
  })

  it('clears the previous report as soon as a new probe starts', async () => {
    const spy = vi.spyOn(api, 'probeDocument')
    spy.mockResolvedValueOnce(makeReport('a'))
    const { result } = renderHook(() => useProbe())
    await act(async () => { await result.current.run('a') })
    expect(result.current.report?.document_id).toBe('a')

    let resolveB: (r: ProbeReport) => void = () => {}
    spy.mockImplementationOnce(() => new Promise((res) => { resolveB = res }))
    act(() => { void result.current.run('b') })

    // Stale results must not linger while the new probe is in flight.
    expect(result.current.report).toBeNull()
    expect(result.current.isLoading).toBe(true)

    await act(async () => { resolveB(makeReport('b')) })
    expect(result.current.report?.document_id).toBe('b')
  })

  it('ignores a stale response from a superseded probe', async () => {
    const spy = vi.spyOn(api, 'probeDocument')
    let resolveA: (r: ProbeReport) => void = () => {}
    let resolveB: (r: ProbeReport) => void = () => {}
    spy.mockImplementationOnce(() => new Promise((res) => { resolveA = res })) // slow doc
    spy.mockImplementationOnce(() => new Promise((res) => { resolveB = res })) // fast doc

    const { result } = renderHook(() => useProbe())
    act(() => { void result.current.run('a') })
    act(() => { void result.current.run('b') })

    await act(async () => { resolveB(makeReport('b')) })
    expect(result.current.report?.document_id).toBe('b')

    // The superseded probe finally lands — it must not clobber the current one.
    await act(async () => { resolveA(makeReport('a')) })
    expect(result.current.report?.document_id).toBe('b')
    expect(result.current.isLoading).toBe(false)
  })
})
