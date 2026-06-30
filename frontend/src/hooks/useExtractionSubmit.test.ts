import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useExtractionSubmit } from './useExtractionSubmit'
import * as extractionApi from '@/api/extraction'
import * as parseRunsApi from '@/api/parseRuns'
import type { RunWithParseRequest } from '@/types/extraction'
import type { ParseRunListItem } from '@/types/cdm'

vi.mock('@/api/extraction')
vi.mock('@/api/parseRuns')

// Mirrors the makeParseRun pattern from useExtractionResults.test.ts.
// config must include { parser } so findMatchingRun can match it.
function makeParseRun(overrides: Partial<ParseRunListItem> = {}): ParseRunListItem {
  return {
    id: 'run-1',
    sourceDocumentId: 'doc-1',
    parser: 'simple',
    parserVersion: null,
    representationKind: 'extract_rich',
    status: 'succeeded',
    startedAt: '2026-01-01T00:00:00Z',
    finishedAt: '2026-01-01T00:01:00Z',
    durationMs: 60000,
    inputTokens: null,
    outputTokens: null,
    cost: {},
    warnings: [],
    failedPages: [],
    providerRefs: {},
    error: null,
    config: { parser: 'simple' },
    createdAt: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

const request: RunWithParseRequest = {
  parseConfig: { parser: 'simple', config: {}, representationKind: 'extract_rich' },
  extractionConfig: { extractionSchemaId: 'schema-1', extractionMethod: 'llm' },
}

describe('useExtractionSubmit', () => {
  beforeEach(() => { vi.clearAllMocks() })
  afterEach(() => { vi.useRealTimers() })

  it('returns result id when matching parse run exists', async () => {
    vi.mocked(extractionApi.runExtraction).mockResolvedValue(
      { id: 'result-1', status: 'pending' } as never,
    )
    const { result } = renderHook(() => useExtractionSubmit())
    let resultId: string | null = null
    await act(async () => {
      resultId = await result.current.submit('doc-1', [makeParseRun()], request)
    })
    expect(resultId).toBe('result-1')
    expect(result.current.phase).toBe('idle')
    expect(parseRunsApi.createParseRun).not.toHaveBeenCalled()
  })

  it('sets phase to failed and returns null when runExtraction throws', async () => {
    vi.mocked(extractionApi.runExtraction).mockRejectedValue(new Error('API error'))
    const { result } = renderHook(() => useExtractionSubmit())
    let resultId: string | null = 'not-null'
    await act(async () => {
      resultId = await result.current.submit('doc-1', [makeParseRun()], request)
    })
    expect(resultId).toBeNull()
    expect(result.current.phase).toBe('failed')
    expect(result.current.phaseError).toBe('API error')
  })

  it('returns null and does not call runExtraction when createParseRun fails', async () => {
    vi.mocked(parseRunsApi.createParseRun).mockRejectedValue(new Error('Server error'))
    const { result } = renderHook(() => useExtractionSubmit())
    let resultId: string | null = 'not-null'
    await act(async () => {
      // pass empty existing runs so no matching run is found → triggers parse
      resultId = await result.current.submit('doc-1', [], request)
    })
    expect(resultId).toBeNull()
    expect(result.current.phase).toBe('failed')
    expect(result.current.phaseError).toBe('Failed to start parse')
    expect(extractionApi.runExtraction).not.toHaveBeenCalled()
  })
})
