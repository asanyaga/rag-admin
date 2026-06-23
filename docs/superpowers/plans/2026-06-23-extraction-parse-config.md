# Extraction Parse Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a parse configuration section to the extraction form so users can trigger fresh parses directly from the extraction screen, with automatic reuse of existing matching parse runs.

**Architecture:** Frontend-only. `useExtractionResults` owns orchestration and phase state. `ExtractionPage` passes existing parse runs into the hook for the match check. `ExtractionForm` embeds `ParseMethodSelector` pre-populated from the latest parse run. `ExtractionHistory` renders a synthetic row during parse/extract phases.

**Tech Stack:** React 18, TypeScript, vitest, @testing-library/react, shadcn/ui, Tailwind CSS

## Global Constraints

- No backend changes whatsoever
- `representationKind` fixed to `"extract_rich"` — not user-configurable
- Stored `ParseRun.config` includes a `parser` key (added by backend) but excludes `representationKind`
- `POST /documents/{id}/parse-runs` returns `{ status: "accepted" }` — no run ID in response
- Landing AI parser key is `landing_ai` (underscore) in both `PARSER_REGISTRY` and `ParseRunListItem.parser`
- Poll interval: 3 000 ms; parse timeout: 600 000 ms (10 min)

---

## File Map

| File | Change |
|---|---|
| `frontend/src/types/extraction.ts` | Add `RunWithParseRequest`, `ExtractionPhase` |
| `frontend/src/hooks/useExtractionResults.ts` | Add `runExtractionWithParse`, `extractionPhase`, `phaseError`; remove `runExtraction` |
| `frontend/src/hooks/useExtractionResults.test.ts` | New — unit tests for orchestration logic |
| `frontend/src/components/extraction/ExtractionForm.tsx` | Swap `parseRunId` prop for `defaultParser`/`defaultParserConfig`; add parse config section |
| `frontend/src/components/extraction/ExtractionHistory.tsx` | Add `inProgressPhase` prop, synthetic row, failed/retry state |
| `frontend/src/pages/ExtractionPage.tsx` | Wire phase state, always show form when doc ready, store last request for retry |

---

### Task 1: Add `RunWithParseRequest` and `ExtractionPhase` types

**Files:**
- Modify: `frontend/src/types/extraction.ts`

**Interfaces:**
- Produces: `RunWithParseRequest`, `ExtractionPhase` — used by Tasks 2, 3, 4, 5

- [ ] **Step 1: Add types to `types/extraction.ts`**

Open `frontend/src/types/extraction.ts` and append after the existing `ExtractorInfo` interface:

```ts
export type ExtractionPhase = 'idle' | 'parsing' | 'extracting' | 'done' | 'failed'

export interface RunWithParseRequest {
  parseConfig: {
    parser: string
    /** Parser-specific fields (tier, expand, model, etc.) — does NOT include representationKind */
    config: Record<string, unknown>
    representationKind: string
  }
  extractionConfig: {
    extractionSchemaId: string
    extractionMethod: string
    config?: Record<string, unknown>
    llmConfig?: PromptConfig
    userPromptTemplate?: string
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
npx --prefix frontend tsc --noEmit
```

Expected: no errors relating to the new types.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/extraction.ts
git commit -m "feat(extraction): add RunWithParseRequest and ExtractionPhase types"
```

---

### Task 2: Extend `useExtractionResults` with orchestration

**Files:**
- Modify: `frontend/src/hooks/useExtractionResults.ts`
- Create: `frontend/src/hooks/useExtractionResults.test.ts`

**Interfaces:**
- Consumes: `RunWithParseRequest`, `ExtractionPhase` from Task 1; `ParseRunListItem` from `@/types/cdm`; `createParseRun`, `listParseRuns`, `getParseRun` from `@/api/parseRuns`
- Produces: `runExtractionWithParse(documentId, existingParseRuns, request)`, `extractionPhase`, `phaseError` in hook return

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/hooks/useExtractionResults.test.ts`:

```ts
import { renderHook, act, waitFor } from '@testing-library/react'
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
    const existingRun = makeParseRun({ id: 'run-match', parser: 'simple', config: { parser: 'simple' }, status: 'succeeded' })
    mockExtraction.runExtraction.mockResolvedValue({
      id: 'result-1', documentId: 'doc-1', extractionSchemaId: 'schema-1',
      schemaDefinitionSnapshot: {}, extractionMethod: 'llm', config: null,
      structuredData: null, extractionMetadata: null, citations: null,
      providerResponseRaw: null, sourceParseRunId: 'run-match',
      status: 'pending', statusMessage: null, startedAt: null,
      createdBy: 'user-1', createdAt: '2026-06-23T00:00:00Z', updatedAt: '2026-06-23T00:00:00Z',
    })

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
    // First poll: run is still pending; second poll: succeeded
    mockParseRuns.listParseRuns
      .mockResolvedValueOnce([makeParseRun({ id: 'new-run', status: 'pending' })])
      .mockResolvedValue([makeParseRun({ id: 'new-run', status: 'succeeded' })])
    mockParseRuns.getParseRun.mockResolvedValue(makeParseRun({ id: 'new-run', status: 'succeeded' }))
    mockExtraction.runExtraction.mockResolvedValue({
      id: 'result-1', documentId: 'doc-1', extractionSchemaId: 'schema-1',
      schemaDefinitionSnapshot: {}, extractionMethod: 'llm', config: null,
      structuredData: null, extractionMetadata: null, citations: null,
      providerResponseRaw: null, sourceParseRunId: 'new-run',
      status: 'pending', statusMessage: null, startedAt: null,
      createdBy: 'user-1', createdAt: '2026-06-23T00:00:00Z', updatedAt: '2026-06-23T00:00:00Z',
    })

    vi.useFakeTimers()
    const { result } = renderHook(() => useExtractionResults('doc-1'))

    const runPromise = act(async () => {
      const p = result.current.runExtractionWithParse('doc-1', [], baseRequest)
      await vi.runAllTimersAsync()
      return p
    })
    await runPromise
    vi.useRealTimers()

    expect(mockParseRuns.createParseRun).toHaveBeenCalledWith(
      'doc-1', 'simple', expect.objectContaining({ representation_kind: 'extract_rich' })
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

    await waitFor(() => {
      expect(result.current.extractionPhase).toBe('failed')
      expect(result.current.phaseError).toBe('Parse error')
    })
    expect(mockExtraction.runExtraction).not.toHaveBeenCalled()
  })

  it('transitions through idle → parsing → extracting → done phases for a fresh parse', async () => {
    mockParseRuns.createParseRun.mockResolvedValue(undefined)
    mockParseRuns.listParseRuns.mockResolvedValue([makeParseRun({ id: 'r', status: 'succeeded' })])
    mockParseRuns.getParseRun.mockResolvedValue(makeParseRun({ id: 'r', status: 'succeeded' }))
    mockExtraction.runExtraction.mockResolvedValue({
      id: 'result-1', documentId: 'doc-1', extractionSchemaId: 'schema-1',
      schemaDefinitionSnapshot: {}, extractionMethod: 'llm', config: null,
      structuredData: null, extractionMetadata: null, citations: null,
      providerResponseRaw: null, sourceParseRunId: 'r',
      status: 'pending', statusMessage: null, startedAt: null,
      createdBy: 'user-1', createdAt: '2026-06-23T00:00:00Z', updatedAt: '2026-06-23T00:00:00Z',
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

    await waitFor(() => expect(result.current.extractionPhase).toBe('done'))
  })
})
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
npx --prefix frontend vitest run src/hooks/useExtractionResults.test.ts
```

Expected: tests fail because `runExtractionWithParse` does not exist yet.

- [ ] **Step 3: Rewrite `useExtractionResults.ts`**

Replace the entire file content:

```ts
import { useState, useCallback, useEffect, useRef } from 'react'
import type {
  ExtractionResult,
  ExtractionResultListItem,
  ExtractionPhase,
  RunWithParseRequest,
} from '@/types/extraction'
import type { ParseRunListItem } from '@/types/cdm'
import * as extractionApi from '@/api/extraction'
import { createParseRun, listParseRuns, getParseRun } from '@/api/parseRuns'

const POLLING_INTERVAL = 3_000
const EXTRACTION_POLLING_TIMEOUT = 5 * 60 * 1_000
const PARSE_TIMEOUT = 10 * 60 * 1_000

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function stableStringify(value: unknown): string {
  if (value === null || typeof value !== 'object') return JSON.stringify(value)
  if (Array.isArray(value)) return `[${(value as unknown[]).map(stableStringify).join(',')}]`
  const obj = value as Record<string, unknown>
  const sorted = Object.keys(obj)
    .sort()
    .map((k) => `${JSON.stringify(k)}:${stableStringify(obj[k])}`)
  return `{${sorted.join(',')}}`
}

function findMatchingRun(
  runs: ParseRunListItem[],
  parser: string,
  representationKind: string,
  config: Record<string, unknown>
): ParseRunListItem | undefined {
  const target = stableStringify({ parser, ...config })
  return runs.find(
    (r) =>
      r.parser === parser &&
      r.representationKind === representationKind &&
      stableStringify(r.config) === target &&
      (r.status === 'succeeded' || r.status === 'partial')
  )
}

interface UseExtractionResultsReturn {
  results: ExtractionResultListItem[]
  selectedResult: ExtractionResult | null
  isLoading: boolean
  isLoadingResult: boolean
  error: string | null
  extractionPhase: ExtractionPhase
  phaseError: string | null
  fetchResults: () => Promise<void>
  selectResult: (resultId: string) => Promise<void>
  runExtractionWithParse: (
    documentId: string,
    existingParseRuns: ParseRunListItem[],
    request: RunWithParseRequest
  ) => Promise<void>
}

export function useExtractionResults(
  documentId: string | null
): UseExtractionResultsReturn {
  const [results, setResults] = useState<ExtractionResultListItem[]>([])
  const [selectedResult, setSelectedResult] = useState<ExtractionResult | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingResult, setIsLoadingResult] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [extractionPhase, setExtractionPhase] = useState<ExtractionPhase>('idle')
  const [phaseError, setPhaseError] = useState<string | null>(null)
  const pollingRef = useRef<NodeJS.Timeout | null>(null)
  const pollingStartRef = useRef<number | null>(null)

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
    pollingStartRef.current = null
  }, [])

  const fetchResults = useCallback(async () => {
    if (!documentId) {
      setResults([])
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      const data = await extractionApi.listExtractionResults(documentId)
      setResults(data)

      const hasPending = data.some((r) => r.status === 'pending')
      if (hasPending && !pollingRef.current) {
        pollingStartRef.current = Date.now()
        pollingRef.current = setInterval(async () => {
          if (
            pollingStartRef.current &&
            Date.now() - pollingStartRef.current > EXTRACTION_POLLING_TIMEOUT
          ) {
            setResults((prev) =>
              prev.map((r) =>
                r.status === 'pending'
                  ? { ...r, status: 'failed' as const, statusMessage: 'Processing timeout' }
                  : r
              )
            )
            stopPolling()
            return
          }
          try {
            const updated = await extractionApi.listExtractionResults(documentId)
            setResults(updated)
            if (!updated.some((r) => r.status === 'pending')) stopPolling()
          } catch {
            stopPolling()
          }
        }, POLLING_INTERVAL)
      } else if (!hasPending) {
        stopPolling()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch extraction results')
    } finally {
      setIsLoading(false)
    }
  }, [documentId, stopPolling])

  const selectResult = useCallback(async (resultId: string) => {
    setIsLoadingResult(true)
    setError(null)
    try {
      const result = await extractionApi.getExtractionResult(resultId)
      setSelectedResult(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch extraction result')
    } finally {
      setIsLoadingResult(false)
    }
  }, [])

  const runExtractionWithParse = useCallback(
    async (
      documentId: string,
      existingParseRuns: ParseRunListItem[],
      request: RunWithParseRequest
    ): Promise<void> => {
      const { parseConfig, extractionConfig } = request
      setPhaseError(null)

      // Step 1: Match check — reuse existing parse run if config matches
      const matched = findMatchingRun(
        existingParseRuns,
        parseConfig.parser,
        parseConfig.representationKind,
        parseConfig.config
      )

      // eslint-disable-next-line prefer-const
      let parseRunId!: string  // assigned in all non-returning branches below

      if (matched) {
        parseRunId = matched.id
      } else {
        // Step 2: Trigger a fresh parse
        setExtractionPhase('parsing')
        const started = Date.now()

        try {
          await createParseRun(documentId, parseConfig.parser, {
            ...parseConfig.config,
            representation_kind: parseConfig.representationKind,
          })
        } catch {
          setExtractionPhase('failed')
          setPhaseError('Failed to start parse')
          return
        }

        // Poll the list to find the new run by config match
        let resolvedId: string | null = null
        while (resolvedId === null) {
          if (Date.now() - started > PARSE_TIMEOUT) {
            setExtractionPhase('failed')
            setPhaseError('Parse timed out')
            return
          }
          await sleep(POLLING_INTERVAL)
          const runs = await listParseRuns(documentId)
          const target = stableStringify({ parser: parseConfig.parser, ...parseConfig.config })
          const found = runs.find(
            (r) =>
              r.parser === parseConfig.parser &&
              r.representationKind === parseConfig.representationKind &&
              stableStringify(r.config) === target
          )
          if (found) resolvedId = found.id
        }

        // resolvedId is non-null after the loop exits — TypeScript doesn't know this
        const foundId = resolvedId as string

        // Poll by ID until terminal
        while (true) {
          if (Date.now() - started > PARSE_TIMEOUT) {
            setExtractionPhase('failed')
            setPhaseError('Parse timed out')
            return
          }
          const run = await getParseRun(foundId)
          if (run.status === 'succeeded' || run.status === 'partial') {
            parseRunId = foundId
            break
          }
          if (run.status === 'failed') {
            setExtractionPhase('failed')
            setPhaseError(run.error ?? 'Parse failed')
            return
          }
          await sleep(POLLING_INTERVAL)
        }
      }

      // Step 3: Run extraction
      setExtractionPhase('extracting')
      try {
        await extractionApi.runExtraction({
          parseRunId,
          extractionSchemaId: extractionConfig.extractionSchemaId,
          extractionMethod: extractionConfig.extractionMethod,
          config: extractionConfig.config,
          llmConfig: extractionConfig.llmConfig,
          userPromptTemplate: extractionConfig.userPromptTemplate,
        })
        await fetchResults()
        setExtractionPhase('done')
      } catch (err) {
        setExtractionPhase('failed')
        setPhaseError(err instanceof Error ? err.message : 'Extraction failed')
      }
    },
    [fetchResults]
  )

  useEffect(() => {
    setExtractionPhase('idle')
    setPhaseError(null)
    if (documentId) {
      fetchResults()
    } else {
      setResults([])
      setSelectedResult(null)
    }
  }, [documentId, fetchResults])

  useEffect(() => {
    return () => { stopPolling() }
  }, [stopPolling])

  return {
    results,
    selectedResult,
    isLoading,
    isLoadingResult,
    error,
    extractionPhase,
    phaseError,
    fetchResults,
    selectResult,
    runExtractionWithParse,
  }
}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
npx --prefix frontend vitest run src/hooks/useExtractionResults.test.ts
```

Expected: all 4 tests pass.

- [ ] **Step 5: Verify TypeScript**

```bash
npx --prefix frontend tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useExtractionResults.ts frontend/src/hooks/useExtractionResults.test.ts
git commit -m "feat(extraction): add runExtractionWithParse orchestration with phase tracking"
```

---

