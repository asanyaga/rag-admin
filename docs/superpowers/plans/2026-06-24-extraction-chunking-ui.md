# Extraction Chunking UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface chunking config, citation granularity, and chunking result metadata in the extraction UI (frontend only).

**Architecture:** The `/extractions/run` endpoint already accepts `chunking`/`preprocess`. This plan threads those fields through the frontend types + `runExtractionWithParse` hook, adds hand-built LLM-only controls to `ExtractionForm`, and adds a result-side summary to `ExtractionResultViewer`. No backend changes.

**Tech Stack:** React 18, TypeScript, Vite, shadcn/ui (Radix), Tailwind, Vitest + Testing Library + happy-dom.

## Global Constraints

- All frontend commands run from the `frontend/` directory (e.g. `npx vitest run <path>`).
- Spec: `docs/superpowers/specs/2026-06-24-extraction-chunking-ui-design.md`. Issue: #102.
- Controls are LLM-method-only; default `strategy: none` + `citationLevel: auto` → request must be byte-identical to today (no `chunking` key sent).
- Hand-built controls (no schema-driven renderer, no new endpoints). No `preprocess` UI (type is forwarded only).
- Match existing form/component patterns (shadcn `Select`, `Input`, `Collapsible`, `Badge`).

---

## File Structure

- `frontend/src/types/extraction.ts` — add `ChunkingConfig`, `PreprocessStage`; extend `RunExtractionRequest` and `RunWithParseRequest.extractionConfig`.
- `frontend/src/hooks/useExtractionResults.ts` — forward `chunking`/`preprocess` in `runExtractionWithParse`.
- `frontend/src/test/setup.ts` — add Radix pointer-capture/scrollIntoView polyfills for Select tests.
- `frontend/src/components/extraction/ExtractionForm.tsx` — "Large document handling" controls + request building.
- `frontend/src/components/extraction/ChunkingSummary.tsx` — new presentational summary component.
- `frontend/src/components/extraction/ExtractionResultViewer.tsx` — render `ChunkingSummary`.

---

## Task 1: Forward chunking/preprocess through types + hook

**Files:**
- Modify: `frontend/src/types/extraction.ts:61-68` (and `RunWithParseRequest` at `80-94`)
- Modify: `frontend/src/hooks/useExtractionResults.ts:223-230`
- Test: `frontend/src/hooks/useExtractionResults.test.ts`

**Interfaces:**
- Produces: `ChunkingConfig { strategy: string; config?: Record<string, unknown>; citationLevel?: 'auto'|'full'|'page_only'|'off' }`; `PreprocessStage { stage: string; config: Record<string, unknown> }`. `RunExtractionRequest` and `RunWithParseRequest.extractionConfig` gain optional `chunking?: ChunkingConfig` and `preprocess?: PreprocessStage[]`.

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/hooks/useExtractionResults.test.ts` inside the `describe('runExtractionWithParse', ...)` block:

```ts
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run src/hooks/useExtractionResults.test.ts -t "forwards chunking"`
Expected: FAIL — `runExtraction` called without a `chunking` property (and a TS error that `chunking` is not assignable to `extractionConfig`).

- [ ] **Step 3: Add the types**

In `frontend/src/types/extraction.ts`, add after `RunExtractionRequest` (around line 68):

```ts
export interface ChunkingConfig {
  strategy: string
  config?: Record<string, unknown>
  citationLevel?: 'auto' | 'full' | 'page_only' | 'off'
}

export interface PreprocessStage {
  stage: string
  config: Record<string, unknown>
}
```

Extend `RunExtractionRequest` (lines 61-68) to:

```ts
export interface RunExtractionRequest {
  parseRunId: string
  extractionSchemaId: string
  extractionMethod: string
  config?: Record<string, unknown>
  llmConfig?: PromptConfig
  userPromptTemplate?: string
  chunking?: ChunkingConfig
  preprocess?: PreprocessStage[]
}
```

Extend `RunWithParseRequest.extractionConfig` (lines 87-93) to add the two fields:

```ts
  extractionConfig: {
    extractionSchemaId: string
    extractionMethod: string
    config?: Record<string, unknown>
    llmConfig?: PromptConfig
    userPromptTemplate?: string
    chunking?: ChunkingConfig
    preprocess?: PreprocessStage[]
  }
