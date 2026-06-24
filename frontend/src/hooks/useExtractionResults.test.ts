import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useExtractionResults } from './useExtractionResults'
import * as parseRunsApi from '@/api/parseRuns'
import * as extractionApi from '@/api/extraction'
import type { ParseRunListItem } from '@/types/cdm'

vi.mock('@/api/parseRuns')
vi.mock('@/api/extraction')

const mockParseRuns = vi.mocked(parseRunsApi)
const mockExtraction = vi.mocked(extractionApi)

function makeParseRun(overrides: Partial<ParseRunListItem> = {}): ParseRunListItem {
  return {
    id: 'run-1',
    sourceDocumentId: 'doc-1',
    parser: 'simple',
    parserVersion: null,
    representationKind: 'extract_rich',
    status: 'succeeded',
    startedAt: '2026-06-23T00:00:00Z',
    finishedAt: '2026-06-23T00:01:00Z',
    durationMs: 60000,
    inputTokens: null,
    outputTokens: null,
    cost: {},
    warnings: [],
    failedPages: [],
    providerRefs: {},
    error: null,
    config: { parser: 'simple' },
    createdAt: '2026-06-23T00:00:00Z',
    ...overrides,
  }
}

const fakeExtractionResult = {
  id: 'result-1',
  documentId: 'doc-1',
  extractionSchemaId: 'schema-1',
  schemaDefinitionSnapshot: {},
  extractionMethod: 'llm',
  config: null,
  structuredData: null,
  extractionMetadata: null,
  citations: null,
  providerResponseRaw: null,
  sourceParseRunId: 'run-1',
  status: 'pending' as const,
  statusMessage: null,
  startedAt: null,
  createdBy: 'user-1',
  createdAt: '2026-06-23T00:00:00Z',
  updatedAt: '2026-06-23T00:00:00Z',
  timeoutMinutes: null,
}

const baseRequest = {
  parseConfig: {
    parser: 'simple',
    config: {},
    representationKind: 'extract_rich',
  },
  extractionConfig: {
    extractionSchemaId: 'schema-1',
    extractionMethod: 'llm',
    config: {},
  },
}

beforeEach(() => {
  vi.clearAllMocks()
  mockExtraction.listExtractionResults.mockResolvedValue([])
})

