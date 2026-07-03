# Extraction Page Rework + Inline Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the classification filter a standalone, method-agnostic extraction parameter; add inline classification configuration that auto-runs on submit; restructure the New Extraction Run page (card + collapsibles).

**Architecture:** Frontend-only (backend already supports resolver + category_filter + classification create/poll). A filter *intent* is composed on the page and passed to `useExtractionSubmit`, which orchestrates parse → (classify + poll) → extract, then attaches one `category_filter` preprocess stage regardless of method.

**Tech Stack:** React 18, TypeScript, Vite, vitest, shadcn/ui.

## Global Constraints

- Frontend: one hook per feature, feature-scoped components, shadcn/ui + Tailwind.
- The `category_filter` stage config the backend expects: `{ classificationRunId, categories, granularity }`.
- Classification create request: `createClassificationRun(documentId, { parseRunId, labels, classifierType, classifierConfig })`; poll `getClassificationRun(id)` until `status === 'completed'` (or `'failed'` → abort).
- TDD: failing test first, then implement, then commit.
- Frontend test: `cd frontend && npx vitest run <path>`; lint: `npm run lint`; build: `npm run build`.

---

### Task 1: Shared `buildClassifierConfig` helper

**Files:**
- Create: `frontend/src/lib/classifierConfig.ts`
- Create test: `frontend/src/lib/classifierConfig.test.ts`
- Modify: `frontend/src/pages/NewClassificationRunPage.tsx` (use the helper)

**Interfaces:**
- Produces: `buildClassifierConfig(classifierType: string, promptConfig: PromptConfig, batchSize: number, batchOverlap: number): Record<string, unknown>` — returns the LLM classifier config object, or `{}` for non-llm.

- [ ] **Step 1: Failing test** — `frontend/src/lib/classifierConfig.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { buildClassifierConfig } from './classifierConfig'

const prompt = { provider: 'openai', model: 'gpt', temperature: 0.2, maxTokens: 100, systemPrompt: 'sp' }

describe('buildClassifierConfig', () => {
  it('builds llm config from prompt + batch settings', () => {
    expect(buildClassifierConfig('llm', prompt as never, 10, 3)).toEqual({
      provider: 'openai', model: 'gpt', batch_size: 10, batch_overlap: 3,
      llm_config: { system_prompt: 'sp', temperature: 0.2, max_tokens: 100 },
    })
  })

  it('returns empty object for non-llm classifier', () => {
    expect(buildClassifierConfig('llamaindex_split', prompt as never, 10, 3)).toEqual({})
  })
})
```

- [ ] **Step 2: Run — expect fail**: `npx vitest run src/lib/classifierConfig.test.ts` → module missing.

- [ ] **Step 3: Implement** — `frontend/src/lib/classifierConfig.ts`:

```ts
import type { PromptConfig } from '@/types/prompt-config'

export function buildClassifierConfig(
  classifierType: string,
  promptConfig: PromptConfig,
  batchSize: number,
  batchOverlap: number,
): Record<string, unknown> {
  if (classifierType !== 'llm') return {}
  return {
    provider: promptConfig.provider,
    model: promptConfig.model,
    batch_size: batchSize,
    batch_overlap: batchOverlap,
    llm_config: {
      system_prompt: promptConfig.systemPrompt ?? null,
      temperature: promptConfig.temperature ?? 0.0,
      max_tokens: promptConfig.maxTokens ?? 4096,
    },
  }
}
```

- [ ] **Step 4: Refactor `NewClassificationRunPage.handleSubmit`** to use it — replace the inline `classifierConfig` object (lines ~115-128) with:

```tsx
const classifierConfig = buildClassifierConfig(
  classifyConfig.classifierType, promptConfig, batchSize, batchOverlap,
)
```

Add import: `import { buildClassifierConfig } from '@/lib/classifierConfig'`.

- [ ] **Step 5: Run — expect pass**: `npx vitest run src/lib/classifierConfig.test.ts` and `npm run lint`.

- [ ] **Step 6: Commit**:

```bash
git add frontend/src/lib/classifierConfig.ts frontend/src/lib/classifierConfig.test.ts frontend/src/pages/NewClassificationRunPage.tsx
git commit -m "refactor(classification): extract buildClassifierConfig helper"
```

---

### Task 2: Filter intent types + `buildFilterIntent` helper