```

- [ ] **Step 4: Forward the fields in the hook**

In `frontend/src/hooks/useExtractionResults.ts`, update the `runExtraction` call (lines 223-230) to:

```ts
        await extractionApi.runExtraction({
          parseRunId: parseRunId!,
          extractionSchemaId: extractionConfig.extractionSchemaId,
          extractionMethod: extractionConfig.extractionMethod,
          config: extractionConfig.config,
          llmConfig: extractionConfig.llmConfig,
          userPromptTemplate: extractionConfig.userPromptTemplate,
          chunking: extractionConfig.chunking,
          preprocess: extractionConfig.preprocess,
        })
```

- [ ] **Step 5: Run tests to verify they pass**

Run (from `frontend/`): `npx vitest run src/hooks/useExtractionResults.test.ts`
Expected: PASS (all existing tests + the new one).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/extraction.ts frontend/src/hooks/useExtractionResults.ts frontend/src/hooks/useExtractionResults.test.ts
git commit -m "feat(extraction-ui): forward chunking/preprocess through types and run hook"
```

---

## Task 2: "Large document handling" controls in ExtractionForm

**Files:**
- Modify: `frontend/src/test/setup.ts`
- Modify: `frontend/src/components/extraction/ExtractionForm.tsx`
- Test: `frontend/src/components/extraction/ExtractionForm.test.tsx`

**Interfaces:**
- Consumes: `ChunkingConfig` (Task 1).
- Produces: form emits `extractionConfig.chunking` per the rules: built only when `strategy !== 'none'` or `citationLevel !== 'auto'`; never for `llamaextract`.

- [ ] **Step 1: Add Radix test polyfills**

Radix `Select` relies on pointer-capture and `scrollIntoView`, which happy-dom lacks. Append to `frontend/src/test/setup.ts`:

```ts
// Radix UI Select/Dropdown rely on pointer capture + scrollIntoView, absent in happy-dom
if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false
}
if (!Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = () => {}
}
if (!Element.prototype.releasePointerCapture) {
  Element.prototype.releasePointerCapture = () => {}
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}
```

- [ ] **Step 2: Write the failing tests**

Add to `frontend/src/components/extraction/ExtractionForm.test.tsx`. First add an `llmExtractor` constant near the top (after the existing `extractor` const):

```ts
const llmExtractor: ExtractorInfo = {
  extractionMethod: 'llm',
  name: 'LLM',
  description: 'Generic LLM extraction',
  configSchema: null,
  configured: true,
}
```

Then add these tests inside `describe('ExtractionForm', ...)`:

```ts
it('omits chunking from the request when LLM defaults are unchanged', async () => {
  const user = userEvent.setup()
  const onRun = vi.fn().mockResolvedValue(undefined)
  render(<ExtractionForm {...defaultProps} extractors={[llmExtractor]} onRun={onRun} />)
  await act(async () => {})
  await user.click(screen.getByRole('button', { name: /run extraction/i }))
  const arg = onRun.mock.calls[0][0]
  expect(arg.extractionConfig.chunking).toBeUndefined()
})

it('does not show Large document handling for llamaextract', () => {
  render(<ExtractionForm {...defaultProps} onRun={vi.fn()} />)
  expect(screen.queryByText(/large document handling/i)).not.toBeInTheDocument()
})

it('emits token_budget_pages chunking with default max input tokens', async () => {
  const user = userEvent.setup()
  const onRun = vi.fn().mockResolvedValue(undefined)
  render(<ExtractionForm {...defaultProps} extractors={[llmExtractor]} onRun={onRun} />)
  await act(async () => {})

  await user.click(screen.getByRole('button', { name: /large document handling/i }))
  await user.click(screen.getByRole('combobox', { name: /chunking strategy/i }))
  await user.click(screen.getByRole('option', { name: /token-budgeted pages/i }))
  await user.click(screen.getByRole('button', { name: /run extraction/i }))

  const arg = onRun.mock.calls[0][0]
  expect(arg.extractionConfig.chunking).toEqual({
    strategy: 'token_budget_pages',
    config: { maxInputTokens: 8000 },
    citationLevel: 'auto',
  })
})

it('emits citation-only chunking when only citation level changes', async () => {
  const user = userEvent.setup()
  const onRun = vi.fn().mockResolvedValue(undefined)
  render(<ExtractionForm {...defaultProps} extractors={[llmExtractor]} onRun={onRun} />)
  await act(async () => {})

  await user.click(screen.getByRole('button', { name: /large document handling/i }))
  await user.click(screen.getByRole('combobox', { name: /citation detail/i }))
  await user.click(screen.getByRole('option', { name: /page only/i }))
  await user.click(screen.getByRole('button', { name: /run extraction/i }))

  const arg = onRun.mock.calls[0][0]
  expect(arg.extractionConfig.chunking).toEqual({ strategy: 'none', citationLevel: 'page_only' })
})
```

