# WS1: ClassificationConfig Component Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract classifier UI from `ClassificationRunForm` into a standalone, reusable `ClassificationConfig` component with a `defaultValues/onChange` interface; slim `ClassificationRunForm` down to a thin wrapper that adds a submit button.

**Architecture:** `ClassificationConfig` owns all internal UI state (labels, classifierType, promptConfig, batchSize, batchOverlap), initialises from `defaultValues` on mount, and fires `onChange` with a derived `ClassificationConfigValue` on every change. It has no submit button and no knowledge of API or routing. `ClassificationRunForm` becomes a 20-line wrapper that holds the latest `onChange` value and adds a submit button — preserving the existing caller interface so nothing else needs to change in this workstream.

**Tech Stack:** React 18, TypeScript, Vitest + @testing-library/react, shadcn/ui, Tailwind CSS

## Global Constraints

- All new files live under `frontend/src/`
- Component files: `PascalCase.tsx`; hook files: `camelCase.ts`; test files: `ComponentName.test.tsx` co-located with the component
- Run tests with: `npm --prefix frontend exec -- npx vitest run <path>`
- Run lint with: `npm --prefix frontend run lint`
- shadcn/ui + Tailwind only for UI — no new CSS files
- No backend changes in this workstream

---

### Task 1: ClassificationConfig component

**Files:**
- Create: `frontend/src/components/classification/ClassificationConfig.tsx`
- Create: `frontend/src/components/classification/ClassificationConfig.test.tsx`

**Interfaces:**
- Produces: `ClassificationConfigValue` (exported type), `ClassificationConfig` (exported component)
- `ClassificationConfigValue` shape:
  ```typescript
  { labels: string[]; classifierType: string; classifierConfig: Record<string, unknown> }
  ```
- `classifierConfig` for `"llm"` type:
  ```typescript
  { provider, model, batch_size, batch_overlap, llm_config: { system_prompt, temperature, max_tokens } }
  ```

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/classification/ClassificationConfig.test.tsx`:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ClassificationConfig } from './ClassificationConfig'

describe('ClassificationConfig', () => {
  it('renders the labels input and Add button', () => {
    render(<ClassificationConfig onChange={() => {}} />)
    expect(screen.getByPlaceholderText('e.g. balance_sheet')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add' })).toBeInTheDocument()
  })

  it('adds a label on Add button click and calls onChange', () => {
    const onChange = vi.fn()
    render(<ClassificationConfig onChange={onChange} />)
    fireEvent.change(screen.getByPlaceholderText('e.g. balance_sheet'), {
      target: { value: 'income_statement' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(screen.getByText('income_statement')).toBeInTheDocument()
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ labels: ['income_statement'] }),
    )
  })

  it('adds a label on Enter keydown', () => {
    const onChange = vi.fn()
    render(<ClassificationConfig onChange={onChange} />)
    const input = screen.getByPlaceholderText('e.g. balance_sheet')
    fireEvent.change(input, { target: { value: 'balance_sheet' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(screen.getByText('balance_sheet')).toBeInTheDocument()
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ labels: ['balance_sheet'] }),
    )
  })

  it('removes a label when its remove button is clicked', () => {
    const onChange = vi.fn()
    render(
      <ClassificationConfig
        defaultValues={{ labels: ['income_statement'] }}
        onChange={onChange}
      />,
    )
    expect(screen.getByText('income_statement')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Remove income_statement' }))
    expect(screen.queryByText('income_statement')).not.toBeInTheDocument()
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ labels: [] }))
  })

  it('does not add a duplicate label and does not call onChange', () => {
    const onChange = vi.fn()
    render(
      <ClassificationConfig
        defaultValues={{ labels: ['income_statement'] }}
        onChange={onChange}
      />,
    )
    fireEvent.change(screen.getByPlaceholderText('e.g. balance_sheet'), {
      target: { value: 'income_statement' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(onChange).not.toHaveBeenCalled()
  })

  it('seeds labels from defaultValues', () => {
    render(
      <ClassificationConfig
        defaultValues={{ labels: ['a', 'b'] }}
        onChange={() => {}}
      />,
    )
    expect(screen.getByText('a')).toBeInTheDocument()
    expect(screen.getByText('b')).toBeInTheDocument()
  })

  it('shows Batch settings trigger when classifierType is llm (default)', () => {
    render(<ClassificationConfig onChange={() => {}} />)
    expect(screen.getByText('Batch settings')).toBeInTheDocument()
  })

  it('calls onChange with correct llm classifierConfig shape', () => {
    const onChange = vi.fn()
    render(<ClassificationConfig onChange={onChange} />)
    fireEvent.change(screen.getByPlaceholderText('e.g. balance_sheet'), {
      target: { value: 'test_label' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        classifierType: 'llm',
        classifierConfig: expect.objectContaining({
          provider: expect.any(String),
          model: expect.any(String),
          batch_size: expect.any(Number),
          batch_overlap: expect.any(Number),
          llm_config: expect.objectContaining({
            temperature: expect.any(Number),
            max_tokens: expect.any(Number),
          }),
        }),
      }),
    )
  })
})
```