**Files:**
- Create: `frontend/src/lib/classificationFilter.ts`
- Create test: `frontend/src/lib/classificationFilter.test.ts`

**Interfaces:**
- Produces:
  ```ts
  export type Granularity = 'page' | 'block'
  export type ClassificationFilterIntent =
    | { mode: 'none' }
    | { mode: 'select'; classificationRunId: string; categories: string[]; granularity: Granularity }
    | { mode: 'configure'; classify: { labels: string[]; classifierType: string; classifierConfig: Record<string, unknown> }; categories: string[]; granularity: Granularity }
  export interface FilterInputs {
    eligibleRunId: string | null       // completed, parse-matched run (select mode) or null
    selectedCategories: string[]
    granularity: Granularity
    classify: { labels: string[]; classifierType: string; classifierConfig: Record<string, unknown> } | null // configure-mode config, or null
  }
  export function buildFilterIntent(inputs: FilterInputs): ClassificationFilterIntent
  ```
- Rules: if `eligibleRunId` set and `selectedCategories` non-empty → `select`. Else if `classify` set with `labels` non-empty and `selectedCategories` non-empty → `configure` (categories = selectedCategories). Else → `none`.

- [ ] **Step 1: Failing test** — `frontend/src/lib/classificationFilter.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { buildFilterIntent } from './classificationFilter'

const base = { eligibleRunId: null, selectedCategories: [], granularity: 'page' as const, classify: null }

describe('buildFilterIntent', () => {
  it('select mode when an eligible run and categories are chosen', () => {
    expect(buildFilterIntent({ ...base, eligibleRunId: 'r1', selectedCategories: ['fin'] })).toEqual({
      mode: 'select', classificationRunId: 'r1', categories: ['fin'], granularity: 'page',
    })
  })

  it('configure mode when no run but classify labels + filter categories set', () => {
    const classify = { labels: ['fin', 'legal'], classifierType: 'llm', classifierConfig: { a: 1 } }
    expect(buildFilterIntent({ ...base, classify, selectedCategories: ['fin'] })).toEqual({
      mode: 'configure', classify, categories: ['fin'], granularity: 'page',
    })
  })

  it('none when nothing selected', () => {
    expect(buildFilterIntent(base)).toEqual({ mode: 'none' })
    expect(buildFilterIntent({ ...base, eligibleRunId: 'r1' })).toEqual({ mode: 'none' })
    expect(buildFilterIntent({ ...base, classify: { labels: [], classifierType: 'llm', classifierConfig: {} } }))
      .toEqual({ mode: 'none' })
  })
})
```

- [ ] **Step 2: Run — expect fail**: `npx vitest run src/lib/classificationFilter.test.ts`.

- [ ] **Step 3: Implement** — `frontend/src/lib/classificationFilter.ts`:

```ts
export type Granularity = 'page' | 'block'

export type ClassificationFilterIntent =
  | { mode: 'none' }
  | { mode: 'select'; classificationRunId: string; categories: string[]; granularity: Granularity }
  | {
      mode: 'configure'
      classify: { labels: string[]; classifierType: string; classifierConfig: Record<string, unknown> }
      categories: string[]
      granularity: Granularity
    }

export interface FilterInputs {
  eligibleRunId: string | null
  selectedCategories: string[]
  granularity: Granularity
  classify: { labels: string[]; classifierType: string; classifierConfig: Record<string, unknown> } | null
}

export function buildFilterIntent(inputs: FilterInputs): ClassificationFilterIntent {
  const { eligibleRunId, selectedCategories, granularity, classify } = inputs
  if (selectedCategories.length === 0) return { mode: 'none' }
  if (eligibleRunId) {
    return { mode: 'select', classificationRunId: eligibleRunId, categories: selectedCategories, granularity }
  }
  if (classify && classify.labels.length > 0) {
    return { mode: 'configure', classify, categories: selectedCategories, granularity }
  }
  return { mode: 'none' }
}
```

- [ ] **Step 4: Run — expect pass**; **Step 5: Commit**:

```bash
git add frontend/src/lib/classificationFilter.ts frontend/src/lib/classificationFilter.test.ts
git commit -m "feat(extraction): add classification filter intent model"
```

---

### Task 3: Rework the filter hook → `useClassificationFilter`