- [ ] **Step 3: Run tests to verify they fail**

Run (from `frontend/`): `npx vitest run src/components/extraction/ExtractionForm.test.tsx`
Expected: FAIL — new tests fail (no "Large document handling" control; `chunking` never set).

- [ ] **Step 4: Add imports, state, and controls**

In `frontend/src/components/extraction/ExtractionForm.tsx`, add imports:

```ts
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { Pencil, Play, ChevronDown } from 'lucide-react'
import type { ExtractionSchema, ExtractorInfo, RunWithParseRequest, ChunkingConfig } from '@/types/extraction'
```

(Replace the existing `lucide-react` import line and the existing type import line with the versions above.)

Add state alongside the other LLM state (after line 60):

```ts
  const [chunkStrategy, setChunkStrategy] = useState<'none' | 'token_budget_pages'>('none')
  const [maxInputTokens, setMaxInputTokens] = useState('8000')
  const [pageOverlap, setPageOverlap] = useState('0')
  const [dedupeKey, setDedupeKey] = useState('')
  const [citationLevel, setCitationLevel] =
    useState<'auto' | 'full' | 'page_only' | 'off'>('auto')
```

In `handleRun`, replace the `else if (extractionMethod === 'llm')` branch (lines 131-138) with:

```ts
    } else if (extractionMethod === 'llm') {
      let chunking: ChunkingConfig | undefined
      if (chunkStrategy !== 'none') {
        const cfg: Record<string, unknown> = {}
        const max = parseInt(maxInputTokens, 10)
        if (!Number.isNaN(max)) cfg.maxInputTokens = max
        const overlap = parseInt(pageOverlap, 10)
        if (!Number.isNaN(overlap) && overlap > 0) cfg.pageOverlap = overlap
        if (dedupeKey.trim()) cfg.dedupeKey = dedupeKey.trim()
        chunking = { strategy: chunkStrategy, config: cfg, citationLevel }
      } else if (citationLevel !== 'auto') {
        chunking = { strategy: 'none', citationLevel }
      }
      extractionConfig = {
        extractionSchemaId: schemaId,
        extractionMethod,
        config: { structured_output_mode: structuredOutputMode, inject_block_ids: injectBlockIds },
        llmConfig: promptConfig,
        userPromptTemplate: userPromptTemplate.trim() || undefined,
        ...(chunking ? { chunking } : {}),
      }
    }
```

Add the controls inside the LLM config block, immediately before its closing `</div>` (after the output-mode grid that ends at line 309):