### Task 3: Add parse config section to `ExtractionForm`

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionForm.tsx`

**Interfaces:**
- Consumes: `RunWithParseRequest` from Task 1; `ParseMethodSelector` (existing, props: `parserType`, `config`, `onParserTypeChange`, `onConfigChange`, `disabled`)
- Produces: updated `ExtractionFormProps` with `defaultParser`, `defaultParserConfig` replacing `parseRunId`; `onRun` now accepts `RunWithParseRequest`

- [ ] **Step 1: Replace `ExtractionForm.tsx`**

Replace the entire file:

```tsx
import { useState, useEffect } from 'react'
import type { ExtractionSchema, ExtractorInfo, RunWithParseRequest } from '@/types/extraction'
import type { ParseConfig } from '@/types/parsing'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Pencil, Play } from 'lucide-react'
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'
import { usePromptConfig } from '@/hooks/usePromptConfig'
import { ParseMethodSelector } from '@/components/documents/ParseMethodSelector'

const REPRESENTATION_KIND = 'extract_rich'

interface ExtractionFormProps {
  defaultParser: string
  defaultParserConfig: ParseConfig
  schemas: ExtractionSchema[]
  extractors: ExtractorInfo[]
  onRun: (request: RunWithParseRequest) => Promise<void>
  onEditSchema?: (schema: ExtractionSchema) => void
}