- [ ] **Step 2: Run the tests to confirm they fail**

```
npm --prefix frontend exec -- npx vitest run src/components/classification/ClassificationConfig.test.tsx
```

Expected: all tests fail with "Cannot find module './ClassificationConfig'".

- [ ] **Step 3: Create ClassificationConfig.tsx**

Create `frontend/src/components/classification/ClassificationConfig.tsx`:

```typescript
import { useState } from 'react'
import { X, ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { PromptConfigEditor } from '@/components/shared/PromptConfigEditor'
import type { PromptConfig } from '@/types/prompt-config'

const CLASSIFIER_TYPES = [
  { value: 'llm', label: 'LLM classifier' },
  { value: 'llamaindex_split', label: 'LlamaIndex split (not yet implemented)' },
]

const DEFAULT_PROMPT_CONFIG: PromptConfig = {
  provider: 'ollama_local',
  model: 'qwen2.5:7b',
  temperature: 0.0,
  maxTokens: 4096,
}

export interface ClassificationConfigValue {
  labels: string[]
  classifierType: string
  classifierConfig: Record<string, unknown>
}

interface Props {
  defaultValues?: Partial<ClassificationConfigValue>
  onChange: (value: ClassificationConfigValue) => void
}

function configToPromptConfig(config: Record<string, unknown>): PromptConfig {
  const llm = (config.llm_config as Record<string, unknown> | undefined) ?? {}
  return {
    provider: (config.provider as string | undefined) ?? DEFAULT_PROMPT_CONFIG.provider,
    model: (config.model as string | undefined) ?? DEFAULT_PROMPT_CONFIG.model,
    temperature: (llm.temperature as number | undefined) ?? DEFAULT_PROMPT_CONFIG.temperature,
    maxTokens: (llm.max_tokens as number | undefined) ?? DEFAULT_PROMPT_CONFIG.maxTokens,
    systemPrompt: llm.system_prompt as string | undefined,
  }
}

function buildClassifierConfig(
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

export function ClassificationConfig({ defaultValues, onChange }: Props) {
  const dv = defaultValues ?? {}
  const [labels, setLabels] = useState<string[]>(dv.labels ?? [])
  const [labelInput, setLabelInput] = useState('')
  const [classifierType, setClassifierType] = useState(dv.classifierType ?? 'llm')
  const [promptConfig, setPromptConfig] = useState<PromptConfig>(
    dv.classifierConfig && Object.keys(dv.classifierConfig).length > 0
      ? configToPromptConfig(dv.classifierConfig)
      : DEFAULT_PROMPT_CONFIG,
  )
  const [batchSize, setBatchSize] = useState(
    (dv.classifierConfig?.batch_size as number | undefined) ?? 10,
  )
  const [batchOverlap, setBatchOverlap] = useState(
    (dv.classifierConfig?.batch_overlap as number | undefined) ?? 3,
  )

  function emit(
    nextLabels: string[],
    nextType: string,
    nextPrompt: PromptConfig,
    nextBatch: number,
    nextOverlap: number,
  ) {
    onChange({
      labels: nextLabels,
      classifierType: nextType,
      classifierConfig: buildClassifierConfig(nextType, nextPrompt, nextBatch, nextOverlap),
    })
  }

  const addLabel = () => {
    const trimmed = labelInput.trim()
    if (!trimmed || labels.includes(trimmed)) return
    const next = [...labels, trimmed]
    setLabels(next)
    setLabelInput('')
    emit(next, classifierType, promptConfig, batchSize, batchOverlap)
  }

  const removeLabel = (l: string) => {
    const next = labels.filter((x) => x !== l)
    setLabels(next)
    emit(next, classifierType, promptConfig, batchSize, batchOverlap)
  }

  const handleClassifierTypeChange = (v: string) => {
    setClassifierType(v)
    emit(labels, v, promptConfig, batchSize, batchOverlap)
  }

  const handlePromptConfigChange = (v: PromptConfig) => {
    setPromptConfig(v)
    emit(labels, classifierType, v, batchSize, batchOverlap)
  }

  const handleBatchSizeChange = (v: number) => {
    setBatchSize(v)
    emit(labels, classifierType, promptConfig, v, batchOverlap)
  }

  const handleBatchOverlapChange = (v: number) => {
    setBatchOverlap(v)
    emit(labels, classifierType, promptConfig, batchSize, v)
  }

  return (
    <div className="space-y-6">
      {/* Labels */}
      <div className="space-y-2">
        <Label>Labels to classify</Label>
        <div className="flex gap-2">
          <Input
            placeholder="e.g. balance_sheet"
            value={labelInput}
            onChange={(e) => setLabelInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                addLabel()
              }
            }}
          />
          <Button type="button" variant="outline" onClick={addLabel}>
            Add
          </Button>
        </div>
        {labels.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-2">
            {labels.map((l) => (
              <Badge key={l} variant="secondary" className="flex items-center gap-1">
                {l}
                <button
                  aria-label={`Remove ${l}`}
                  onClick={() => removeLabel(l)}
                  className="ml-1 hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Classifier type */}
      <div className="space-y-2">
        <Label>Classifier</Label>
        <Select value={classifierType} onValueChange={handleClassifierTypeChange}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CLASSIFIER_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* LLM config */}
      {classifierType === 'llm' && (
        <>
          <PromptConfigEditor value={promptConfig} onChange={handlePromptConfigChange} />
          <Collapsible>
            <CollapsibleTrigger className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
              <ChevronDown className="h-4 w-4" />
              Batch settings
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-3 grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Batch size (pages)</Label>
                <Input
                  type="number"
                  min={1}
                  value={batchSize}
                  onChange={(e) => handleBatchSizeChange(Number(e.target.value))}
                />
              </div>
              <div className="space-y-2">
                <Label>Batch overlap (pages)</Label>
                <Input
                  type="number"
                  min={0}
                  value={batchOverlap}
                  onChange={(e) => handleBatchOverlapChange(Number(e.target.value))}
                />
              </div>
            </CollapsibleContent>
          </Collapsible>
        </>
      )}

      {/* LlamaIndex placeholder */}
      {classifierType === 'llamaindex_split' && (
        <p className="text-sm text-muted-foreground">
          LlamaIndex split classifier is not yet implemented. Select LLM classifier to proceed.
        </p>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run the tests to confirm they pass**

```
npm --prefix frontend exec -- npx vitest run src/components/classification/ClassificationConfig.test.tsx
```

Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```
git add frontend/src/components/classification/ClassificationConfig.tsx frontend/src/components/classification/ClassificationConfig.test.tsx
git commit -m "feat(classify): add ClassificationConfig composable component"
```

---

### Task 2: Slim ClassificationRunForm to a thin wrapper

**Files:**
- Modify: `frontend/src/components/classification/ClassificationRunForm.tsx`

**Interfaces:**
- Consumes: `ClassificationConfig`, `ClassificationConfigValue` from `./ClassificationConfig`
- Produces: `ClassificationRunFormValues` (re-exported alias), `ClassificationRunForm` (unchanged public interface — existing callers in `NewClassificationRunPage` still work)

- [ ] **Step 1: Replace ClassificationRunForm.tsx**

Replace the entire contents of `frontend/src/components/classification/ClassificationRunForm.tsx` with:

```typescript
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { ClassificationConfig } from './ClassificationConfig'
import type { ClassificationConfigValue } from './ClassificationConfig'