describe('runExtractionWithParse', () => {
  it('reuses existing parse run when config matches — skips createParseRun', async () => {
    const existingRun = makeParseRun({
      id: 'run-match',
      parser: 'simple',
      config: { parser: 'simple' },
      status: 'succeeded',
    })
    mockExtraction.runExtraction.mockResolvedValue(fakeExtractionResult)

    const { result } = renderHook(() => useExtractionResults('doc-1'))

    await act(async () => {
      await result.current.runExtractionWithParse('doc-1', [existingRun], baseRequest)
    })

    expect(mockParseRuns.createParseRun).not.toHaveBeenCalled()
    expect(mockExtraction.runExtraction).toHaveBeenCalledWith(
      expect.objectContaining({ parseRunId: 'run-match' })
    )
  })

  it('creates a new parse run when no matching run exists', async () => {
    mockParseRuns.createParseRun.mockResolvedValue(undefined)
    mockParseRuns.listParseRuns.mockResolvedValue([
      makeParseRun({ id: 'new-run', status: 'succeeded' }),
    ])
    mockParseRuns.getParseRun.mockResolvedValue(
      makeParseRun({ id: 'new-run', status: 'succeeded' })
    )
    mockExtraction.runExtraction.mockResolvedValue({
      ...fakeExtractionResult,
      sourceParseRunId: 'new-run',
    })

    vi.useFakeTimers()
    const { result } = renderHook(() => useExtractionResults('doc-1'))

    await act(async () => {
      const p = result.current.runExtractionWithParse('doc-1', [], baseRequest)
      await vi.runAllTimersAsync()
      return p
    })
    vi.useRealTimers()

    expect(mockParseRuns.createParseRun).toHaveBeenCalledWith(
      'doc-1',
      'simple',
      expect.objectContaining({ representation_kind: 'extract_rich' })
    )
    expect(mockExtraction.runExtraction).toHaveBeenCalledWith(
      expect.objectContaining({ parseRunId: 'new-run' })
    )
  })

  it('sets phase to failed when parse run fails — does not trigger extraction', async () => {
    mockParseRuns.createParseRun.mockResolvedValue(undefined)
    mockParseRuns.listParseRuns.mockResolvedValue([
      makeParseRun({ id: 'bad-run', status: 'failed', error: 'Parse error' }),
    ])
    mockParseRuns.getParseRun.mockResolvedValue(
      makeParseRun({ id: 'bad-run', status: 'failed', error: 'Parse error' })
    )

    vi.useFakeTimers()
    const { result } = renderHook(() => useExtractionResults('doc-1'))

    await act(async () => {
      const p = result.current.runExtractionWithParse('doc-1', [], baseRequest)
      await vi.runAllTimersAsync()
      return p
    })
    vi.useRealTimers()

    expect(result.current.extractionPhase).toBe('failed')
    expect(result.current.phaseError).toBe('Parse error')
    expect(mockExtraction.runExtraction).not.toHaveBeenCalled()
  })

  it('transitions through idle → parsing → done phases for a fresh parse', async () => {
    mockParseRuns.createParseRun.mockResolvedValue(undefined)
    mockParseRuns.listParseRuns.mockResolvedValue([
      makeParseRun({ id: 'r', status: 'succeeded' }),
    ])
    mockParseRuns.getParseRun.mockResolvedValue(
      makeParseRun({ id: 'r', status: 'succeeded' })
    )
    mockExtraction.runExtraction.mockResolvedValue({
      ...fakeExtractionResult,
      sourceParseRunId: 'r',
    })

    vi.useFakeTimers()
    const { result } = renderHook(() => useExtractionResults('doc-1'))
    expect(result.current.extractionPhase).toBe('idle')

    await act(async () => {
      const p = result.current.runExtractionWithParse('doc-1', [], baseRequest)
      await vi.runAllTimersAsync()
      return p
    })
    vi.useRealTimers()

    expect(result.current.extractionPhase).toBe('done')
  })

  it('forwards chunking config to runExtraction', async () => {
    const existingRun = makeParseRun({
      id: 'run-match', parser: 'simple', config: { parser: 'simple' }, status: 'succeeded',
    })
    mockExtraction.runExtraction.mockResolvedValue(fakeExtractionResult)

    const { result } = renderHook(() => useExtractionResults('doc-1'))

    const requestWithChunking = {
      ...baseRequest,
      extractionConfig: {
        ...baseRequest.extractionConfig,
        chunking: { strategy: 'token_budget_pages', config: { maxInputTokens: 6000 }, citationLevel: 'auto' as const },
      },
    }

    await act(async () => {
      await result.current.runExtractionWithParse('doc-1', [existingRun], requestWithChunking)
    })

    expect(mockExtraction.runExtraction).toHaveBeenCalledWith(
      expect.objectContaining({
        chunking: { strategy: 'token_budget_pages', config: { maxInputTokens: 6000 }, citationLevel: 'auto' },
      })
    )
  })
})

describe('clearSelection', () => {
  it('sets selectedResult to null', async () => {
    const fullResult = { ...fakeExtractionResult, id: 'result-1', status: 'completed' as const }
    const listItem = {
      id: 'result-1',
      documentId: 'doc-1',
      extractionSchemaId: 'schema-1',
      extractionMethod: 'llm',
      status: 'completed' as const,
      statusMessage: null,
      timeoutMinutes: null,
      createdAt: '2026-06-24T00:00:00Z',
    }
    mockExtraction.listExtractionResults.mockResolvedValue([listItem])
    mockExtraction.getExtractionResult.mockResolvedValue(fullResult)

    const { result } = renderHook(() => useExtractionResults('doc-1'))
    await act(async () => {})

    await act(async () => { await result.current.selectResult('result-1') })
    expect(result.current.selectedResult?.id).toBe('result-1')

    act(() => { result.current.clearSelection() })
    expect(result.current.selectedResult).toBeNull()
  })
})