**Files:**
- Rename/replace: `frontend/src/hooks/useCategoryFilter.ts` → `frontend/src/hooks/useClassificationFilter.ts`
- Rename/replace test: `frontend/src/hooks/useCategoryFilter.test.ts` → `frontend/src/hooks/useClassificationFilter.test.ts`

**Interfaces:**
- Produces:
  ```ts
  interface ClassificationFilterState {
    mode: 'select' | 'configure'
    eligibleRun: ClassificationRun | null
    selectCategories: string[]            // labelsRequested of eligibleRun (select mode)
    selectedCategories: string[]
    granularity: Granularity
    setSelectedCategories: (c: string[]) => void
    setGranularity: (g: Granularity) => void
  }
  function useClassificationFilter(runs: ClassificationRun[], parseRunId: string | null): ClassificationFilterState
  ```
- `mode` is `'select'` when an eligible run exists (completed + `parseRunId` match), else `'configure'`. `selectCategories` from `eligibleRun.labelsRequested`.

- [ ] **Step 1: Failing test** — `frontend/src/hooks/useClassificationFilter.test.ts`:

```ts
import { renderHook, act } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useClassificationFilter } from './useClassificationFilter'
import type { ClassificationRun } from '@/types/classification'

function run(overrides: Partial<ClassificationRun>): ClassificationRun {
  return {
    id: 'r1', parseRunId: 'p1', documentId: 'd1', labelsRequested: ['fin', 'legal'],
    classifierType: 'llm', classifierConfig: {}, status: 'completed',
    error: null, inputTokens: 0, outputTokens: 0, durationMs: 0,
    createdAt: '', regions: [], ...overrides,
  } as ClassificationRun
}

describe('useClassificationFilter', () => {
  it('select mode with categories from labelsRequested when eligible run exists', () => {
    const { result } = renderHook(() => useClassificationFilter([run({})], 'p1'))
    expect(result.current.mode).toBe('select')
    expect(result.current.selectCategories).toEqual(['fin', 'legal'])
  })

  it('configure mode when no eligible run for the parse', () => {
    const { result } = renderHook(() => useClassificationFilter([run({ parseRunId: 'pX' })], 'p1'))
    expect(result.current.mode).toBe('configure')
    expect(result.current.eligibleRun).toBeNull()
  })

  it('tracks selected categories and granularity', () => {
    const { result } = renderHook(() => useClassificationFilter([run({})], 'p1'))
    act(() => result.current.setSelectedCategories(['fin']))
    act(() => result.current.setGranularity('block'))
    expect(result.current.selectedCategories).toEqual(['fin'])
    expect(result.current.granularity).toBe('block')
  })
})
```

- [ ] **Step 2: Run — expect fail**.

- [ ] **Step 3: Implement** — `frontend/src/hooks/useClassificationFilter.ts`:

```ts
import { useMemo, useState } from 'react'
import type { ClassificationRun } from '@/types/classification'
import type { Granularity } from '@/lib/classificationFilter'

export interface ClassificationFilterState {
  mode: 'select' | 'configure'
  eligibleRun: ClassificationRun | null
  selectCategories: string[]
  selectedCategories: string[]
  granularity: Granularity
  setSelectedCategories: (c: string[]) => void
  setGranularity: (g: Granularity) => void
}

export function useClassificationFilter(
  runs: ClassificationRun[],
  parseRunId: string | null,
): ClassificationFilterState {
  const [selectedCategories, setSelectedCategories] = useState<string[]>([])
  const [granularity, setGranularity] = useState<Granularity>('page')

  const eligibleRun = useMemo<ClassificationRun | null>(() => {
    if (!parseRunId) return null
    return runs.find((r) => r.status === 'completed' && r.parseRunId === parseRunId) ?? null
  }, [runs, parseRunId])

  const selectCategories = useMemo<string[]>(
    () => (eligibleRun ? Array.from(new Set(eligibleRun.labelsRequested)) : []),
    [eligibleRun],
  )

  return {
    mode: eligibleRun ? 'select' : 'configure',
    eligibleRun,
    selectCategories,
    selectedCategories,
    granularity,
    setSelectedCategories,
    setGranularity,
  }
}
```

- [ ] **Step 4: Delete old files** `useCategoryFilter.ts` / `useCategoryFilter.test.ts`.

- [ ] **Step 5: Run — expect pass**; **Step 6: Commit**:

