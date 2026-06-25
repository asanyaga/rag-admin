# LlamaExtract UI Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the extraction frontend to wire up the CDM-based backend: fix the `documentId` → `parseRunId` mismatch, expose the `configured` flag, add LlamaExtract-specific config options, and display `provider_response_raw` in the result viewer.

**Architecture:** `ExtractionPage` calls `useParseRuns` to find the latest succeeded/partial parse run for the selected document and passes its `id` as `parseRunId` to `ExtractionForm`. `ExtractionForm` builds `RunExtractionRequest` with `parseRunId` (which the Axios camelCase serialiser sends as `parse_run_id`). LlamaExtract-specific config controls (`extraction_target`, `confidence_scores`) are conditionally shown based on `extractionMethod`. The result viewer gains a "Provider Response" collapsible for `providerResponseRaw`.

**Tech Stack:** React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS, Vitest + React Testing Library

---

## File map

| File | Action | Responsibility |
|---|---|---|
| `frontend/src/types/extraction.ts` | Modify | Fix `RunExtractionRequest`, add result fields, add `configured` to `ExtractorInfo` |
| `frontend/src/pages/ExtractionPage.tsx` | Modify | Call `useParseRuns`, derive `latestViableRun`, pass `parseRunId` to form |
| `frontend/src/components/extraction/ExtractionForm.tsx` | Modify | Change `documentId` prop to `parseRunId`; add extractor-specific controls; disable unconfigured |
| `frontend/src/components/extraction/ExtractionForm.test.tsx` | Create | Unit tests for form behaviour |
| `frontend/src/components/extraction/ExtractionResultViewer.tsx` | Modify | Rename metadata section; add Provider Response collapsible |
| `frontend/src/components/extraction/ExtractionResultViewer.test.tsx` | Create | Unit tests for viewer section visibility |

---

## Task 1: Update extraction TypeScript types

**Files:**
- Modify: `frontend/src/types/extraction.ts`

These are pure type changes — the TypeScript compiler validates them. No runtime tests needed.

- [ ] **Step 1: Replace file contents**

Open `frontend/src/types/extraction.ts` and replace the entire file with:

```typescript
export type ExtractionResultStatus = 'pending' | 'completed' | 'failed'

export interface ExtractionSchema {
  id: string
  projectId: string
  name: string
  description: string | null
  schemaDefinition: Record<string, unknown>
  extractionTarget: string
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface ExtractionSchemaCreate {
  name: string
  description?: string
  schemaDefinition: Record<string, unknown>
  extractionTarget?: string
}

export interface ExtractionSchemaUpdate {
  name?: string
  description?: string
  schemaDefinition?: Record<string, unknown>
  extractionTarget?: string
}

export interface ExtractionResult {
  id: string
  documentId: string
  extractionSchemaId: string
  schemaDefinitionSnapshot: Record<string, unknown>
  extractionMethod: string
  config: Record<string, unknown> | null
  structuredData: Record<string, unknown> | null
  extractionMetadata: Record<string, unknown> | null
  citations: Record<string, unknown>[] | null
  providerResponseRaw: Record<string, unknown> | null
  sourceParseRunId: string | null
  status: ExtractionResultStatus
  statusMessage: string | null
  startedAt: string | null
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface ExtractionResultListItem {
  id: string
  documentId: string
  extractionSchemaId: string
  extractionMethod: string
  status: ExtractionResultStatus
  statusMessage: string | null
  createdAt: string
}

export interface RunExtractionRequest {
  parseRunId: string
  extractionSchemaId: string
  extractionMethod: string
  config?: Record<string, unknown>
}

export interface ExtractorInfo {
  extractionMethod: string
  name: string
  description: string
  configSchema: Record<string, unknown> | null
  configured: boolean
}
```

- [ ] **Step 2: Check for type errors**

Run: `npm --prefix frontend run build 2>&1 | grep "error TS"`

Expected: errors only in `ExtractionForm.tsx` complaining that prop `documentId` no longer exists on `RunExtractionRequest` — those are fixed in Task 2. No other files should have errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/extraction.ts
git commit -m "feat(extraction): add configured, parseRunId, citations, providerResponseRaw to extraction types"
```

---

## Task 2: Resolve parse run ID and update ExtractionForm

**Files:**
- Modify: `frontend/src/pages/ExtractionPage.tsx`
- Modify: `frontend/src/components/extraction/ExtractionForm.tsx`
- Create: `frontend/src/components/extraction/ExtractionForm.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/extraction/ExtractionForm.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ExtractionForm } from './ExtractionForm'
import type { ExtractionSchema, ExtractorInfo } from '@/types/extraction'