// Re-export so existing imports of ClassificationRunFormValues continue to work
export type { ClassificationConfigValue as ClassificationRunFormValues }

interface Props {
  defaultValues?: Partial<ClassificationConfigValue>
  onSubmit: (values: ClassificationConfigValue) => void
  isSubmitting?: boolean
  submitLabel?: string
}

export function ClassificationRunForm({
  defaultValues,
  onSubmit,
  isSubmitting,
  submitLabel = 'Start classification',
}: Props) {
  const [config, setConfig] = useState<ClassificationConfigValue>({
    labels: defaultValues?.labels ?? [],
    classifierType: defaultValues?.classifierType ?? 'llm',
    classifierConfig: defaultValues?.classifierConfig ?? {},
  })

  return (
    <div className="space-y-6">
      <ClassificationConfig defaultValues={defaultValues} onChange={setConfig} />
      <Button
        onClick={() => onSubmit(config)}
        disabled={
          config.labels.length === 0 ||
          isSubmitting ||
          config.classifierType === 'llamaindex_split'
        }
      >
        {isSubmitting ? 'Starting…' : submitLabel}
      </Button>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```
npm --prefix frontend run build 2>&1 | head -40
```

Expected: no TypeScript errors related to `ClassificationRunForm` or `ClassificationConfig`.

- [ ] **Step 3: Run lint**

```
npm --prefix frontend run lint
```

Expected: no lint errors in the modified files.

- [ ] **Step 4: Commit**

```
git add frontend/src/components/classification/ClassificationRunForm.tsx
git commit -m "refactor(classify): slim ClassificationRunForm to wrapper over ClassificationConfig"
```

---

## Manual Verification (Human + Browser)

Start the dev server if it is not already running:
```
npm --prefix frontend run dev
```

Open `http://localhost:5173` in a browser and navigate to **Classify → New classification run**.

Step through the wizard to step 3 (Configure labels and model).

**Label management:**
1. Type `income_statement` in the label input, press **Enter** → badge `income_statement` appears below the input, input clears.
2. Type `balance_sheet`, click **Add** → badge `balance_sheet` appears.
3. Click the **×** on the `income_statement` badge → badge disappears.
4. Type `balance_sheet` again, click **Add** → no second `balance_sheet` badge (duplicate blocked).
5. Confirm the **Start classification** button is enabled (at least one label present).

**Classifier type:**
6. Open the **Classifier** dropdown, select **LlamaIndex split** → "not yet implemented" text appears, LLM config section disappears, Start button is disabled.
7. Switch back to **LLM classifier** → LLM config section reappears, Start button re-enables (if a label exists).

**Batch settings:**
8. Click **Batch settings** → collapsible expands showing Batch size and Batch overlap inputs.

**End-to-end:**
9. With at least one label and LLM classifier selected, click **Start classification** → request fires and navigation proceeds to the run detail page. (Requires a running backend with a selected document and parse run.)