export function ExtractionForm({
  defaultParser,
  defaultParserConfig,
  schemas,
  extractors,
  onRun,
  onEditSchema,
}: ExtractionFormProps) {
  const [parserType, setParserType] = useState(defaultParser)
  const [parserConfig, setParserConfig] = useState<ParseConfig>(defaultParserConfig)

  const [schemaId, setSchemaId] = useState('')
  const [extractionMethod, setExtractionMethod] = useState('')

  // LlamaExtract config
  const [extractionMode, setExtractionMode] = useState('MULTIMODAL')
  const [citeSources, setCiteSources] = useState(false)
  const [useReasoning, setUseReasoning] = useState(false)
  const [pageRange, setPageRange] = useState('')
  const [extractionTarget, setExtractionTarget] = useState('PER_DOC')
  const [confidenceScores, setConfidenceScores] = useState(false)

  // LLM method config
  const { promptConfig, setPromptConfig, setProvider } = usePromptConfig()
  const [userPromptTemplate, setUserPromptTemplate] = useState('')
  const [structuredOutputMode, setStructuredOutputMode] = useState('json_schema')
  const [injectBlockIds, setInjectBlockIds] = useState(false)

  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset parse config when defaults change (document selection changed)
  useEffect(() => {
    setParserType(defaultParser)
    setParserConfig(defaultParserConfig)
  }, [defaultParser, defaultParserConfig])

  useEffect(() => {
    if (schemas.length > 0 && !schemaId) setSchemaId(schemas[0].id)
  }, [schemas, schemaId])

  useEffect(() => {
    if (extractors.length > 0 && !extractionMethod) {
      const firstConfigured = extractors.find((e) => e.configured)
      setExtractionMethod(firstConfigured?.extractionMethod ?? extractors[0].extractionMethod)
    }
  }, [extractors, extractionMethod])

  const selectedExtractor = extractors.find((e) => e.extractionMethod === extractionMethod)
  const isConfigured = selectedExtractor?.configured ?? true

  const handleRun = async () => {
    setError(null)

    if (!schemaId) {
      setError('Please select a schema')
      return
    }
    if (!extractionMethod) {
      setError('No extraction method available')
      return
    }

    const parseConfig = {
      parser: parserType,
      config: parserConfig as Record<string, unknown>,
      representationKind: REPRESENTATION_KIND,
    }

    let extractionConfig: RunWithParseRequest['extractionConfig']

    if (extractionMethod === 'llamaextract') {
      const config: Record<string, unknown> = { extraction_mode: extractionMode }
      if (citeSources) config.cite_sources = true
      if (useReasoning) config.use_reasoning = true
      if (pageRange.trim()) config.page_range = pageRange.trim()
      config.extraction_target = extractionTarget
      if (confidenceScores) config.confidence_scores = true
      extractionConfig = { extractionSchemaId: schemaId, extractionMethod, config }
    } else if (extractionMethod === 'llm') {
      extractionConfig = {
        extractionSchemaId: schemaId,
        extractionMethod,
        config: { structured_output_mode: structuredOutputMode, inject_block_ids: injectBlockIds },
        llmConfig: promptConfig,
        userPromptTemplate: userPromptTemplate.trim() || undefined,
      }
    } else {
      extractionConfig = { extractionSchemaId: schemaId, extractionMethod, config: {} }
    }

    setIsRunning(true)
    try {
      await onRun({ parseConfig, extractionConfig })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run extraction')
    } finally {
      setIsRunning(false)
    }
  }

  const hasSchemas = schemas.length > 0
  const hasExtractors = extractors.length > 0

  if (!hasSchemas || !hasExtractors) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
        {!hasExtractors
          ? 'No extraction methods available. Contact your administrator.'
          : 'Create a schema first to run extractions.'}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Parse Configuration */}
      <div className="space-y-3">
        <Label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Parse Configuration
        </Label>
        <ParseMethodSelector
          parserType={parserType}
          config={parserConfig}
          onParserTypeChange={setParserType}
          onConfigChange={setParserConfig}
          disabled={isRunning}
        />
      </div>

      <Separator />

      {/* Schema + Method row */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label className="text-xs">Schema</Label>
          <div className="flex items-center gap-1">
            <Select value={schemaId} onValueChange={setSchemaId}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="Select schema" />
              </SelectTrigger>
              <SelectContent>
                {schemas.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {onEditSchema && schemaId && (
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9 shrink-0"
                title="Edit selected schema"
                onClick={() => {
                  const selected = schemas.find((s) => s.id === schemaId)
                  if (selected) onEditSchema(selected)
                }}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        </div>

        {extractors.length > 1 ? (
          <div className="space-y-1.5">
            <Label className="text-xs">Method</Label>
            <Select value={extractionMethod} onValueChange={setExtractionMethod}>
              <SelectTrigger className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {extractors.map((e) => (
                  <SelectItem key={e.extractionMethod} value={e.extractionMethod} disabled={!e.configured}>
                    {e.name}{!e.configured ? ' (not configured)' : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : (
          <div className="space-y-1.5">
            <Label className="text-xs">Method</Label>
            <div className="h-9 flex items-center text-sm text-muted-foreground px-3 border rounded-md bg-muted/50">
              {extractors[0]?.name}
            </div>
          </div>
        )}
      </div>

      {/* LlamaExtract-specific config */}
      {extractionMethod === 'llamaextract' && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Mode</Label>
              <Select value={extractionMode} onValueChange={setExtractionMode}>
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="FAST">Fast</SelectItem>
                  <SelectItem value="BALANCED">Balanced</SelectItem>
                  <SelectItem value="MULTIMODAL">Multimodal</SelectItem>
                  <SelectItem value="PREMIUM">Premium</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Page Range</Label>
              <Input value={pageRange} onChange={(e) => setPageRange(e.target.value)} placeholder="e.g. 1-5" className="h-9" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="extraction-target" className="text-xs">Target</Label>
              <Select value={extractionTarget} onValueChange={setExtractionTarget}>
                <SelectTrigger id="extraction-target" className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="PER_DOC">Per Document</SelectItem>
                  <SelectItem value="PER_PAGE">Per Page</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end pb-2">
              <div className="flex items-center space-x-2">
                <Checkbox id="confidence-scores" checked={confidenceScores} onCheckedChange={(c) => setConfidenceScores(c === true)} />
                <Label htmlFor="confidence-scores" className="text-xs font-normal">Confidence Scores</Label>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center space-x-2">
              <Checkbox id="cite-sources-inline" checked={citeSources} onCheckedChange={(c) => setCiteSources(c === true)} />
              <Label htmlFor="cite-sources-inline" className="text-xs font-normal">Citations</Label>
            </div>
            <div className="flex items-center space-x-2">
              <Checkbox id="use-reasoning-inline" checked={useReasoning} onCheckedChange={(c) => setUseReasoning(c === true)} />
              <Label htmlFor="use-reasoning-inline" className="text-xs font-normal">Reasoning</Label>
            </div>
          </div>
        </>
      )}

      {/* LLM method config */}
      {extractionMethod === 'llm' && (
        <div className="space-y-4">
          <PromptConfigEditor value={promptConfig} onChange={setPromptConfig} onProviderChange={setProvider} capabilities={{ thinking: true }} />
          <div className="space-y-1.5">
            <Label className="text-xs">User prompt template</Label>
            <p className="text-[11px] text-muted-foreground">
              Variables: <code>{'{schema_json}'}</code> and <code>{'{document_context}'}</code>. Leave blank to use the default.
            </p>
            <Textarea value={userPromptTemplate} onChange={(e) => setUserPromptTemplate(e.target.value)} className="font-mono text-xs min-h-[80px]" placeholder="Extract structured data from the following document..." />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Output mode</Label>
              <Select value={structuredOutputMode} onValueChange={setStructuredOutputMode}>
                <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="json_schema">JSON Schema</SelectItem>
                  <SelectItem value="json_mode">JSON Mode</SelectItem>
                  <SelectItem value="prompt_only">Prompt Only</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end pb-2">
              <div className="flex items-center space-x-2">
                <Checkbox id="inject-block-ids" checked={injectBlockIds} onCheckedChange={(v) => setInjectBlockIds(v === true)} />
                <Label htmlFor="inject-block-ids" className="text-xs font-normal">Inject block IDs</Label>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Run button */}
      <div className="flex items-center justify-between">
        <div />
        <Button onClick={handleRun} disabled={isRunning || !isConfigured} size="sm">
          {isRunning ? 'Running...' : (
            <><Play className="h-3.5 w-3.5 mr-1.5" />Run Extraction</>
          )}
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {!isConfigured && (
        <p className="text-xs text-amber-600">
          {selectedExtractor?.name ?? 'This extractor'} is not configured. Contact your administrator.
        </p>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
npx --prefix frontend tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/extraction/ExtractionForm.tsx
git commit -m "feat(extraction): add parse configuration section to ExtractionForm"
```

---

### Task 4: Add `inProgressPhase` to `ExtractionHistory`

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionHistory.tsx`

**Interfaces:**
- Consumes: `ExtractionPhase` from Task 1
- Produces: updated `ExtractionHistoryProps` with `inProgressPhase`

- [ ] **Step 1: Replace `ExtractionHistory.tsx`**

Replace the entire file:

```tsx
import type { ExtractionResult, ExtractionResultListItem } from '@/types/extraction'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { AlertCircle, ChevronRight, Loader2, RefreshCw } from 'lucide-react'
import { ExtractionResultViewer } from './ExtractionResultViewer'

interface InProgressPhase {
  phase: 'parsing' | 'extracting' | 'failed'
  phaseError?: string | null
  onRetry?: () => void
}

interface ExtractionHistoryProps {
  results: ExtractionResultListItem[]
  isLoading: boolean
  selectedResult: ExtractionResult | null
  isLoadingResult?: boolean
  onSelectResult: (resultId: string) => void
  inProgressPhase?: InProgressPhase
}

export function ExtractionHistory({
  results,
  isLoading,
  selectedResult,
  onSelectResult,
  inProgressPhase,
}: ExtractionHistoryProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    )
  }

  // Show synthetic row when actively parsing/extracting and no real pending result exists yet
  const hasPendingResult = results.some((r) => r.status === 'pending')
  const showSyntheticRow =
    inProgressPhase &&
    (inProgressPhase.phase === 'parsing' ||
      inProgressPhase.phase === 'extracting' ||
      inProgressPhase.phase === 'failed') &&
    !hasPendingResult

  const isEmpty = results.length === 0 && !showSyntheticRow

  if (isEmpty) {
    return (
      <p className="text-sm text-muted-foreground text-center py-6">
        No extractions yet. Run one above to get started.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {showSyntheticRow && inProgressPhase && (
        <div className="rounded-md border px-3 py-2.5">
          {inProgressPhase.phase === 'failed' ? (
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-destructive">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span className="text-sm">{inProgressPhase.phaseError ?? 'Failed'}</span>
              </div>
              {inProgressPhase.onRetry && (
                <Button variant="outline" size="sm" className="h-7 text-xs gap-1.5" onClick={inProgressPhase.onRetry}>
                  <RefreshCw className="h-3 w-3" />
                  Retry
                </Button>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 shrink-0 animate-spin" />
              <span className="text-sm">
                {inProgressPhase.phase === 'parsing' ? 'Parsing document…' : 'Extracting…'}
              </span>
            </div>
          )}
        </div>
      )}

      {results.map((r) => {
        const isExpanded = selectedResult?.id === r.id
        const isPending = r.status === 'pending'

        return (
          <Collapsible
            key={r.id}
            open={isExpanded}
            onOpenChange={(open) => { if (open) onSelectResult(r.id) }}
          >
            <CollapsibleTrigger asChild>
              <Button variant="ghost" className="w-full justify-between h-auto py-2.5 px-3 hover:bg-muted/50">
                <div className="flex items-center gap-2 text-left">
                  <ChevronRight className={`h-4 w-4 shrink-0 transition-transform ${isExpanded ? 'rotate-90' : ''}`} />
                  <Badge variant="outline" className="text-[10px] font-normal">{r.extractionMethod}</Badge>
                  <Badge
                    variant={r.status === 'completed' ? 'default' : r.status === 'pending' ? 'secondary' : 'destructive'}
                    className="text-[10px]"
                  >
                    {isPending && <Loader2 className="h-2.5 w-2.5 mr-1 animate-spin" />}
                    {r.status}
                  </Badge>
                </div>
                <span className="text-xs text-muted-foreground">{formatDate(r.createdAt)}</span>
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="ml-6 mr-3 mb-2 mt-1">
                {selectedResult?.id === r.id ? (
                  <ExtractionResultViewer result={selectedResult} isLoading={false} />
                ) : isExpanded ? (
                  <div className="space-y-2 p-3">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-4 w-1/2" />
                  </div>
                ) : null}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )
      })}
    </div>
  )
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
npx --prefix frontend tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/extraction/ExtractionHistory.tsx
git commit -m "feat(extraction): add inProgressPhase synthetic row to ExtractionHistory"
```

---

### Task 5: Wire everything in `ExtractionPage`

**Files:**
- Modify: `frontend/src/pages/ExtractionPage.tsx`

**Interfaces:**
- Consumes: `runExtractionWithParse`, `extractionPhase`, `phaseError` from Task 2; updated `ExtractionForm` props from Task 3; `inProgressPhase` prop from Task 4; `RunWithParseRequest` from Task 1

- [ ] **Step 1: Replace `ExtractionPage.tsx`**

Replace the entire file:

```tsx
import { useState, useEffect, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useProject } from '@/contexts/ProjectContext'
import { useDocuments } from '@/hooks/useDocuments'
import { useExtractionSchemas } from '@/hooks/useExtractionSchemas'
import { useExtractionResults } from '@/hooks/useExtractionResults'
import { useParseRuns } from '@/hooks/useParseRuns'
import type {
  ExtractionSchema,
  ExtractionSchemaCreate,
  ExtractionSchemaUpdate,
  ExtractorInfo,
  RunWithParseRequest,
} from '@/types/extraction'
import type { ParseConfig } from '@/types/parsing'
import type { Document as AppDocument, DocumentUpload } from '@/types/document'
import { ExtractionSchemaEditor } from '@/components/extraction/ExtractionSchemaEditor'
import { ExtractionForm } from '@/components/extraction/ExtractionForm'
import { ExtractionHistory } from '@/components/extraction/ExtractionHistory'
import { SchemaManager } from '@/components/extraction/SchemaManager'
import { DocumentSelector } from '@/components/extraction/DocumentSelector'
import { DocumentUploadDialog } from '@/components/documents/DocumentUploadDialog'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { FileSearch } from 'lucide-react'
import { toast } from 'sonner'
import * as extractionApi from '@/api/extraction'

export default function ExtractionPage(): JSX.Element {
  const { currentProject } = useProject()
  const projectId = currentProject?.id || null

  const { documents, isLoading: documentsLoading, uploadDocument } = useDocuments(projectId)
  const { schemas, error: schemasError, createSchema, updateSchema, deleteSchema } = useExtractionSchemas(projectId)

  const [searchParams, setSearchParams] = useSearchParams()
  const preselectedDocumentId = searchParams.get('documentId')
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(preselectedDocumentId)

  const {
    results,
    selectedResult,
    isLoading: resultsLoading,
    isLoadingResult,
    error: resultsError,
    extractionPhase,
    phaseError,
    selectResult,
    runExtractionWithParse,
  } = useExtractionResults(selectedDocumentId)

  const { parseRuns, isLoading: parseRunsLoading } = useParseRuns(selectedDocumentId)

  // Latest viable parse run drives form defaults
  const latestViableRun = parseRuns.find((r) => r.status === 'succeeded' || r.status === 'partial')

  // Strip the backend-added "parser" key from config before passing as default
  const defaultParser: string = latestViableRun?.parser ?? 'simple'
  const defaultParserConfig: ParseConfig = (() => {
    if (!latestViableRun?.config) return {}
    const { parser: _p, ...rest } = latestViableRun.config as Record<string, unknown>
    return rest as ParseConfig
  })()

  const [extractors, setExtractors] = useState<ExtractorInfo[]>([])
  const [schemaEditorOpen, setSchemaEditorOpen] = useState(false)
  const [editingSchema, setEditingSchema] = useState<ExtractionSchema | null>(null)
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false)

  // Store last request for retry after parse failure
  const lastRequestRef = useRef<RunWithParseRequest | null>(null)

  const fetchExtractors = useCallback(async () => {
    try {
      const data = await extractionApi.listExtractors()
      setExtractors(data)
    } catch {
      // Extractors not available
    }
  }, [])

  useEffect(() => { fetchExtractors() }, [fetchExtractors])

  // Reset phase to idle when document changes
  // (phase state lives in the hook and resets when documentId changes via useEffect in hook)

  const handleSelectDocument = (docId: string) => {
    setSelectedDocumentId(docId)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('documentId', docId)
      return next
    })
  }

  const handleCreateSchema = () => { setEditingSchema(null); setSchemaEditorOpen(true) }
  const handleEditSchema = (schema: ExtractionSchema) => { setEditingSchema(schema); setSchemaEditorOpen(true) }

  const handleDeleteSchema = async (schemaId: string) => {
    try {
      await deleteSchema(schemaId)
      toast.success('Schema deleted')
    } catch (err) {
      toast.error('Failed to delete schema', { description: err instanceof Error ? err.message : 'An error occurred' })
    }
  }

  const handleSaveSchema = async (data: ExtractionSchemaCreate | ExtractionSchemaUpdate) => {
    try {
      if (editingSchema) {
        await updateSchema(editingSchema.id, data as ExtractionSchemaUpdate)
        toast.success('Schema updated')
      } else {
        await createSchema(data as ExtractionSchemaCreate)
        toast.success('Schema created')
      }
    } catch (err) {
      toast.error('Failed to save schema', { description: err instanceof Error ? err.message : 'An error occurred' })
      throw err
    }
  }

  const handleRunExtraction = async (request: RunWithParseRequest) => {
    lastRequestRef.current = request
    await runExtractionWithParse(selectedDocumentId!, parseRuns, request)
  }

  const handleRetry = async () => {
    if (lastRequestRef.current && selectedDocumentId) {
      await runExtractionWithParse(selectedDocumentId, parseRuns, lastRequestRef.current)
    }
  }

  const handleUpload = async (data: DocumentUpload): Promise<AppDocument> => {
    const newDoc = await uploadDocument(data)
    toast.success('Document uploaded', { description: newDoc.status === 'processing' ? 'Processing in progress...' : undefined })
    handleSelectDocument(newDoc.id)
    return newDoc
  }

  if (!currentProject) {
    return (
      <div className="space-y-6">
        <Alert><AlertDescription>Loading project...</AlertDescription></Alert>
      </div>
    )
  }

  const selectedDocument = documents.find((d) => d.id === selectedDocumentId)
  const isDocumentReady = selectedDocument?.status === 'ready'

  const inProgressPhase =
    extractionPhase === 'parsing' || extractionPhase === 'extracting'
      ? { phase: extractionPhase as 'parsing' | 'extracting' }
      : extractionPhase === 'failed' && phaseError
        ? { phase: 'failed' as const, phaseError, onRetry: handleRetry }
        : undefined

  return (
    <div className="-m-6 flex flex-col h-[calc(100vh-3.5rem)]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b shrink-0">
        <div>
          <h1 className="text-lg font-semibold">Extraction</h1>
          <p className="text-xs text-muted-foreground">{currentProject.name}</p>
        </div>
      </div>

      {/* Errors */}
      {(schemasError || resultsError) && (
        <div className="px-6 pt-3 shrink-0">
          <Alert variant="destructive">
            <AlertDescription>{schemasError || resultsError}</AlertDescription>
          </Alert>
        </div>
      )}

      {/* Two-panel layout */}
      <div className="flex flex-1 min-h-0">
        {/* Left panel */}
        <div className="w-72 border-r shrink-0 flex flex-col">
          <DocumentSelector
            documents={documents}
            isLoading={documentsLoading}
            selectedDocumentId={selectedDocumentId}
            onSelect={handleSelectDocument}
            onUploadClick={() => setUploadDialogOpen(true)}
          />
        </div>

        {/* Right panel */}
        <div className="flex-1 overflow-y-auto">
          {!selectedDocumentId ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-6">
              <FileSearch className="h-12 w-12 text-muted-foreground/40 mb-4" />
              <h2 className="text-lg font-medium text-muted-foreground">Select a document to get started</h2>
              <p className="text-sm text-muted-foreground/70 mt-1 max-w-sm">
                Choose a document from the list, or upload a new one to begin extracting structured data.
              </p>
            </div>
          ) : (
            <div className="p-6 space-y-6 max-w-3xl">
              <SchemaManager schemas={schemas} onEdit={handleEditSchema} onDelete={handleDeleteSchema} onCreate={handleCreateSchema} />

              <Separator />

              {selectedDocument && (
                <div className="flex items-center gap-3">
                  <h2 className="text-base font-medium truncate">{selectedDocument.title}</h2>
                  <Badge
                    variant={selectedDocument.status === 'ready' ? 'outline' : selectedDocument.status === 'processing' ? 'secondary' : 'destructive'}
                    className="shrink-0 text-xs"
                  >
                    {selectedDocument.status}
                  </Badge>
                  <span className="text-xs text-muted-foreground shrink-0">
                    Uploaded {new Date(selectedDocument.createdAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </span>
                </div>
              )}

              {/* Run New Extraction */}
              <div>
                <h3 className="text-sm font-medium mb-3">Run New Extraction</h3>
                {!isDocumentReady ? (
                  <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
                    {selectedDocument?.status === 'processing'
                      ? 'Document is still processing. Extraction will be available once it completes.'
                      : 'This document cannot be used for extraction.'}
                  </div>
                ) : parseRunsLoading ? (
                  <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
                    Loading...
                  </div>
                ) : (
                  <div className="rounded-lg border p-4">
                    <ExtractionForm
                      defaultParser={defaultParser}
                      defaultParserConfig={defaultParserConfig}
                      schemas={schemas}
                      extractors={extractors}
                      onRun={handleRunExtraction}
                      onEditSchema={handleEditSchema}
                    />
                  </div>
                )}
              </div>

              <Separator />

              {/* Previous Extractions */}
              <div>
                <h3 className="text-sm font-medium mb-3">
                  Previous Extractions
                  {results.length > 0 && (
                    <span className="text-muted-foreground font-normal ml-1.5">({results.length})</span>
                  )}
                </h3>
                <ExtractionHistory
                  results={results}
                  isLoading={resultsLoading}
                  selectedResult={selectedResult}
                  isLoadingResult={isLoadingResult}
                  onSelectResult={selectResult}
                  inProgressPhase={inProgressPhase}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      <ExtractionSchemaEditor
        open={schemaEditorOpen}
        onOpenChange={setSchemaEditorOpen}
        schema={editingSchema}
        onSave={handleSaveSchema}
      />

      <DocumentUploadDialog
        open={uploadDialogOpen}
        onOpenChange={setUploadDialogOpen}
        onUpload={handleUpload}
        projectId={projectId || ''}
      />
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles cleanly**

```bash
npx --prefix frontend tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Run full test suite**

```bash
npx --prefix frontend vitest run
```

Expected: all tests pass including the new hook tests.

- [ ] **Step 4: Build to catch any remaining issues**

```bash
npx --prefix frontend vite build
```

Expected: build succeeds with no errors.

- [ ] **Step 5: Manual verification**

Start the dev server and verify:

1. **Pre-populated defaults** — Select a document that has an existing parse run. The Parse Configuration section shows the correct parser type and config pre-filled.

2. **Parser switching** — Change the parser dropdown. Config fields update (LlamaParse shows tier/expand; Landing AI shows model selector; Simple/Docling show nothing). Switching parser resets config to defaults.

3. **Reuse path (no parse triggered)** — Select a document with an existing succeeded parse run. Keep the same parser + config as the existing run. Click Run Extraction. Verify in network DevTools: no `POST /parse-runs` call fires. Only `POST /extractions/run` fires.

4. **Fresh parse path** — Select a document. Change the parser to a config that has no existing parse run. Click Run Extraction. Verify: `POST /parse-runs` fires, then "Parsing document…" spinner appears in the history area, then transitions to the real pending extraction result row.

5. **Parse failure** — If you can trigger a parse failure (e.g., invalid API key for LlamaParse), verify: the history area shows the error message with a Retry button. Clicking Retry re-triggers the flow.

6. **No parse run pre-existing** — Select a document that has never been parsed. The form still shows (no "parse document first" placeholder). Parser defaults to Simple. Run extraction — triggers parse then extraction.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ExtractionPage.tsx
git commit -m "feat(extraction): wire parse config orchestration into ExtractionPage"
```