```bash
git rm frontend/src/hooks/useCategoryFilter.ts frontend/src/hooks/useCategoryFilter.test.ts
git add frontend/src/hooks/useClassificationFilter.ts frontend/src/hooks/useClassificationFilter.test.ts
git commit -m "feat(extraction): rework filter hook into useClassificationFilter (select/configure modes)"
```

---

### Task 4: Dual-mode `ClassificationFilterSection` component

**Files:**
- Replace: `frontend/src/components/extraction/CategoryFilterSection.tsx` → `ClassificationFilterSection.tsx`
- Replace test: `CategoryFilterSection.test.tsx` → `ClassificationFilterSection.test.tsx`

**Interfaces:**
- Consumes: `ClassificationFilterState` (Task 3); `ClassificationConfig` (`@/components/classification/ClassificationConfig`), `PromptConfigEditor`.
- Props:
  ```ts
  interface Props {
    state: ClassificationFilterState
    // configure-mode inputs (owned by the page, mirrors NewClassificationRunPage):
    classifyConfig: ClassificationConfigValue
    onClassifyConfigChange: (v: ClassificationConfigValue) => void
    promptConfig: PromptConfig
    onPromptConfigChange: (v: PromptConfig) => void
  }
  ```
- **Select mode:** checkbox per `state.selectCategories`, toggling `state.selectedCategories`; granularity `<select>`.
- **Configure mode:** `ClassificationConfig` + `PromptConfigEditor`; a "Filter extraction to" checkbox group over `classifyConfig.labels` (the subset to filter by → `state.selectedCategories`); granularity `<select>`.

- [ ] **Step 1: Failing test** — `frontend/src/components/extraction/ClassificationFilterSection.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ClassificationFilterSection } from './ClassificationFilterSection'
import type { ClassificationFilterState } from '@/hooks/useClassificationFilter'

function baseState(o: Partial<ClassificationFilterState>): ClassificationFilterState {
  return {
    mode: 'select', eligibleRun: { id: 'r1' } as never, selectCategories: ['fin', 'legal'],
    selectedCategories: [], granularity: 'page',
    setSelectedCategories: vi.fn(), setGranularity: vi.fn(), ...o,
  }
}

const cfgProps = {
  classifyConfig: { labels: ['a', 'b'], classifierType: 'llm' },
  onClassifyConfigChange: vi.fn(),
  promptConfig: { provider: 'openai', model: 'gpt', temperature: 0, maxTokens: 10 } as never,
  onPromptConfigChange: vi.fn(),
}

describe('ClassificationFilterSection', () => {
  it('select mode: renders a checkbox per eligible category', () => {
    render(<ClassificationFilterSection state={baseState({})} {...cfgProps} />)
    expect(screen.getByLabelText('fin')).toBeInTheDocument()
    expect(screen.getByLabelText('legal')).toBeInTheDocument()
  })

  it('select mode: toggles category', () => {
    const setSel = vi.fn()
    render(<ClassificationFilterSection state={baseState({ setSelectedCategories: setSel })} {...cfgProps} />)
    fireEvent.click(screen.getByLabelText('fin'))
    expect(setSel).toHaveBeenCalledWith(['fin'])
  })

  it('configure mode: renders label editor and filter-subset over classify labels', () => {
    render(<ClassificationFilterSection
      state={baseState({ mode: 'configure', eligibleRun: null, selectCategories: [] })} {...cfgProps} />)
    expect(screen.getByText(/Labels to classify/i)).toBeInTheDocument()
    expect(screen.getByLabelText('a')).toBeInTheDocument()   // filter-subset over classify labels
    expect(screen.getByLabelText('b')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run — expect fail**.

- [ ] **Step 3: Implement** — `frontend/src/components/extraction/ClassificationFilterSection.tsx`:

```tsx
import type { ClassificationFilterState } from '@/hooks/useClassificationFilter'
import { ClassificationConfig } from '@/components/classification/ClassificationConfig'
import type { ClassificationConfigValue } from '@/components/classification/ClassificationConfig'
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'
import type { PromptConfig } from '@/types/prompt-config'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'

interface Props {
  state: ClassificationFilterState
  classifyConfig: ClassificationConfigValue
  onClassifyConfigChange: (v: ClassificationConfigValue) => void
  promptConfig: PromptConfig
  onPromptConfigChange: (v: PromptConfig) => void
}

