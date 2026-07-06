# Parser Eval Variant Config Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the New Run dialog compare `(adapter, config)` variants — a variant list where the same adapter can appear multiple times with different configs — by reusing `ParseMethodSelector`.

**Architecture:** Frontend-only. Replace `NewRunDialog`'s adapter checkboxes with a variant-row list; each row is a reused `ParseMethodSelector` (adapter dropdown + per-adapter config editor). A recursive `stableStringify` helper backs a client-side duplicate-variant guard so identical `(adapter, config)` rows can't reach the backend. No backend change — the engine and `variant_key` already handle it.

**Tech Stack:** React 18 + TypeScript + Vite, shadcn/ui, Vitest + React Testing Library.

## Global Constraints

- **Frontend-only.** Backend accepts arbitrary `config`, derives `variant_key` from `(adapter, config)`, enforces `unique(run, eval_case, variant_key)`, validates only the adapter name.
- Reuse `ParseMethodSelector` (`components/documents/ParseMethodSelector.tsx`, exported) — props `{ parserType, config, onParserTypeChange, onConfigChange, disabled?, compact? }`; it resets a row's config to the adapter's `defaultConfig` on adapter change.
- `ParseConfig` type from `@/types/parsing`. `PARSER_REGISTRY` from `ParseMethodSelector`.
- Commands: `cd frontend && npx vitest run <path>`, `npx tsc --noEmit`, `npm run lint`, `npm run build`.
- Branch `feat/parser-eval-variant-config`. Commit after each green task. Trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- Spec: `docs/superpowers/specs/2026-07-06-parser-eval-variant-config-editor-design.md`.

## File Structure

| File | Responsibility |
|---|---|
| `frontend/src/lib/stableStringify.ts` (create) | recursive, key-sorted stringify for equality keys |
| `frontend/src/lib/stableStringify.test.ts` (create) | its unit tests |
| `frontend/src/components/parser-eval/NewRunDialog.tsx` (modify) | variant list + config editors + dup guard |
| `frontend/src/components/parser-eval/NewRunDialog.test.tsx` (modify) | new interaction coverage |

---

### Task 1: `stableStringify` helper

**Files:**
- Create: `frontend/src/lib/stableStringify.ts`
- Test: `frontend/src/lib/stableStringify.test.ts`

**Interfaces:**
- Produces: `stableStringify(value: unknown): string` — deterministic; object keys sorted at every nesting level; array order preserved.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/stableStringify.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { stableStringify } from './stableStringify'