```tsx
          <Collapsible>
            <CollapsibleTrigger asChild>
              <Button variant="ghost" size="sm" className="w-full justify-between px-0">
                <span className="text-xs font-medium">Large document handling</span>
                <ChevronDown className="h-4 w-4" />
              </Button>
            </CollapsibleTrigger>
            <CollapsibleContent className="space-y-3 pt-2">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs">Chunking</Label>
                  <Select value={chunkStrategy} onValueChange={(v) => setChunkStrategy(v as 'none' | 'token_budget_pages')}>
                    <SelectTrigger className="h-9" aria-label="Chunking strategy"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">None (single-shot)</SelectItem>
                      <SelectItem value="token_budget_pages">Token-budgeted pages</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs">Citation detail</Label>
                  <Select value={citationLevel} onValueChange={(v) => setCitationLevel(v as 'auto' | 'full' | 'page_only' | 'off')}>
                    <SelectTrigger className="h-9" aria-label="Citation detail"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="auto">Auto</SelectItem>
                      <SelectItem value="full">Full</SelectItem>
                      <SelectItem value="page_only">Page only</SelectItem>
                      <SelectItem value="off">Off</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              {chunkStrategy === 'token_budget_pages' && (
                <div className="grid grid-cols-3 gap-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs">Max input tokens</Label>
                    <Input type="number" value={maxInputTokens} onChange={(e) => setMaxInputTokens(e.target.value)} className="h-9" />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs">Page overlap</Label>
                    <Input type="number" value={pageOverlap} onChange={(e) => setPageOverlap(e.target.value)} className="h-9" />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs">Dedupe key</Label>
                    <Input value={dedupeKey} onChange={(e) => setDedupeKey(e.target.value)} placeholder="e.g. sku" className="h-9" />
                  </div>
                </div>
              )}
              <p className="text-[11px] text-muted-foreground">
                {citationLevel === 'off'
                  ? 'No provenance will be captured.'
                  : 'Auto uses page-level provenance on large documents. Chunking splits big docs to avoid truncation and rate limits.'}
              </p>
            </CollapsibleContent>
          </Collapsible>
```

- [ ] **Step 5: Run tests to verify they pass**