function CategoryChecklist({
  categories, selected, onToggle,
}: { categories: string[]; selected: string[]; onToggle: (c: string) => void }) {
  return (
    <div className="space-y-2">
      {categories.map((cat) => (
        <div key={cat} className="flex items-center gap-2">
          <Checkbox id={`cat-${cat}`} checked={selected.includes(cat)} onCheckedChange={() => onToggle(cat)} />
          <Label htmlFor={`cat-${cat}`}>{cat}</Label>
        </div>
      ))}
    </div>
  )
}

export function ClassificationFilterSection({
  state, classifyConfig, onClassifyConfigChange, promptConfig, onPromptConfigChange,
}: Props) {
  const { mode, selectCategories, selectedCategories, granularity, setSelectedCategories, setGranularity } = state

  const toggle = (cat: string) =>
    setSelectedCategories(
      selectedCategories.includes(cat)
        ? selectedCategories.filter((c) => c !== cat)
        : [...selectedCategories, cat],
    )

  const granularitySelect = (
    <div className="flex items-center gap-2">
      <Label htmlFor="granularity">Granularity</Label>
      <select id="granularity" className="rounded border px-2 py-1 text-sm"
        value={granularity} onChange={(e) => setGranularity(e.target.value as 'page' | 'block')}>
        <option value="page">Page</option>
        <option value="block">Block</option>
      </select>
    </div>
  )

  if (mode === 'select') {
    return (
      <div className="space-y-3">
        <p className="text-xs text-muted-foreground">Filter extraction to these classified categories:</p>
        <CategoryChecklist categories={selectCategories} selected={selectedCategories} onToggle={toggle} />
        {granularitySelect}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        No classification exists for this parse. Configure one — it runs before extraction.
      </p>
      <ClassificationConfig defaultValues={classifyConfig} onChange={onClassifyConfigChange} />
      {classifyConfig.classifierType === 'llm' && (
        <PromptConfigEditor value={promptConfig} onChange={onPromptConfigChange} />
      )}
      {classifyConfig.labels.length > 0 && (
        <div className="space-y-2">
          <Label className="text-xs">Filter extraction to</Label>
          <CategoryChecklist categories={classifyConfig.labels} selected={selectedCategories} onToggle={toggle} />
        </div>
      )}
      {granularitySelect}
    </div>
  )
}
```

- [ ] **Step 4: Delete old component files** `CategoryFilterSection.tsx` / `.test.tsx`.

- [ ] **Step 5: Run — expect pass**; **Step 6: Commit**:

```bash
git rm frontend/src/components/extraction/CategoryFilterSection.tsx frontend/src/components/extraction/CategoryFilterSection.test.tsx
git add frontend/src/components/extraction/ClassificationFilterSection.tsx frontend/src/components/extraction/ClassificationFilterSection.test.tsx
git commit -m "feat(extraction): dual-mode ClassificationFilterSection (select/configure)"
```

---

### Task 5: Auto-chain orchestration in `useExtractionSubmit`

**Files:**
- Modify: `frontend/src/hooks/useExtractionSubmit.ts`
- Modify test: `frontend/src/hooks/useExtractionSubmit.test.ts`

**Interfaces:**
- `submit(documentId, existingParseRuns, request, intent: ClassificationFilterIntent)` — new 4th arg.
- `SubmitPhase` gains `'classifying'`.
- After parse resolves: if `intent.mode === 'configure'` → `createClassificationRun` + poll `getClassificationRun` until `completed` (fail → phase `failed`, return null); build stage `{ stage: 'category_filter', config: { classificationRunId, categories, granularity } }`. If `mode === 'select'` → build stage from `intent.classificationRunId`. Attach stage to `preprocess` (append) for any method.

- [ ] **Step 1: Failing test** — add to `frontend/src/hooks/useExtractionSubmit.test.ts` (follow the file's existing mock setup for `@/api/extraction` and `@/api/parseRuns`; add `@/api/classification` mock):

```ts
// Mock classification API alongside existing mocks
vi.mock('@/api/classification', () => ({
  createClassificationRun: vi.fn(),
  getClassificationRun: vi.fn(),
}))
```

```ts
it('auto-chains: configure-mode classification runs and its id is used to filter', async () => {
  // existing parse run p1 succeeded so parse phase is skipped (reuse the file's helper/fixture)
  const clsApi = await import('@/api/classification')
  vi.mocked(clsApi.createClassificationRun).mockResolvedValue({ id: 'cls1', status: 'pending' } as never)
  vi.mocked(clsApi.getClassificationRun).mockResolvedValue({ id: 'cls1', status: 'completed' } as never)
  const extApi = await import('@/api/extraction')
  vi.mocked(extApi.runExtraction).mockResolvedValue({ id: 'ext1' } as never)

  const { result } = renderHook(() => useExtractionSubmit())
  await act(async () => {
    await result.current.submit('doc1', [/* parse run matching request, status succeeded */], /* request */, {
      mode: 'configure',
      classify: { labels: ['fin'], classifierType: 'llm', classifierConfig: {} },
      categories: ['fin'], granularity: 'page',
    })
  })

  expect(clsApi.createClassificationRun).toHaveBeenCalled()
  const runArg = vi.mocked(extApi.runExtraction).mock.calls[0][0]
  expect(runArg.preprocess).toContainEqual({
    stage: 'category_filter',
    config: { classificationRunId: 'cls1', categories: ['fin'], granularity: 'page' },
  })
})
```

> Implementer note: the existing test file already builds a `RunWithParseRequest` and parse-run fixtures; reuse them so the parse phase is skipped (matching run present). Poll interval: the hook uses `POLLING_INTERVAL`; keep the classification poll on the same constant and resolve the mock to `completed` on first poll so no fake timers are needed.

- [ ] **Step 2: Run — expect fail**.

- [ ] **Step 3: Implement.** In `useExtractionSubmit.ts`:

Add imports:
```ts
import { createClassificationRun, getClassificationRun } from '@/api/classification'
import type { ClassificationFilterIntent } from '@/lib/classificationFilter'
import type { PreprocessStage } from '@/types/extraction'
```

Extend phase type: `export type SubmitPhase = 'idle' | 'parsing' | 'classifying' | 'extracting' | 'failed'`.

Add the 4th param to `submit` and its type. After `parseRunId` is resolved (just before `setPhase('extracting')`), insert:

```ts
      let categoryStage: PreprocessStage | null = null
      if (intent.mode === 'select') {
        categoryStage = {
          stage: 'category_filter',
          config: { classificationRunId: intent.classificationRunId, categories: intent.categories, granularity: intent.granularity },
        }
      } else if (intent.mode === 'configure') {
        setPhase('classifying')
        let runId: string
        try {
          const created = await createClassificationRun(documentId, {
            parseRunId: parseRunId!,
            labels: intent.classify.labels,
            classifierType: intent.classify.classifierType,
            classifierConfig: intent.classify.classifierConfig,
          })
          runId = created.id
        } catch {
          setPhase('failed'); setPhaseError('Failed to start classification'); return null
        }
        const clsStarted = Date.now()
        for (;;) {
          if (cancelledRef.current) return null
          if (Date.now() - clsStarted > PARSE_TIMEOUT_MS) {
            setPhase('failed'); setPhaseError('Classification timed out'); return null
          }
          const run = await getClassificationRun(runId)
          if (run.status === 'completed') break
          if (run.status === 'failed') {
            setPhase('failed'); setPhaseError(run.error ?? 'Classification failed'); return null
          }
          await sleep(POLLING_INTERVAL)
        }
        categoryStage = {
          stage: 'category_filter',
          config: { classificationRunId: runId, categories: intent.categories, granularity: intent.granularity },
        }
      }
```

Then when calling `runExtraction`, merge the stage into preprocess:
```ts
        const preprocess = [
          ...(extractionConfig.preprocess ?? []),
          ...(categoryStage ? [categoryStage] : []),
        ]
        const result = await extractionApi.runExtraction({
          parseRunId: parseRunId!,
          extractionSchemaId: extractionConfig.extractionSchemaId,
          extractionMethod: extractionConfig.extractionMethod,
          config: extractionConfig.config,
          llmConfig: extractionConfig.llmConfig,
          userPromptTemplate: extractionConfig.userPromptTemplate,
          chunking: extractionConfig.chunking,
          preprocess: preprocess.length ? preprocess : undefined,
          timeoutMinutes: extractionConfig.timeoutMinutes,
        })
```

- [ ] **Step 4: Run — expect pass**; **Step 5: Commit**:

```bash
git add frontend/src/hooks/useExtractionSubmit.ts frontend/src/hooks/useExtractionSubmit.test.ts
git commit -m "feat(extraction): auto-chain classification before extraction in submit"
```

---

### Task 6: Restructure New Extraction Run page (card + collapsibles) + wire intent

**Files:**
- Modify: `frontend/src/pages/NewExtractionRunPage.tsx`

**Interfaces:**
- Consumes: `useClassificationFilter`, `ClassificationFilterSection`, `buildFilterIntent`, `buildClassifierConfig`, `useDocumentClassificationRuns`.

- [ ] **Step 1: Remove old wiring.** Delete the old `useCategoryFilter` import/usage and the `CategoryFilterSection` render + the `preprocess: [categoryStage]` addition inside the llm branch (Tasks 3/4/5 supersede them).

- [ ] **Step 2: Add classification state + hook.** Near the other hooks:

```tsx
const { runs: classificationRuns } = useDocumentClassificationRuns(documentId)
const matchedParseRunId = useMemo(
  () => parseRuns.find(
    (r) => r.parser === parserType && r.representationKind === REPRESENTATION_KIND
      && (r.status === 'succeeded' || r.status === 'partial'),
  )?.id ?? null,
  [parseRuns, parserType],
)
const filter = useClassificationFilter(classificationRuns, matchedParseRunId)
const [classifyConfig, setClassifyConfig] = useState<ClassificationConfigValue>({ labels: [], classifierType: 'llm' })
const [classifyPrompt, setClassifyPrompt] = useState<PromptConfig>({
  provider: 'ollama_local', model: 'qwen2.5:7b', temperature: 0.0, maxTokens: 4096,
})
```

- [ ] **Step 3: Build the intent in the submit handler** (replace per-method preprocess wiring). Just before calling `submit(...)`:

```tsx
const intent = buildFilterIntent({
  eligibleRunId: filter.eligibleRun?.id ?? null,
  selectedCategories: filter.selectedCategories,
  granularity: filter.granularity,
  classify: filter.mode === 'configure' && classifyConfig.labels.length > 0
    ? {
        labels: classifyConfig.labels,
        classifierType: classifyConfig.classifierType,
        classifierConfig: buildClassifierConfig(classifyConfig.classifierType, classifyPrompt, 10, 3),
      }
    : null,
})
const resultId = await submit(documentId, parseRuns, { parseConfig, extractionConfig }, intent)
```

- [ ] **Step 4: Restructure JSX.** Wrap the extraction config controls in a `<Card><CardHeader><CardTitle>Extraction</CardTitle></CardHeader><CardContent>…</CardContent></Card>`. Move the Parse config (`ParseMethodSelector`) into a `<Collapsible>` whose `open` defaults to `!matchedParseRunId` (auto-open + required when no viable run). Add a second `<Collapsible>` "Filter by classification (optional)" rendering:

```tsx
<ClassificationFilterSection
  state={filter}
  classifyConfig={classifyConfig}
  onClassifyConfigChange={setClassifyConfig}
  promptConfig={classifyPrompt}
  onPromptConfigChange={setClassifyPrompt}
/>
```

Keep the existing method-specific and chunking controls inside the Extraction card. Preserve all existing state and the run button.

- [ ] **Step 5: Verify** — `npm run lint && npx vitest run && npm run build`. Expected: lint clean, all tests pass, build succeeds.

- [ ] **Step 6: Commit**:

```bash
git add frontend/src/pages/NewExtractionRunPage.tsx
git commit -m "feat(extraction): restructure run page into card + parse/classification collapsibles"
```

---

## Self-Review

- **Point 1 (standalone, method-agnostic):** Task 5 attaches the stage in submit regardless of method; Task 6 removes it from the llm block. ✓
- **Point 2 (configure when none found):** Tasks 3 (mode), 4 (configure UI), 5 (auto-chain). ✓
- **Point 3 (UI orchestrated):** Task 5 orchestrates in the hook. ✓
- **Point 4 (card + collapsibles, parse required only when no viable run):** Task 6. ✓
- **Filter by subset of classified labels:** Task 4 configure-mode filter-subset over `classifyConfig.labels`; Task 2 carries `categories` subset. ✓
- **Placeholder scan:** all steps carry concrete code. Two implementer notes point at existing fixtures to reuse (submit test setup).
- **Type consistency:** `ClassificationFilterIntent` (Task 2) consumed by Task 5; `ClassificationFilterState` (Task 3) consumed by Tasks 4 & 6; `buildClassifierConfig` (Task 1) used in Task 6.
