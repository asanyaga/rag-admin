import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useParseRuns } from './useParseRuns'
import type {
  ParsedDocumentDetail,
  ParseRunListItem,
  ParseRunStatus,
} from '@/types/cdm'

vi.mock('@/api/parseRuns', () => ({
  listParseRuns: vi.fn(),
  getParsedDocument: vi.fn(),
}))

import * as api from '@/api/parseRuns'

const mockListParseRuns = vi.mocked(api.listParseRuns)
const mockGetParsedDocument = vi.mocked(api.getParsedDocument)

function buildRun(overrides: Partial<ParseRunListItem> = {}): ParseRunListItem {
  return {
    id: overrides.id ?? 'run-1',
    sourceDocumentId: 'src-1',
    parser: 'llamaparse',
    parserVersion: null,
    representationKind: 'vector_light',
    status: (overrides.status as ParseRunStatus) ?? 'succeeded',
    startedAt: '2026-04-24T10:00:00Z',
    finishedAt: '2026-04-24T10:00:12Z',
    durationMs: 12000,
    inputTokens: 100,
    outputTokens: 50,
    cost: {},
    warnings: [],
    failedPages: [],
    providerRefs: {},
    error: null,
    config: {},
    createdAt: '2026-04-24T10:00:00Z',
    ...overrides,
  }
}

function buildDetail(
  overrides: Partial<ParsedDocumentDetail> = {}
): ParsedDocumentDetail {
  return {
    parseRunId: 'run-1',
    sourceDocumentId: 'src-1',
    pageCount: 1,
    blockCount: 1,
    fullText: 'hello',
    fullMarkdown: '# hello',
    content: { pages: [], blocks: [] },
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useParseRuns', () => {
  it('does not call the API when documentId is null', async () => {
    const { result } = renderHook(() => useParseRuns(null))
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })
    expect(mockListParseRuns).not.toHaveBeenCalled()
  })

  it('auto-selects newest succeeded run and fetches its parsed document', async () => {
    // Backend returns newest-first. r-newest is failed, r-mid is succeeded.
    const runs = [
      buildRun({ id: 'r-newest', status: 'failed' }),
      buildRun({ id: 'r-mid', status: 'succeeded' }),
      buildRun({ id: 'r-oldest', status: 'succeeded' }),
    ]
    mockListParseRuns.mockResolvedValue(runs)
    mockGetParsedDocument.mockResolvedValue(
      buildDetail({ parseRunId: 'r-mid' })
    )

    const { result } = renderHook(() => useParseRuns('doc-1'))
    await waitFor(() => {
      expect(result.current.parseRuns).toHaveLength(3)
    })
    await waitFor(() => {
      expect(result.current.parsedDocument?.parseRunId).toBe('r-mid')
    })
    expect(result.current.selectedRun?.id).toBe('r-mid')
    expect(mockGetParsedDocument).toHaveBeenCalledWith('r-mid')
  })

  it('does not fetch parsed document for failed runs', async () => {
    const runs = [
      buildRun({ id: 'r1', status: 'succeeded' }),
      buildRun({ id: 'r2', status: 'failed' }),
    ]
    mockListParseRuns.mockResolvedValue(runs)
    mockGetParsedDocument.mockResolvedValue(buildDetail())

    const { result } = renderHook(() => useParseRuns('doc-1'))
    await waitFor(() => {
      expect(result.current.selectedRun?.id).toBe('r1')
    })
    expect(mockGetParsedDocument).toHaveBeenCalledTimes(1)

    act(() => {
      result.current.selectRun('r2')
    })
    await waitFor(() => {
      expect(result.current.selectedRun?.id).toBe('r2')
    })
    expect(result.current.parsedDocument).toBeUndefined()
    expect(mockGetParsedDocument).toHaveBeenCalledTimes(1) // no extra call
  })

  it('polls while a run is non-terminal and stops once all terminal', async () => {
    mockListParseRuns
      .mockResolvedValueOnce([buildRun({ id: 'r1', status: 'running' })])
      .mockResolvedValueOnce([buildRun({ id: 'r1', status: 'running' })])
      .mockResolvedValueOnce([buildRun({ id: 'r1', status: 'succeeded' })])
    mockGetParsedDocument.mockResolvedValue(buildDetail({ parseRunId: 'r1' }))

    const { result } = renderHook(() => useParseRuns('doc-1'))
    await waitFor(() => {
      expect(result.current.parseRuns[0]?.status).toBe('running')
    })

    // First poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(mockListParseRuns).toHaveBeenCalledTimes(2)

    // Second poll → run flips to succeeded
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(mockListParseRuns).toHaveBeenCalledTimes(3)
    await waitFor(() => {
      expect(result.current.parseRuns[0]?.status).toBe('succeeded')
    })

    // Polling should have stopped: another tick should NOT call again.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000)
    })
    expect(mockListParseRuns).toHaveBeenCalledTimes(3)
  })
})