describe('stableStringify', () => {
  it('is independent of key order at every level', () => {
    expect(stableStringify({ a: 1, b: 2 })).toBe(stableStringify({ b: 2, a: 1 }))
    expect(stableStringify({ x: { b: 2, a: 1 } })).toBe(stableStringify({ x: { a: 1, b: 2 } }))
  })

  it('preserves array order (order is significant)', () => {
    expect(stableStringify([1, 2])).not.toBe(stableStringify([2, 1]))
  })

  it('distinguishes nested differences', () => {
    expect(stableStringify({ tools: [{ id: 'fitz' }] }))
      .not.toBe(stableStringify({ tools: [{ id: 'pdfplumber' }] }))
  })

  it('handles primitives and null', () => {
    expect(stableStringify(null)).toBe('null')
    expect(stableStringify(3)).toBe('3')
    expect(stableStringify('x')).toBe('"x"')
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/lib/stableStringify.test.ts`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement**

`frontend/src/lib/stableStringify.ts`:

```ts
/**
 * Deterministic JSON string for equality comparison: object keys are sorted at every
 * nesting level; array order is preserved (order is significant). Not a stable *hash* —
 * used only to detect equal values (e.g. duplicate variant configs).
 */
export function stableStringify(value: unknown): string {
  if (value === null || typeof value !== 'object') {
    return JSON.stringify(value) ?? 'null'
  }
  if (Array.isArray(value)) {
    return `[${value.map(stableStringify).join(',')}]`
  }
  const obj = value as Record<string, unknown>
  const body = Object.keys(obj)
    .sort()
    .map((k) => `${JSON.stringify(k)}:${stableStringify(obj[k])}`)
    .join(',')
  return `{${body}}`
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run src/lib/stableStringify.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/stableStringify.ts frontend/src/lib/stableStringify.test.ts
git commit -m "feat(parser-eval-fe): recursive stableStringify for variant equality keys"
```

---

### Task 2: `NewRunDialog` variant list + config editors

**Files:**
- Modify (full rewrite): `frontend/src/components/parser-eval/NewRunDialog.tsx`
- Modify (rewrite): `frontend/src/components/parser-eval/NewRunDialog.test.tsx`

**Interfaces:**
- Consumes: `stableStringify` (Task 1), `ParseMethodSelector` + `PARSER_REGISTRY`, `ParseConfig`, `useParserEvalCases`, `useSourceDocuments`, `CreateRunRequest`.
- Produces: `NewRunDialog({ open, onOpenChange, projectId, onCreate })` — same props; submits `variants: { adapter, config }[]`.

- [ ] **Step 1: Rewrite the test**

Replace `frontend/src/components/parser-eval/NewRunDialog.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('@/hooks/useParserEval', () => ({
  useParserEvalCases: () => ({
    cases: [{ id: 'c1', sourceDocumentId: 's1', dimension: 'text', sourceMethod: 'human', reviewStatus: 'draft', createdAt: 'x' }],
    isLoading: false, error: null, fetchCases: vi.fn(), createCase: vi.fn(),
  }),
}))
vi.mock('@/hooks/useSourceDocuments', () => ({
  useSourceDocuments: () => ({ sourceDocuments: [{ id: 's1', filename: 'acme.pdf' }], isLoading: false, error: null, refresh: vi.fn() }),
}))

import { NewRunDialog } from './NewRunDialog'

function setup(onCreate = vi.fn()) {
  render(<NewRunDialog open onOpenChange={vi.fn()} projectId="p1" onCreate={onCreate} />)
  return onCreate
}

describe('NewRunDialog', () => {
  it('enables Run once a case and a variant are added', () => {
    setup()
    const runBtn = screen.getByRole('button', { name: /^run$/i })
    expect(runBtn).toBeDisabled()
    fireEvent.click(screen.getByLabelText('acme.pdf'))
    fireEvent.click(screen.getByRole('button', { name: /add variant/i }))
    expect(runBtn).not.toBeDisabled()
  })

  it('blocks duplicate variants and re-enables after removing one', () => {
    setup()
    fireEvent.click(screen.getByLabelText('acme.pdf'))
    const addBtn = screen.getByRole('button', { name: /add variant/i })
    fireEvent.click(addBtn)
    fireEvent.click(addBtn) // two identical docling/{} variants
    expect(screen.getByText(/duplicate variant/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^run$/i })).toBeDisabled()
    fireEvent.click(screen.getAllByRole('button', { name: /remove variant/i })[0])
    expect(screen.queryByText(/duplicate variant/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^run$/i })).not.toBeDisabled()
  })

  it('submits variants as { adapter, config }', async () => {
    const onCreate = setup()
    fireEvent.click(screen.getByLabelText('acme.pdf'))
    fireEvent.click(screen.getByRole('button', { name: /add variant/i }))
    fireEvent.click(screen.getByRole('button', { name: /^run$/i }))
    await waitFor(() =>
      expect(onCreate).toHaveBeenCalledWith({
        name: undefined,
        evalCaseIds: ['c1'],
        variants: [{ adapter: 'docling', config: {} }],
      })
    )
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run src/components/parser-eval/NewRunDialog.test.tsx`
Expected: FAIL (no "Add variant" button; old UI has adapter checkboxes).

- [ ] **Step 3: Rewrite the dialog**

Replace `frontend/src/components/parser-eval/NewRunDialog.tsx`:

```tsx
import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { ParseMethodSelector, PARSER_REGISTRY } from '@/components/documents/ParseMethodSelector'
import { useParserEvalCases } from '@/hooks/useParserEval'
import { useSourceDocuments } from '@/hooks/useSourceDocuments'
import { stableStringify } from '@/lib/stableStringify'
import type { ParseConfig } from '@/types/parsing'
import type { CreateRunRequest } from '@/types/parserEval'

type Variant = { adapter: string; config: ParseConfig }

const DEFAULT_ADAPTER = 'docling'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  projectId: string
  onCreate: (data: CreateRunRequest) => Promise<void>
}

export function NewRunDialog({ open, onOpenChange, projectId, onCreate }: Props) {
  const { cases } = useParserEvalCases(projectId)
  const { sourceDocuments } = useSourceDocuments()
  const [name, setName] = useState('')
  const [caseIds, setCaseIds] = useState<string[]>([])
  const [variants, setVariants] = useState<Variant[]>([])
  const [submitting, setSubmitting] = useState(false)

  const filename = (id: string) => sourceDocuments.find((d) => d.id === id)?.filename ?? id
  const toggleCase = (id: string) =>
    setCaseIds((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]))

  const addVariant = () =>
    setVariants((vs) => [
      ...vs,
      { adapter: DEFAULT_ADAPTER, config: PARSER_REGISTRY[DEFAULT_ADAPTER]?.defaultConfig ?? {} },
    ])
  const removeVariant = (i: number) => setVariants((vs) => vs.filter((_, idx) => idx !== i))
  const setVariant = (i: number, patch: Partial<Variant>) =>
    setVariants((vs) => vs.map((v, idx) => (idx === i ? { ...v, ...patch } : v)))

  const keys = variants.map((v) => `${v.adapter}|${stableStringify(v.config)}`)
  const hasDuplicate = new Set(keys).size !== keys.length
  const canSubmit = caseIds.length > 0 && variants.length > 0 && !hasDuplicate

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      await onCreate({ name: name || undefined, evalCaseIds: caseIds, variants })
      onOpenChange(false)
      setName('')
      setCaseIds([])
      setVariants([])
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>New Run</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="run-name">Name (optional)</Label>
            <Input id="run-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>

          <div className="space-y-2">
            <Label>Cases</Label>
            {cases.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No cases yet — create one in the Cases tab first.
              </p>
            ) : (
              cases.map((c) => (
                <div key={c.id} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    aria-label={filename(c.sourceDocumentId)}
                    checked={caseIds.includes(c.id)}
                    onCheckedChange={() => toggleCase(c.id)}
                  />
                  <span>
                    {filename(c.sourceDocumentId)} · {c.dimension}
                  </span>
                </div>
              ))
            )}
          </div>

          <div className="space-y-3">
            <Label>Variants</Label>
            {variants.map((v, i) => (
              <div key={i} className="flex items-start gap-2 rounded-md border p-3">
                <div className="flex-1">
                  <ParseMethodSelector
                    compact
                    parserType={v.adapter}
                    config={v.config}
                    onParserTypeChange={(adapter) => setVariant(i, { adapter })}
                    onConfigChange={(config) => setVariant(i, { config })}
                  />
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label="Remove variant"
                  onClick={() => removeVariant(i)}
                >
                  Remove
                </Button>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={addVariant}>
              Add variant
            </Button>
          </div>
        </div>

        {hasDuplicate && (
          <p className="text-xs text-destructive">
            Duplicate variant: the same adapter appears more than once with the same config — change or
            remove one.
          </p>
        )}
        {!canSubmit && !hasDuplicate && (
          <p className="text-xs text-muted-foreground">
            Select at least one case and add at least one variant to run. (Name is optional.)
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={!canSubmit || submitting} onClick={handleSubmit}>
            {submitting ? 'Starting…' : 'Run'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

> Adapter change resets that row's config: `ParseMethodSelector.handleParserChange` fires
> `onParserTypeChange(newType)` then `onConfigChange(defaultConfig)`; the two `setVariant` calls compose
> (both functional updates on index `i`), leaving `{ adapter: newType, config: newDefault }`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/components/parser-eval/NewRunDialog.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Typecheck, lint, build**

Run: `cd frontend && npx tsc --noEmit && npx eslint src/components/parser-eval/NewRunDialog.tsx src/lib/stableStringify.ts && npm run build`
Expected: all PASS (no unused `ADAPTER_OPTIONS`/`Checkbox`-for-adapters leftovers; `Checkbox` still used for cases).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/parser-eval/NewRunDialog.tsx frontend/src/components/parser-eval/NewRunDialog.test.tsx
git commit -m "feat(parser-eval-fe): variant list with per-adapter config + duplicate guard"
```

---

## Self-Review

**Spec coverage:**
- §Component changes (variant list, reuse `ParseMethodSelector`, submit shape) → Task 2. ✅
- §Duplicate-variant guard (recursive stable key, disable + warning) → Task 1 (`stableStringify`) + Task 2 (key/`hasDuplicate`/warning). ✅
- §Validation & gating (≥1 case, ≥1 variant, no dup; updated hint) → Task 2 (`canSubmit`, hints). ✅
- §Acceptance criteria 1–5 → Task 2 test + UI; criterion 6 (lint/build/vitest) → Task 2 Step 5. ✅
- §Testing (add variant enables; duplicate blocks + remove re-enables; submit shape) → Task 2 Step 1. ✅
- No backend change required → nothing in either task touches backend. ✅

**Placeholder scan:** No TBD/TODO/"handle edge cases". All steps carry full code. The adapter-change compose behavior is shown (blockquote after Step 3), not hand-waved.

**Type consistency:** `Variant = { adapter: string; config: ParseConfig }` consistent across Task 2. `stableStringify(value: unknown): string` matches its use in the dialog key. `ParseMethodSelector` prop names (`parserType`/`config`/`onParserTypeChange`/`onConfigChange`/`compact`) match the actual component signature. Submit payload `{ name?, evalCaseIds, variants }` matches `CreateRunRequest`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-06-parser-eval-variant-config-editor.md`. Per the project pre-implementation gate, a confirmed GitHub issue must exist before implementation. Two execution options after that:

1. **Subagent-Driven (recommended)** — a fresh subagent per task, review between tasks.
2. **Inline Execution** — execute tasks in this session with checkpoints.
