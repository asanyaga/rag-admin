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
})