Run (from `frontend/`): `npx vitest run src/components/extraction/ExtractionForm.test.tsx`
Expected: PASS (existing + 4 new tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/test/setup.ts frontend/src/components/extraction/ExtractionForm.tsx frontend/src/components/extraction/ExtractionForm.test.tsx
git commit -m "feat(extraction-ui): add LLM-only chunking + citation controls to ExtractionForm"
```

---

## Task 3: Chunking result summary in ExtractionResultViewer

**Files:**
- Create: `frontend/src/components/extraction/ChunkingSummary.tsx`
- Create: `frontend/src/components/extraction/ChunkingSummary.test.tsx`
- Modify: `frontend/src/components/extraction/ExtractionResultViewer.tsx`

**Interfaces:**
- Produces: `ChunkingSummary({ metadata }: { metadata: Record<string, unknown> | null | undefined })` — renders a chunk-count/usage strip and a scalar-conflicts callout; renders `null` when none present.

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/extraction/ChunkingSummary.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ChunkingSummary } from './ChunkingSummary'

describe('ChunkingSummary', () => {
  it('renders chunk count and token usage when present', () => {
    render(<ChunkingSummary metadata={{ chunkCount: 3, usage: { total_tokens: 4210 } }} />)
    expect(screen.getByText(/3 chunks/i)).toBeInTheDocument()
    expect(screen.getByText(/4,210 tokens/i)).toBeInTheDocument()
  })

  it('renders a conflicts callout when scalarConflicts present', () => {
    render(
      <ChunkingSummary
        metadata={{ chunkCount: 2, scalarConflicts: [{ path: 'currency', kept: 'EUR', discarded: 'USD' }] }}
      />
    )
    expect(screen.getByText(/conflicting values/i)).toBeInTheDocument()
    expect(screen.getByText(/currency/)).toBeInTheDocument()
  })

  it('renders nothing when metadata lacks chunking fields', () => {
    const { container } = render(<ChunkingSummary metadata={{ model: 'x', usage: {} }} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when metadata is null', () => {
    const { container } = render(<ChunkingSummary metadata={null} />)
    expect(container).toBeEmptyDOMElement()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `frontend/`): `npx vitest run src/components/extraction/ChunkingSummary.test.tsx`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/extraction/ChunkingSummary.tsx`:

```tsx
import { Badge } from '@/components/ui/badge'

interface ScalarConflict {
  path: string
  kept: unknown
  discarded: unknown
}

interface ChunkingSummaryProps {
  metadata: Record<string, unknown> | null | undefined
}

export function ChunkingSummary({ metadata }: ChunkingSummaryProps) {
  if (!metadata) return null

  const chunkCount = typeof metadata.chunkCount === 'number' ? metadata.chunkCount : undefined
  const usage = metadata.usage as { total_tokens?: number } | undefined
  const totalTokens =
    usage && typeof usage.total_tokens === 'number' ? usage.total_tokens : undefined
  const conflicts: ScalarConflict[] = Array.isArray(metadata.scalarConflicts)
    ? (metadata.scalarConflicts as ScalarConflict[])
    : []

  if (chunkCount === undefined && totalTokens === undefined && conflicts.length === 0) {
    return null
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {chunkCount !== undefined && (
          <Badge variant="secondary">
            {chunkCount} chunk{chunkCount === 1 ? '' : 's'}
          </Badge>
        )}
        {totalTokens !== undefined && (
          <Badge variant="outline">{totalTokens.toLocaleString()} tokens</Badge>
        )}
      </div>
      {conflicts.length > 0 && (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800">
          <p className="font-medium">Conflicting values across chunks ({conflicts.length})</p>
          <ul className="mt-1 space-y-0.5">
            {conflicts.map((c, i) => (
              <li key={i}>
                <code>{c.path}</code>: kept {String(c.kept)} ≠ {String(c.discarded)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `frontend/`): `npx vitest run src/components/extraction/ChunkingSummary.test.tsx`
Expected: PASS.

- [ ] **Step 5: Render it in the viewer**

In `frontend/src/components/extraction/ExtractionResultViewer.tsx`, add the import:

```ts
import { ChunkingSummary } from './ChunkingSummary'
```

Render it as the first child of the outer container, just after `if (!result) return null` — change the opening of the returned JSX from:

```tsx
  return (
    <div className="space-y-4">
      <Card>
```

to:

```tsx
  return (
    <div className="space-y-4">
      <ChunkingSummary metadata={result.extractionMetadata} />
      <Card>
```

- [ ] **Step 6: Run the full extraction component suite**

Run (from `frontend/`): `npx vitest run src/components/extraction`
Expected: PASS (ChunkingSummary, ExtractionForm, ExtractionResultViewer suites all green).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/extraction/ChunkingSummary.tsx frontend/src/components/extraction/ChunkingSummary.test.tsx frontend/src/components/extraction/ExtractionResultViewer.tsx
git commit -m "feat(extraction-ui): show chunk count, usage, and scalar conflicts in result viewer"
```

---

## Task 4: Type-check + build gate

**Files:** none (verification only)

- [ ] **Step 1: Type-check**

Run (from `frontend/`): `npx tsc --noEmit`
Expected: exit 0 (no type errors).

- [ ] **Step 2: Lint**

Run (from `frontend/`): `npm run lint`
Expected: no new errors in the changed files. Fix any introduced.

- [ ] **Step 3: Build**

Run (from `frontend/`): `npm run build`
Expected: success.

---

## Self-Review Notes

- **Spec coverage:** controls LLM-only + collapsible + default none (T2); strategy/params/citation controls (T2); type + hook forwarding (T1); request built only when non-default and never for llamaextract (T2 + tests); result summary with chunk count/usage/conflicts (T3); truncation via existing `statusMessage` (no change needed, noted in spec); tests across all three (every task). All spec sections map to a task.
- **Backward compatibility:** `chunking` omitted when defaults unchanged (T2 test `omits chunking ...`); `preprocess` type forwarded but no UI.
- **Type consistency:** `ChunkingConfig` shape (T1) matches the object built in `ExtractionForm.handleRun` (T2) and the hook forwarding (T1). `ChunkingSummary` prop type `Record<string, unknown> | null | undefined` matches `ExtractionResult.extractionMetadata` (`Record<string, unknown> | null`).
- **Radix test reliability:** pointer-capture/scrollIntoView polyfills added in T2 (setup.ts); selects targeted by `aria-label` so option-clicks are unambiguous.