const schema: ExtractionSchema = {
  id: 'schema-1',
  projectId: 'proj-1',
  name: 'Test Schema',
  description: null,
  schemaDefinition: {},
  extractionTarget: 'PER_DOC',
  createdBy: 'user-1',
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
}

const extractor: ExtractorInfo = {
  extractionMethod: 'llamaextract',
  name: 'LlamaExtract',
  description: 'LlamaExtract via LlamaCloud',
  configSchema: null,
  configured: true,
}

describe('ExtractionForm', () => {
  it('calls onRun with parseRunId in request', async () => {
    const user = userEvent.setup()
    const onRun = vi.fn().mockResolvedValue(undefined)
    render(
      <ExtractionForm
        parseRunId="parse-run-123"
        schemas={[schema]}
        extractors={[extractor]}
        onRun={onRun}
      />
    )
    await user.click(screen.getByRole('button', { name: /run extraction/i }))
    await waitFor(() => {
      expect(onRun).toHaveBeenCalledWith(
        expect.objectContaining({ parseRunId: 'parse-run-123' })
      )
    })
  })
})
```

- [ ] **Step 2: Run test to see it fail**

Run: `npx --prefix frontend vitest run src/components/extraction/ExtractionForm.test.tsx`

Expected: FAIL — prop `parseRunId` does not exist on `ExtractionFormProps` (TypeScript error) or `documentId` is sent instead of `parseRunId`

- [ ] **Step 3: Update ExtractionForm**

In `frontend/src/components/extraction/ExtractionForm.tsx`:

Change the `ExtractionFormProps` interface — replace `documentId: string` with `parseRunId: string`:

```tsx
interface ExtractionFormProps {
  parseRunId: string
  schemas: ExtractionSchema[]
  extractors: ExtractorInfo[]
  onRun: (request: RunExtractionRequest) => Promise<void>
  onEditSchema?: (schema: ExtractionSchema) => void
}
```

Change the function signature destructure — replace `documentId` with `parseRunId`:

```tsx
export function ExtractionForm({
  parseRunId,
  schemas,
  extractors,
  onRun,
  onEditSchema,
}: ExtractionFormProps) {
```

In `handleRun`, change the `onRun` call from:

```tsx
await onRun({
  documentId,
  extractionSchemaId: schemaId,
  extractionMethod,
  config,
})
```

to:

```tsx
await onRun({
  parseRunId,
  extractionSchemaId: schemaId,
  extractionMethod,
  config,
})
```

- [ ] **Step 4: Update ExtractionPage to resolve the parse run**

In `frontend/src/pages/ExtractionPage.tsx`:

Add the import after the existing hook imports:

```tsx
import { useParseRuns } from '@/hooks/useParseRuns'
```

After the `useExtractionResults(...)` call, add:

```tsx
const { parseRuns } = useParseRuns(selectedDocumentId)
const latestViableRun = parseRuns.find(
  (r) => r.status === 'succeeded' || r.status === 'partial'
)
```

Replace the extraction form rendering block (the `isDocumentReady ? (...)` ternary that wraps `<ExtractionForm>`) with:

```tsx
{isDocumentReady ? (
  latestViableRun ? (
    <div className="rounded-lg border p-4">
      <ExtractionForm
        parseRunId={latestViableRun.id}
        schemas={schemas}
        extractors={extractors}
        onRun={handleRunExtraction}
        onEditSchema={handleEditSchema}
      />
    </div>
  ) : (
    <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
      Parse the document first to enable extraction.
    </div>
  )
) : (
  <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
    {selectedDocument?.status === 'processing'
      ? 'Document is still processing. Extraction will be available once it completes.'
      : 'This document cannot be used for extraction.'}
  </div>
)}
```

Also update the inline hint above the form block. Replace:

```tsx
{!isDocumentReady && selectedDocument && (
  <span className="text-xs text-muted-foreground">
    (document must be ready)
  </span>
)}
```

with:

```tsx
{(!isDocumentReady || !latestViableRun) && selectedDocument && (
  <span className="text-xs text-muted-foreground">
    {isDocumentReady ? '(parse document first)' : '(document must be ready)'}
  </span>
)}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npx --prefix frontend vitest run src/components/extraction/ExtractionForm.test.tsx`

Expected: PASS

- [ ] **Step 6: Build to verify no TypeScript errors**

Run: `npm --prefix frontend run build 2>&1 | grep "error TS"`

Expected: no output

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/ExtractionPage.tsx frontend/src/components/extraction/ExtractionForm.tsx frontend/src/components/extraction/ExtractionForm.test.tsx
git commit -m "feat(extraction): resolve parse run ID from document; change ExtractionForm prop documentId → parseRunId"
```

---

## Task 3: Disable unconfigured extractors

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionForm.tsx`
- Modify: `frontend/src/components/extraction/ExtractionForm.test.tsx`

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/components/extraction/ExtractionForm.test.tsx`:

```tsx
it('disables Run button and shows warning when selected extractor is not configured', async () => {
  const unconfigured: ExtractorInfo = { ...extractor, configured: false }
  render(
    <ExtractionForm
      parseRunId="run-1"
      schemas={[schema]}
      extractors={[unconfigured]}
      onRun={vi.fn()}
    />
  )
  await waitFor(() => {
    expect(screen.getByRole('button', { name: /run extraction/i })).toBeDisabled()
  })
  expect(screen.getByText(/not configured/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to see it fail**

Run: `npx --prefix frontend vitest run src/components/extraction/ExtractionForm.test.tsx`

Expected: FAIL — button is enabled, no "not configured" text

- [ ] **Step 3: Add configured check to ExtractionForm**

In `frontend/src/components/extraction/ExtractionForm.tsx`, add these two lines immediately after the state declarations (before `handleRun`):

```tsx
const selectedExtractor = extractors.find((e) => e.extractionMethod === extractionMethod)
const isConfigured = selectedExtractor?.configured ?? true
```

Change the Run button's `disabled` prop from `disabled={isRunning}` to:

```tsx
<Button onClick={handleRun} disabled={isRunning || !isConfigured} size="sm">
```

After the existing `{error && <p className="text-sm text-destructive">{error}</p>}` line, add:

```tsx
{!isConfigured && (
  <p className="text-xs text-amber-600">
    {selectedExtractor?.name ?? 'This extractor'} is not configured. Contact your administrator.
  </p>
)}
```

In the multi-extractor `<Select>`, update each `<SelectItem>` to disable unconfigured options:

```tsx
{extractors.map((e) => (
  <SelectItem key={e.extractionMethod} value={e.extractionMethod} disabled={!e.configured}>
    {e.name}{!e.configured ? ' (not configured)' : ''}
  </SelectItem>
))}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx --prefix frontend vitest run src/components/extraction/ExtractionForm.test.tsx`

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/extraction/ExtractionForm.tsx frontend/src/components/extraction/ExtractionForm.test.tsx
git commit -m "feat(extraction): disable Run button and show warning for unconfigured extractors"
```

---

## Task 4: Add LlamaExtract-specific config options

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionForm.tsx`
- Modify: `frontend/src/components/extraction/ExtractionForm.test.tsx`

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/components/extraction/ExtractionForm.test.tsx`:

```tsx
it('shows extraction target and confidence scores controls for llamaextract', () => {
  render(
    <ExtractionForm
      parseRunId="run-1"
      schemas={[schema]}
      extractors={[extractor]}
      onRun={vi.fn()}
    />
  )
  expect(screen.getByLabelText(/target/i)).toBeInTheDocument()
  expect(screen.getByLabelText(/confidence scores/i)).toBeInTheDocument()
})

it('includes confidence_scores in config when checked', async () => {
  const user = userEvent.setup()
  const onRun = vi.fn().mockResolvedValue(undefined)
  render(
    <ExtractionForm
      parseRunId="run-1"
      schemas={[schema]}
      extractors={[extractor]}
      onRun={onRun}
    />
  )
  await user.click(screen.getByLabelText(/confidence scores/i))
  await user.click(screen.getByRole('button', { name: /run extraction/i }))
  await waitFor(() => {
    expect(onRun).toHaveBeenCalledWith(
      expect.objectContaining({
        config: expect.objectContaining({ confidence_scores: true }),
      })
    )
  })
})

it('includes extraction_target in config for llamaextract', async () => {
  const user = userEvent.setup()
  const onRun = vi.fn().mockResolvedValue(undefined)
  render(
    <ExtractionForm
      parseRunId="run-1"
      schemas={[schema]}
      extractors={[extractor]}
      onRun={onRun}
    />
  )
  await user.click(screen.getByRole('button', { name: /run extraction/i }))
  await waitFor(() => {
    expect(onRun).toHaveBeenCalledWith(
      expect.objectContaining({
        config: expect.objectContaining({ extraction_target: 'PER_DOC' }),
      })
    )
  })
})
```

- [ ] **Step 2: Run tests to see them fail**

Run: `npx --prefix frontend vitest run src/components/extraction/ExtractionForm.test.tsx`

Expected: FAIL — no target or confidence scores labels found

- [ ] **Step 3: Add state variables for new options**

In `frontend/src/components/extraction/ExtractionForm.tsx`, add after the existing state declarations (`pageRange`, `isRunning`, `error`):

```tsx
const [extractionTarget, setExtractionTarget] = useState('PER_DOC')
const [confidenceScores, setConfidenceScores] = useState(false)
```

- [ ] **Step 4: Update handleRun to include LlamaExtract-specific config**

In `handleRun`, after the existing config building block (the `if (pageRange.trim())` line), add:

```tsx
if (extractionMethod === 'llamaextract') {
  config.extraction_target = extractionTarget
  if (confidenceScores) config.confidence_scores = true
}
```

- [ ] **Step 5: Add the UI controls**

In `frontend/src/components/extraction/ExtractionForm.tsx`, add the following block after the closing `</div>` of the Mode / Page Range grid (the `<div className="grid grid-cols-2 gap-3">` block):

```tsx
{extractionMethod === 'llamaextract' && (
  <div className="grid grid-cols-2 gap-3">
    <div className="space-y-1.5">
      <Label htmlFor="extraction-target" className="text-xs">Target</Label>
      <Select value={extractionTarget} onValueChange={setExtractionTarget}>
        <SelectTrigger id="extraction-target" className="h-9">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="PER_DOC">Per Document</SelectItem>
          <SelectItem value="PER_PAGE">Per Page</SelectItem>
        </SelectContent>
      </Select>
    </div>
    <div className="flex items-end pb-2">
      <div className="flex items-center space-x-2">
        <Checkbox
          id="confidence-scores"
          checked={confidenceScores}
          onCheckedChange={(checked) => setConfidenceScores(checked === true)}
        />
        <Label htmlFor="confidence-scores" className="text-xs font-normal">
          Confidence Scores
        </Label>
      </div>
    </div>
  </div>
)}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `npx --prefix frontend vitest run src/components/extraction/ExtractionForm.test.tsx`

Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/extraction/ExtractionForm.tsx frontend/src/components/extraction/ExtractionForm.test.tsx
git commit -m "feat(extraction): add extraction_target and confidence_scores config options for llamaextract"
```

---

## Task 5: Update ExtractionResultViewer

**Files:**
- Modify: `frontend/src/components/extraction/ExtractionResultViewer.tsx`
- Create: `frontend/src/components/extraction/ExtractionResultViewer.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/extraction/ExtractionResultViewer.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ExtractionResultViewer } from './ExtractionResultViewer'
import type { ExtractionResult } from '@/types/extraction'

function buildResult(overrides: Partial<ExtractionResult> = {}): ExtractionResult {
  return {
    id: 'result-1',
    documentId: 'doc-1',
    extractionSchemaId: 'schema-1',
    schemaDefinitionSnapshot: {},
    extractionMethod: 'llamaextract',
    config: null,
    structuredData: { invoice_number: 'INV-001' },
    extractionMetadata: { latency_ms: 1234, file_id: 'f-abc' },
    citations: null,
    providerResponseRaw: null,
    sourceParseRunId: 'run-1',
    status: 'completed',
    statusMessage: null,
    startedAt: '2026-01-01T00:00:00Z',
    createdBy: 'user-1',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('ExtractionResultViewer', () => {
  it('shows extraction metadata collapsible when extractionMetadata is present', () => {
    render(<ExtractionResultViewer result={buildResult()} />)
    expect(screen.getByText('Extraction Metadata')).toBeInTheDocument()
  })

  it('shows provider response collapsible when providerResponseRaw is present', () => {
    render(
      <ExtractionResultViewer
        result={buildResult({ providerResponseRaw: { data: { invoice_number: 'INV-001' } } })}
      />
    )
    expect(screen.getByText('Provider Response')).toBeInTheDocument()
  })

  it('does not show provider response collapsible when providerResponseRaw is null', () => {
    render(<ExtractionResultViewer result={buildResult({ providerResponseRaw: null })} />)
    expect(screen.queryByText('Provider Response')).not.toBeInTheDocument()
  })

  it('does not show old metadata label', () => {
    render(<ExtractionResultViewer result={buildResult()} />)
    expect(screen.queryByText(/citations \/ reasoning/i)).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to see them fail**

Run: `npx --prefix frontend vitest run src/components/extraction/ExtractionResultViewer.test.tsx`

Expected: FAIL — old label "Metadata (Citations / Reasoning)" found, "Extraction Metadata" not found, no "Provider Response"

- [ ] **Step 3: Update ExtractionResultViewer**

In `frontend/src/components/extraction/ExtractionResultViewer.tsx`, replace the single metadata `<Collapsible>` block (currently lines 176–194, labeled "Metadata (Citations / Reasoning)") with two collapsible sections:

```tsx
{result.extractionMetadata && Object.keys(result.extractionMetadata).length > 0 && (
  <Collapsible>
    <CollapsibleTrigger asChild>
      <Button variant="outline" size="sm" className="w-full justify-between">
        <span>Extraction Metadata</span>
        <ChevronDown className="h-4 w-4" />
      </Button>
    </CollapsibleTrigger>
    <CollapsibleContent>
      <Card className="mt-2">
        <CardContent className="pt-4">
          <pre className="text-xs overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(result.extractionMetadata, null, 2)}
          </pre>
        </CardContent>
      </Card>
    </CollapsibleContent>
  </Collapsible>
)}

{result.providerResponseRaw && Object.keys(result.providerResponseRaw).length > 0 && (
  <Collapsible>
    <CollapsibleTrigger asChild>
      <Button variant="outline" size="sm" className="w-full justify-between">
        <span>Provider Response</span>
        <ChevronDown className="h-4 w-4" />
      </Button>
    </CollapsibleTrigger>
    <CollapsibleContent>
      <Card className="mt-2">
        <CardContent className="pt-4">
          <pre className="text-xs overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(result.providerResponseRaw, null, 2)}
          </pre>
        </CardContent>
      </Card>
    </CollapsibleContent>
  </Collapsible>
)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx --prefix frontend vitest run src/components/extraction/ExtractionResultViewer.test.tsx`

Expected: all 4 tests PASS

- [ ] **Step 5: Run full frontend test suite**

Run: `npx --prefix frontend vitest run`

Expected: all tests pass (no regressions)

- [ ] **Step 6: Build to verify TypeScript**

Run: `npm --prefix frontend run build 2>&1 | grep "error TS"`

Expected: no output

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/extraction/ExtractionResultViewer.tsx frontend/src/components/extraction/ExtractionResultViewer.test.tsx
git commit -m "feat(extraction): rename metadata collapsible; add provider response section to result viewer"
```

---

## Self-review

**Spec coverage:**
- ✅ `documentId` → `parseRunId` in request — Task 1 (type) + Task 2 (logic)
- ✅ `configured` flag for extractors — Task 1 (type) + Task 3 (UI)
- ✅ `citations`, `providerResponseRaw`, `sourceParseRunId` on result — Task 1 (type)
- ✅ `extraction_target`, `confidence_scores` LlamaExtract config options — Task 4
- ✅ `providerResponseRaw` displayed in viewer — Task 5

**Placeholder check:** No TBD, TODO, or "similar to" entries.

**Type consistency:**
- `RunExtractionRequest.parseRunId` defined in Task 1, used in Tasks 2, 3, 4
- `ExtractorInfo.configured` defined in Task 1, used in Task 3
- `ExtractionResult.providerResponseRaw` defined in Task 1, used in Task 5
- `ExtractionFormProps.parseRunId` — changed in Task 2, tested in Tasks 2, 3, 4