describe('deleteResult', () => {
  it('removes the deleted item from results state', async () => {
    const listItem = {
      id: 'result-1',
      documentId: 'doc-1',
      extractionSchemaId: 'schema-1',
      extractionMethod: 'llm',
      status: 'completed' as const,
      statusMessage: null,
      timeoutMinutes: null,
      createdAt: '2026-06-24T00:00:00Z',
    }
    mockExtraction.listExtractionResults.mockResolvedValue([listItem])
    mockExtraction.deleteExtractionResult = vi.fn().mockResolvedValue(undefined)

    const { result } = renderHook(() => useExtractionResults('doc-1'))
    await act(async () => {})

    expect(result.current.results).toHaveLength(1)

    await act(async () => {
      await result.current.deleteResult('result-1')
    })

    expect(result.current.results).toHaveLength(0)
    expect(mockExtraction.deleteExtractionResult).toHaveBeenCalledWith('result-1')
  })

  it('clears selectedResult when the deleted item was selected', async () => {
    const listItem = {
      id: 'result-1',
      documentId: 'doc-1',
      extractionSchemaId: 'schema-1',
      extractionMethod: 'llm',
      status: 'completed' as const,
      statusMessage: null,
      timeoutMinutes: null,
      createdAt: '2026-06-24T00:00:00Z',
    }
    const fullResult = { ...fakeExtractionResult, id: 'result-1', status: 'completed' as const }
    mockExtraction.listExtractionResults.mockResolvedValue([listItem])
    mockExtraction.getExtractionResult.mockResolvedValue(fullResult)
    mockExtraction.deleteExtractionResult = vi.fn().mockResolvedValue(undefined)

    const { result } = renderHook(() => useExtractionResults('doc-1'))
    await act(async () => {})

    await act(async () => { await result.current.selectResult('result-1') })
    expect(result.current.selectedResult?.id).toBe('result-1')

    await act(async () => { await result.current.deleteResult('result-1') })
    expect(result.current.selectedResult).toBeNull()
  })
})

describe('extraction polling timeout', () => {
  // timeoutMinutes: 1 → deadline = 60000ms; interval = 3000ms
  // interval fires at 3s, 6s, ..., 60s (20 times — all before deadline)
  // interval fires at 63s (21st) — this one is past the deadline → timeout
  const INTERVAL = 3_000
  const ONE_MINUTE_MS = 60_000

  it('uses timeoutMinutes from result when set — stops polling after that many minutes', async () => {
    vi.useFakeTimers()

    const pendingResult = { ...fakeExtractionResult, timeoutMinutes: 1 }
    mockExtraction.listExtractionResults.mockResolvedValue([pendingResult])

    const { result } = renderHook(() => useExtractionResults('doc-1'))
    // Let initial fetch run and interval start
    await act(async () => {})

    // Advance to just before the timeout — still pending
    act(() => { vi.advanceTimersByTime(ONE_MINUTE_MS - 1) })
    await act(async () => {})
    expect(result.current.results[0]?.status).toBe('pending')

    // Advance past the timeout (next interval fires after 60s deadline)
    act(() => { vi.advanceTimersByTime(INTERVAL + 1) })
    await act(async () => {})

    expect(result.current.results[0]?.status).toBe('failed')
    expect(result.current.results[0]?.statusMessage).toBe('Processing timeout')

    vi.useRealTimers()
  })

  it('falls back to 10-minute deadline when timeoutMinutes is null', async () => {
    vi.useFakeTimers()

    const pendingResult = { ...fakeExtractionResult, timeoutMinutes: null }
    mockExtraction.listExtractionResults.mockResolvedValue([pendingResult])

    const { result } = renderHook(() => useExtractionResults('doc-1'))
    await act(async () => {})

    // Still pending before 10-minute mark
    act(() => { vi.advanceTimersByTime(10 * ONE_MINUTE_MS - 1) })
    await act(async () => {})
    expect(result.current.results[0]?.status).toBe('pending')

    // Advance past the 10-minute timeout (next interval after 600s)
    act(() => { vi.advanceTimersByTime(INTERVAL + 1) })
    await act(async () => {})
    expect(result.current.results[0]?.status).toBe('failed')

    vi.useRealTimers()
  })
})
