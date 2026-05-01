# CDM Index Unit 4 — Wizard Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the wide-net resolver bridge in the Create Index wizard with an explicit parse-config family selector (Step 2) and parsed-document picker (Step 4), producing a 6-step wizard that submits `parsed_document_ids` directly.

**Architecture:** All backend APIs are already in place from Units 1–3 (`GET /parse-runs/configs`, `GET /parsed-documents`, `IndexCreate` validation). This unit is entirely frontend: two new picker components, a `listParseConfigs` API function, a rebuilt `CreateIndexPage` (4 → 6 steps), deletion of the unused `IndexCreateDialog`, and removal of the bridge helper from `lib/parsed-documents.ts`.

**Tech Stack:** React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS, Vitest + React Testing Library

---

## File Structure

| Action | Path | Responsibility |
|---|---|---|
| Modify | `frontend/src/lib/parsed-documents.ts` | Add `ParseConfigOption` + `listParseConfigs`; remove bridge |
| Create | `frontend/src/components/indexes/ParseConfigFamilySelector.tsx` | Step 2 UI: card-based family picker |
| Create | `frontend/src/components/indexes/ParseConfigFamilySelector.test.tsx` | Tests for the family picker |
| Create | `frontend/src/components/indexes/ParsedDocumentPicker.tsx` | Step 4 UI: self-fetching parsed-doc list |
| Create | `frontend/src/components/indexes/ParsedDocumentPicker.test.tsx` | Tests for the doc picker |
| Modify | `frontend/src/pages/CreateIndexPage.tsx` | Rebuild wizard (6 steps) |
| Create | `frontend/src/pages/CreateIndexPage.test.tsx` | Integration tests for wizard flow |
| Delete | `frontend/src/components/indexes/IndexCreateDialog.tsx` | Not rendered anywhere; replaced by wizard |
| Delete | `frontend/src/components/indexes/IndexCreateDialog.test.tsx` | Tests for the deleted component |

---

### Task 1: Add `listParseConfigs` and `ParseConfigOption` to `lib/parsed-documents.ts`

**Files:**
- Modify: `frontend/src/lib/parsed-documents.ts`

- [ ] **Step 1: Add the `ParseConfigOption` interface and `listParseConfigs` function**

In `frontend/src/lib/parsed-documents.ts`, after the existing `ParsedDocumentListItem` interface (around line 13), insert:

```ts
export interface ParseConfigOption {
  parser: string
  parseConfigHash: string
  config: Record<string, unknown>
  parsedDocumentCount: number
  hasFullMarkdown: boolean
  latestParsedAt: string
}

export async function listParseConfigs(
  projectId: string,
): Promise<ParseConfigOption[]> {
  const response = await apiClient.get<ParseConfigOption[]>(
    `/projects/${projectId}/parse-runs/configs`,
  )
  return response.data
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `npm run --prefix frontend build 2>&1 | grep "error TS" | head -10`
Expected: no TypeScript errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/parsed-documents.ts
git commit -m "feat(indexes): add listParseConfigs and ParseConfigOption type"
```

---

### Task 2: `ParseConfigFamilySelector` component

**Files:**
- Create: `frontend/src/components/indexes/ParseConfigFamilySelector.tsx`
- Create: `frontend/src/components/indexes/ParseConfigFamilySelector.test.tsx`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/indexes/ParseConfigFamilySelector.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ParseConfigFamilySelector } from './ParseConfigFamilySelector'
import type { ParseConfigOption } from '@/lib/parsed-documents'

const llamaOption: ParseConfigOption = {
  parser: 'llamaparse',
  parseConfigHash: 'abc123',
  config: { result_type: 'markdown', num_workers: 4 },
  parsedDocumentCount: 3,
  hasFullMarkdown: true,
  latestParsedAt: '2026-04-30T09:11:00Z',
}

const landingOption: ParseConfigOption = {
  parser: 'landingai',
  parseConfigHash: 'def456',
  config: { model: 'default' },
  parsedDocumentCount: 1,
  hasFullMarkdown: false,
  latestParsedAt: '2026-04-29T14:32:00Z',
}

function wrap(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('ParseConfigFamilySelector', () => {
  it('renders parser names and document counts', () => {
    wrap(
      <ParseConfigFamilySelector
        options={[llamaOption, landingOption]}
        selected={null}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByText('LlamaParse')).toBeInTheDocument()
    expect(screen.getByText('LandingAI')).toBeInTheDocument()
    expect(screen.getByText('3 parsed documents')).toBeInTheDocument()
    expect(screen.getByText('1 parsed document')).toBeInTheDocument()
  })

  it('shows markdown badge when hasFullMarkdown is true', () => {
    wrap(
      <ParseConfigFamilySelector
        options={[llamaOption]}
        selected={null}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByText('markdown')).toBeInTheDocument()
  })

  it('does not show markdown badge when hasFullMarkdown is false', () => {
    wrap(
      <ParseConfigFamilySelector
        options={[landingOption]}
        selected={null}
        onChange={vi.fn()}
      />,
    )
    expect(screen.queryByText('markdown')).not.toBeInTheDocument()
  })

  it('calls onChange with parser and parseConfigHash when an option is clicked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    wrap(
      <ParseConfigFamilySelector
        options={[llamaOption, landingOption]}
        selected={null}
        onChange={onChange}
      />,
    )
    await user.click(screen.getByRole('button', { name: /llamaparse/i }))
    expect(onChange).toHaveBeenCalledWith({
      parser: 'llamaparse',
      parseConfigHash: 'abc123',
    })
  })

  it('renders the empty state when no options are provided', () => {
    wrap(
      <ParseConfigFamilySelector
        options={[]}
        selected={null}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByText(/no parse runs found/i)).toBeInTheDocument()
  })

  it('marks the selected option with aria-pressed', () => {
    wrap(
      <ParseConfigFamilySelector
        options={[llamaOption, landingOption]}
        selected={{ parser: 'llamaparse', parseConfigHash: 'abc123' }}
        onChange={vi.fn()}
      />,
    )
    expect(
      screen.getByRole('button', { name: /llamaparse/i }),
    ).toHaveAttribute('aria-pressed', 'true')
    expect(
      screen.getByRole('button', { name: /landingai/i }),
    ).toHaveAttribute('aria-pressed', 'false')
  })
})
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `npx --prefix frontend vitest run src/components/indexes/ParseConfigFamilySelector.test.tsx`
Expected: FAIL — component does not exist yet

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/indexes/ParseConfigFamilySelector.tsx`:

```tsx
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import type { ParseConfigOption } from '@/lib/parsed-documents'

interface SelectedFamily {
  parser: string
  parseConfigHash: string
}

interface ParseConfigFamilySelectorProps {
  options: ParseConfigOption[]
  selected: SelectedFamily | null
  onChange: (selected: SelectedFamily) => void
}

const PARSER_NAMES: Record<string, string> = {
  llamaparse: 'LlamaParse',
  landingai: 'LandingAI',
}

function parserDisplayName(parser: string): string {
  return PARSER_NAMES[parser] ?? parser
}

function summarizeConfig(config: Record<string, unknown>): string {
  const parts: string[] = []
  if (config.result_type) parts.push(`type: ${config.result_type}`)
  if (config.num_workers) parts.push(`workers: ${config.num_workers}`)
  if (parts.length === 0) return 'Default config'
  return parts.join(' · ')
}

export function ParseConfigFamilySelector({
  options,
  selected,
  onChange,
}: ParseConfigFamilySelectorProps) {
  if (options.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <p className="mb-2">No parse runs found for this project.</p>
        <p>
          <Link to="/documents" className="underline text-primary">
            Parse some documents first.
          </Link>
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {options.map((option) => {
        const isSelected =
          selected?.parser === option.parser &&
          selected?.parseConfigHash === option.parseConfigHash

        return (
          <button
            key={`${option.parser}|${option.parseConfigHash}`}
            type="button"
            aria-pressed={isSelected}
            onClick={() =>
              onChange({
                parser: option.parser,
                parseConfigHash: option.parseConfigHash,
              })
            }
            className={`w-full text-left rounded-lg border p-4 transition-colors
              ${
                isSelected
                  ? 'border-primary ring-2 ring-primary/20 bg-primary/5'
                  : 'border-border hover:border-primary/40 hover:bg-muted/30'
              }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-semibold">
                    {parserDisplayName(option.parser)}
                  </span>
                  {option.hasFullMarkdown && (
                    <Badge variant="secondary" className="text-xs">
                      markdown
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-muted-foreground truncate">
                  {summarizeConfig(option.config)}
                </p>
              </div>
              <span className="text-sm text-muted-foreground whitespace-nowrap">
                {option.parsedDocumentCount}{' '}
                {option.parsedDocumentCount === 1
                  ? 'parsed document'
                  : 'parsed documents'}
              </span>
            </div>
          </button>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `npx --prefix frontend vitest run src/components/indexes/ParseConfigFamilySelector.test.tsx`
Expected: PASS — all 6 tests green

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/indexes/ParseConfigFamilySelector.tsx \
        frontend/src/components/indexes/ParseConfigFamilySelector.test.tsx
git commit -m "feat(indexes): add ParseConfigFamilySelector component"
```

---

### Task 3: `ParsedDocumentPicker` component

**Files:**
- Create: `frontend/src/components/indexes/ParsedDocumentPicker.tsx`
- Create: `frontend/src/components/indexes/ParsedDocumentPicker.test.tsx`

The picker is self-fetching — it manages the `latestPerSource` toggle, search filter, and API call internally. The parent only cares about `selectedIds`.

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/indexes/ParsedDocumentPicker.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ParsedDocumentPicker } from './ParsedDocumentPicker'

vi.mock('@/lib/parsed-documents', () => ({
  listParsedDocuments: vi.fn(),
}))

import { listParsedDocuments } from '@/lib/parsed-documents'

const docA = {
  id: 'pd-1',
  parseRunId: 'pr-1',
  parser: 'llamaparse',
  parseConfigHash: 'abc',
  sourceDocumentId: 'sd-1',
  sourceFilename: 'acme-msa.pdf',
  hasFullMarkdown: true,
  blockCount: 12,
  parsedAt: '2026-04-30T09:11:00Z',
}

const docB = {
  id: 'pd-2',
  parseRunId: 'pr-2',
  parser: 'llamaparse',
  parseConfigHash: 'abc',
  sourceDocumentId: 'sd-2',
  sourceFilename: 'vendor-form.pdf',
  hasFullMarkdown: true,
  blockCount: 8,
  parsedAt: '2026-04-30T11:48:00Z',
}

const olderDocA = {
  id: 'pd-3',
  parseRunId: 'pr-3',
  parser: 'llamaparse',
  parseConfigHash: 'abc',
  sourceDocumentId: 'sd-1',
  sourceFilename: 'acme-msa.pdf',
  hasFullMarkdown: true,
  blockCount: 10,
  parsedAt: '2026-04-29T14:32:00Z',
}

const defaultProps = {
  projectId: 'proj-1',
  parser: 'llamaparse',
  parseConfigHash: 'abc',
  representation: 'full_markdown' as const,
  selectedIds: [],
  onChange: vi.fn(),
}

describe('ParsedDocumentPicker', () => {
  beforeEach(() => {
    vi.mocked(listParsedDocuments).mockResolvedValue([docA, docB])
  })

  it('fetches with latestPerSource=true by default and shows both docs', async () => {
    render(<ParsedDocumentPicker {...defaultProps} />)
    await waitFor(() => {
      expect(screen.getByText('acme-msa.pdf')).toBeInTheDocument()
      expect(screen.getByText('vendor-form.pdf')).toBeInTheDocument()
    })
    expect(vi.mocked(listParsedDocuments)).toHaveBeenCalledWith('proj-1', {
      parser: 'llamaparse',
      parseConfigHash: 'abc',
      representation: 'full_markdown',
      latestPerSource: true,
    })
  })

  it('refetches with latestPerSource=false when the toggle is unchecked', async () => {
    vi.mocked(listParsedDocuments)
      .mockResolvedValueOnce([docA, docB])
      .mockResolvedValueOnce([docA, docB, olderDocA])

    const user = userEvent.setup()
    render(<ParsedDocumentPicker {...defaultProps} />)
    await waitFor(() => expect(screen.getByText('acme-msa.pdf')).toBeInTheDocument())

    await user.click(screen.getByRole('checkbox', { name: /latest per source/i }))

    await waitFor(() =>
      expect(vi.mocked(listParsedDocuments)).toHaveBeenCalledWith('proj-1', {
        parser: 'llamaparse',
        parseConfigHash: 'abc',
        representation: 'full_markdown',
        latestPerSource: false,
      }),
    )
  })

  it('calls onChange with the doc id when a row checkbox is checked', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<ParsedDocumentPicker {...defaultProps} onChange={onChange} />)
    await waitFor(() => expect(screen.getByText('acme-msa.pdf')).toBeInTheDocument())

    await user.click(screen.getByRole('checkbox', { name: 'acme-msa.pdf' }))

    expect(onChange).toHaveBeenCalledWith(['pd-1'])
  })

  it('filters rows by filename when search is typed', async () => {
    const user = userEvent.setup()
    render(<ParsedDocumentPicker {...defaultProps} />)
    await waitFor(() => expect(screen.getByText('acme-msa.pdf')).toBeInTheDocument())

    await user.type(screen.getByPlaceholderText(/search by filename/i), 'vendor')

    expect(screen.queryByText('acme-msa.pdf')).not.toBeInTheDocument()
    expect(screen.getByText('vendor-form.pdf')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `npx --prefix frontend vitest run src/components/indexes/ParsedDocumentPicker.test.tsx`
Expected: FAIL — component does not exist yet

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/indexes/ParsedDocumentPicker.tsx`:

```tsx
import { useState, useEffect, useCallback } from 'react'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Label } from '@/components/ui/label'
import { listParsedDocuments } from '@/lib/parsed-documents'
import type { ParsedDocumentListItem } from '@/lib/parsed-documents'
import type { SourceRepresentation } from '@/types/index'

interface ParsedDocumentPickerProps {
  projectId: string
  parser: string
  parseConfigHash: string
  representation: SourceRepresentation
  selectedIds: string[]
  onChange: (ids: string[]) => void
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function ParsedDocumentPicker({
  projectId,
  parser,
  parseConfigHash,
  representation,
  selectedIds,
  onChange,
}: ParsedDocumentPickerProps) {
  const [docs, setDocs] = useState<ParsedDocumentListItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [latestPerSource, setLatestPerSource] = useState(true)
  const [search, setSearch] = useState('')

  const fetchDocs = useCallback(async () => {
    setIsLoading(true)
    try {
      const result = await listParsedDocuments(projectId, {
        parser,
        parseConfigHash,
        representation,
        latestPerSource,
      })
      setDocs(result)
    } finally {
      setIsLoading(false)
    }
  }, [projectId, parser, parseConfigHash, representation, latestPerSource])

  useEffect(() => {
    fetchDocs()
  }, [fetchDocs])

  const filtered = docs.filter(
    (d) =>
      !search.trim() ||
      (d.sourceFilename ?? '').toLowerCase().includes(search.trim().toLowerCase()),
  )

  function toggleId(id: string) {
    if (selectedIds.includes(id)) {
      onChange(selectedIds.filter((x) => x !== id))
    } else {
      onChange([...selectedIds, id])
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Checkbox
            id="latest-per-source"
            checked={latestPerSource}
            onCheckedChange={(v) => setLatestPerSource(!!v)}
            aria-label="Latest per source"
          />
          <Label htmlFor="latest-per-source" className="cursor-pointer">
            Latest per source document
          </Label>
        </div>
        <Input
          className="w-56"
          placeholder="Search by filename..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-14 w-full rounded-lg" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <p className="text-center py-8 text-muted-foreground">
          No parsed documents found.
        </p>
      ) : (
        <div className="space-y-2">
          {filtered.map((doc) => (
            <label
              key={doc.id}
              className="flex items-center gap-3 rounded-lg border p-3 cursor-pointer hover:bg-muted/30 has-[:checked]:border-primary has-[:checked]:bg-primary/5"
            >
              <Checkbox
                checked={selectedIds.includes(doc.id)}
                onCheckedChange={() => toggleId(doc.id)}
                aria-label={doc.sourceFilename ?? 'Unknown file'}
              />
              <span className="flex-1 min-w-0">
                <span className="font-medium truncate block">
                  {doc.sourceFilename ?? 'Unknown file'}
                </span>
                <span className="text-xs text-muted-foreground">
                  run {doc.parseRunId.slice(0, 5)}… · {formatDate(doc.parsedAt)}
                </span>
              </span>
              {doc.hasFullMarkdown && (
                <Badge variant="secondary" className="text-xs shrink-0">
                  markdown ✓
                </Badge>
              )}
              <Badge variant="outline" className="text-xs shrink-0 font-mono">
                {doc.blockCount} blocks
              </Badge>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `npx --prefix frontend vitest run src/components/indexes/ParsedDocumentPicker.test.tsx`
Expected: PASS — all 4 tests green

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/indexes/ParsedDocumentPicker.tsx \
        frontend/src/components/indexes/ParsedDocumentPicker.test.tsx
git commit -m "feat(indexes): add ParsedDocumentPicker component"
```

---

### Task 4: Rebuild `CreateIndexPage` with 6-step wizard

**Files:**
- Modify: `frontend/src/pages/CreateIndexPage.tsx`
- Create: `frontend/src/pages/CreateIndexPage.test.tsx`

Steps: 1 Details → 2 Parse Config → 3 Source → 4 Documents → 5 Chunking → 6 Preview + Submit.

- [ ] **Step 1: Write failing tests**

Create `frontend/src/pages/CreateIndexPage.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import CreateIndexPage from './CreateIndexPage'

vi.mock('@/contexts/ProjectContext', () => ({
  useProject: () => ({
    currentProject: { id: 'proj-1', name: 'Test Project' },
  }),
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return { ...actual, useNavigate: () => vi.fn() }
})

vi.mock('@/hooks/useIndexes', () => ({
  useIndexes: () => ({
    createIndex: vi.fn().mockResolvedValue({ id: 'new-idx' }),
    previewChunks: vi.fn().mockResolvedValue({
      totalChunksEstimate: 2,
      avgChunkSizeChars: 100,
      avgChunkSizeTokens: 25,
      minChunkSizeChars: 80,
      maxChunkSizeChars: 120,
      previewChunks: [],
    }),
  }),
}))

vi.mock('@/lib/parsed-documents', () => ({
  listParseConfigs: vi.fn().mockResolvedValue([
    {
      parser: 'llamaparse',
      parseConfigHash: 'abc123',
      config: { result_type: 'markdown' },
      parsedDocumentCount: 2,
      hasFullMarkdown: true,
      latestParsedAt: '2026-04-30T09:00:00Z',
    },
  ]),
  listParsedDocuments: vi.fn().mockResolvedValue([
    {
      id: 'pd-1',
      parseRunId: 'pr-1',
      parser: 'llamaparse',
      parseConfigHash: 'abc123',
      sourceDocumentId: 'sd-1',
      sourceFilename: 'acme-msa.pdf',
      hasFullMarkdown: true,
      blockCount: 12,
      parsedAt: '2026-04-30T09:11:00Z',
    },
  ]),
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <CreateIndexPage />
    </MemoryRouter>,
  )
}

describe('CreateIndexPage wizard', () => {
  it('starts at step 1 and disables Continue when name is empty', () => {
    renderPage()
    expect(screen.getByRole('heading', { name: 'Details' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled()
  })

  it('advances to step 2 (Parse Config) after entering a name', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(screen.getByLabelText(/name/i), 'My Index')
    await user.click(screen.getByRole('button', { name: /continue/i }))
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Parse Config' })).toBeInTheDocument(),
    )
  })

  it('disables Continue at step 2 until a family is selected', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(screen.getByLabelText(/name/i), 'My Index')
    await user.click(screen.getByRole('button', { name: /continue/i }))
    await waitFor(() => screen.getByText('LlamaParse'))

    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: /llamaparse/i }))
    expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled()
  })

  it('disables Continue at step 4 until a parsed-doc is selected', async () => {
    const user = userEvent.setup()
    renderPage()
    // Step 1 → 2
    await user.type(screen.getByLabelText(/name/i), 'My Index')
    await user.click(screen.getByRole('button', { name: /continue/i }))
    await waitFor(() => screen.getByText('LlamaParse'))
    await user.click(screen.getByRole('button', { name: /llamaparse/i }))
    await user.click(screen.getByRole('button', { name: /continue/i }))
    // Step 3 → 4
    await user.click(screen.getByRole('button', { name: /continue/i }))
    // Step 4
    await waitFor(() => screen.getByText('acme-msa.pdf'))
    expect(screen.getByRole('button', { name: /continue/i })).toBeDisabled()
    await user.click(screen.getByRole('checkbox', { name: 'acme-msa.pdf' }))
    expect(screen.getByRole('button', { name: /continue/i })).not.toBeDisabled()
  })
})
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `npx --prefix frontend vitest run src/pages/CreateIndexPage.test.tsx`
Expected: FAIL — wizard doesn't have the new steps yet

- [ ] **Step 3: Rebuild `CreateIndexPage`**

Replace the entire contents of `frontend/src/pages/CreateIndexPage.tsx`:

```tsx
import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { AxiosError } from 'axios'
import { useProject } from '@/contexts/ProjectContext'
import { useIndexes } from '@/hooks/useIndexes'
import { IndexConfig, ChunkPreviewResponse, SourceRepresentation } from '@/types/index'
import { listParseConfigs } from '@/lib/parsed-documents'
import type { ParseConfigOption } from '@/lib/parsed-documents'
import {
  Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/components/ui/select'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { Slider } from '@/components/ui/slider'
import { ParseConfigFamilySelector } from '@/components/indexes/ParseConfigFamilySelector'
import { ParsedDocumentPicker } from '@/components/indexes/ParsedDocumentPicker'
import { ChunkPreviewPanel } from '@/components/indexes/ChunkPreviewPanel'
import { toast } from 'sonner'
import {
  FileText, ChevronRight, ChevronLeft, Info, Check,
  Database, FileCode, Layers, Settings, Eye, Loader2,
} from 'lucide-react'

const STEPS = [
  { number: 1, title: 'Details',      icon: FileText  },
  { number: 2, title: 'Parse Config', icon: Database  },
  { number: 3, title: 'Source',       icon: FileCode  },
  { number: 4, title: 'Documents',    icon: Layers    },
  { number: 5, title: 'Chunking',     icon: Settings  },
  { number: 6, title: 'Preview',      icon: Eye       },
] as const

interface SelectedFamily {
  parser: string
  parseConfigHash: string
  hasFullMarkdown: boolean
}

const DEFAULT_CONFIG: Partial<IndexConfig> = {
  sourceRepresentation: 'full_text',
  chunkingStrategy: 'recursive_character',
  chunkSize: 512,
  chunkOverlap: 50,
  chunkUnit: 'characters',
  splitHeadingLevel: 2,
  maxSectionChars: 4000,
  embeddingProvider: 'openai',
  embeddingModel: 'text-embedding-3-small',
}

function extractErrorMessage(data: unknown, fallback: string): string {
  if (!data || typeof data !== 'object') return fallback
  const d = data as Record<string, unknown>
  if (typeof d.detail === 'string') return d.detail
  if (Array.isArray(d.detail)) {
    return d.detail
      .map((e: unknown) => {
        if (e && typeof e === 'object' && 'msg' in e)
          return String((e as Record<string, unknown>).msg)
        return String(e)
      })
      .join('; ')
  }
  return fallback
}

const STEP_DESCRIPTIONS: Record<number, string> = {
  1: 'Enter basic information about your index',
  2: 'Choose which parse-config family to index',
  3: 'Select which segment of each parsed document to read',
  4: 'Choose which parsed documents to include',
  5: 'Configure chunking and embedding settings',
  6: 'Preview how documents will be chunked, then create the index',
}

export default function CreateIndexPage() {
  const navigate = useNavigate()
  const { currentProject } = useProject()
  const { createIndex, previewChunks } = useIndexes(currentProject?.id ?? null)

  const [currentStep, setCurrentStep] = useState(1)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)
  const [preview, setPreview] = useState<ChunkPreviewResponse | null>(null)
  const [previewDocId, setPreviewDocId] = useState<string | null>(null)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [parseConfigs, setParseConfigs] = useState<ParseConfigOption[]>([])
  const [selectedFamily, setSelectedFamily] = useState<SelectedFamily | null>(null)
  const [selectedParsedDocIds, setSelectedParsedDocIds] = useState<string[]>([])
  const [config, setConfig] = useState<Partial<IndexConfig>>(DEFAULT_CONFIG)

  useEffect(() => {
    if (!currentProject) { navigate('/index'); return }
    listParseConfigs(currentProject.id)
      .then(setParseConfigs)
      .catch(() => toast.error('Failed to load parse configurations'))
  }, [currentProject, navigate])

  // Auto-select first parsed-doc for preview when entering step 6
  useEffect(() => {
    if (currentStep === 6 && selectedParsedDocIds.length > 0 && !previewDocId) {
      setPreviewDocId(selectedParsedDocIds[0])
    }
  }, [currentStep, selectedParsedDocIds, previewDocId])

  const updateConfig = (key: keyof IndexConfig, value: IndexConfig[keyof IndexConfig]) => {
    setConfig((prev) => ({ ...prev, [key]: value }))
    setPreview(null)
  }

  const handleSourceRepresentationChange = (value: SourceRepresentation) => {
    updateConfig('sourceRepresentation', value)
    if (value === 'full_markdown') updateConfig('chunkingStrategy', 'markdown_heading')
    else if (value === 'full_text') updateConfig('chunkingStrategy', 'recursive_character')
    setSelectedParsedDocIds([])
    setPreview(null)
  }

  const handleFamilyChange = (f: { parser: string; parseConfigHash: string }) => {
    const opt = parseConfigs.find(
      (o) => o.parser === f.parser && o.parseConfigHash === f.parseConfigHash,
    )
    const hasMarkdown = opt?.hasFullMarkdown ?? false
    setSelectedFamily({ ...f, hasFullMarkdown: hasMarkdown })
    setSelectedParsedDocIds([])
    setPreview(null)
    if (config.sourceRepresentation === 'full_markdown' && !hasMarkdown) {
      updateConfig('sourceRepresentation', 'full_text')
      updateConfig('chunkingStrategy', 'recursive_character')
    }
  }

  const canProceedFromStep = (step: number): boolean => {
    switch (step) {
      case 1: return name.trim() !== ''
      case 2: return selectedFamily !== null
      case 3: return true
      case 4: return selectedParsedDocIds.length > 0
      default: return true
    }
  }

  const isStepAccessible = (step: number): boolean => {
    if (step <= currentStep) return true
    if (step === currentStep + 1 && canProceedFromStep(currentStep)) return true
    return false
  }

  const handleNext = () => {
    if (currentStep < STEPS.length && canProceedFromStep(currentStep))
      setCurrentStep(currentStep + 1)
  }

  const handleBack = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1)
  }

  const handlePreview = useCallback(async () => {
    if (!previewDocId) { toast.error('Select a document to preview'); return }
    setIsPreviewLoading(true)
    try {
      const result = await previewChunks({
        parsedDocumentId: previewDocId,
        config: {
          ...config,
          parser: selectedFamily!.parser,
          parseConfigHash: selectedFamily!.parseConfigHash,
        } as IndexConfig,
        maxChunks: 10,
      })
      setPreview(result)
    } catch (error) {
      if (error instanceof AxiosError && error.response)
        toast.error(extractErrorMessage(error.response.data, 'Failed to generate preview'))
      else if (error instanceof Error) toast.error(error.message)
      else toast.error('Failed to generate preview')
    } finally {
      setIsPreviewLoading(false)
    }
  }, [previewDocId, config, selectedFamily, previewChunks])

  const handleSubmit = async (autoProcess: boolean) => {
    if (!name.trim()) { toast.error('Index name is required'); return }
    if (!selectedFamily) { toast.error('Select a parse config family'); return }
    if (selectedParsedDocIds.length === 0) { toast.error('Select at least one parsed document'); return }
    if (!currentProject) { toast.error('No project selected'); return }

    setIsSubmitting(true)
    try {
      await createIndex({
        name: name.trim(),
        description: description.trim() || undefined,
        parsedDocumentIds: selectedParsedDocIds,
        config: {
          ...config,
          parser: selectedFamily.parser,
          parseConfigHash: selectedFamily.parseConfigHash,
        } as IndexConfig,
        autoProcess,
      })
      toast.success(autoProcess ? 'Index created and processing started' : 'Index saved as draft')
      navigate('/index')
    } catch (error) {
      if (error instanceof AxiosError && error.response)
        toast.error(extractErrorMessage(error.response.data, 'Failed to create index'))
      else if (error instanceof Error) toast.error(error.message)
      else toast.error('Failed to create index')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="-m-6 min-h-[calc(100vh-4rem)]">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold">Create Index</h1>
          <p className="text-muted-foreground mt-2">
            Configure how your parsed documents will be chunked and embedded for retrieval
          </p>
        </div>

        {/* Step Indicator */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            {STEPS.map((step, index) => {
              const StepIcon = step.icon
              const isCompleted = currentStep > step.number
              const isCurrent = currentStep === step.number
              const isClickable = isStepAccessible(step.number)
              return (
                <div key={step.number} className="flex items-center flex-1 last:flex-initial">
                  <div
                    className={`flex flex-col items-center ${isClickable ? 'cursor-pointer' : 'cursor-not-allowed'}`}
                    onClick={() => isClickable && setCurrentStep(step.number)}
                  >
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-1 transition-all
                      ${isCompleted ? 'bg-primary text-primary-foreground'
                        : isCurrent ? 'bg-primary text-primary-foreground ring-4 ring-primary/20'
                        : isClickable ? 'bg-muted text-muted-foreground hover:bg-muted/80'
                        : 'bg-muted/50 text-muted-foreground/50'}`}
                    >
                      {isCompleted ? <Check className="w-4 h-4" /> : <StepIcon className="w-4 h-4" />}
                    </div>
                    <span className={`text-xs font-medium ${isCurrent ? 'text-primary' : isClickable ? 'text-foreground' : 'text-muted-foreground/50'}`}>
                      {step.title}
                    </span>
                  </div>
                  {index < STEPS.length - 1 && (
                    <div className={`flex-1 h-px mx-2 mt-[-0.75rem] ${isCompleted ? 'bg-primary' : 'bg-border'}`} />
                  )}
                </div>
              )
            })}
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{STEPS[currentStep - 1].title}</CardTitle>
            <CardDescription>{STEP_DESCRIPTIONS[currentStep]}</CardDescription>
          </CardHeader>

          <CardContent className="min-h-[400px]">
            {/* Step 1: Details */}
            {currentStep === 1 && (
              <div className="space-y-6 max-w-lg">
                <div className="space-y-2">
                  <Label htmlFor="name">Name <span className="text-destructive">*</span></Label>
                  <Input
                    id="name"
                    placeholder="My Index"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    disabled={isSubmitting}
                    autoFocus
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    placeholder="Optional description..."
                    rows={4}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    disabled={isSubmitting}
                  />
                </div>
              </div>
            )}

            {/* Step 2: Parse-Config Family */}
            {currentStep === 2 && (
              <ParseConfigFamilySelector
                options={parseConfigs}
                selected={selectedFamily}
                onChange={handleFamilyChange}
              />
            )}

            {/* Step 3: Source Representation */}
            {currentStep === 3 && (
              <div className="space-y-4 max-w-lg">
                <div className="space-y-2">
                  <Label>Source segment</Label>
                  <ToggleGroup
                    type="single"
                    value={config.sourceRepresentation ?? 'full_text'}
                    onValueChange={(v) =>
                      v && handleSourceRepresentationChange(v as SourceRepresentation)
                    }
                    className="justify-start"
                  >
                    <ToggleGroupItem value="full_text" aria-label="Full text">
                      Full text
                    </ToggleGroupItem>
                    <ToggleGroupItem
                      value="full_markdown"
                      aria-label="Full Markdown"
                      disabled={!selectedFamily?.hasFullMarkdown}
                    >
                      Full Markdown
                    </ToggleGroupItem>
                  </ToggleGroup>
                  {!selectedFamily?.hasFullMarkdown && (
                    <p className="text-sm text-muted-foreground">
                      Full Markdown is unavailable — the selected parse-config family does not produce markdown output.
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Step 4: Parsed Documents */}
            {currentStep === 4 && selectedFamily && (
              <div className="space-y-4">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-sm text-muted-foreground">
                    Select parsed documents to include in this index
                  </p>
                  <Badge variant="outline">{selectedParsedDocIds.length} selected</Badge>
                </div>
                {selectedParsedDocIds.length === 0 && (
                  <Alert>
                    <Info className="h-4 w-4" />
                    <AlertDescription>
                      Select at least one parsed document to continue
                    </AlertDescription>
                  </Alert>
                )}
                <ParsedDocumentPicker
                  projectId={currentProject!.id}
                  parser={selectedFamily.parser}
                  parseConfigHash={selectedFamily.parseConfigHash}
                  representation={config.sourceRepresentation ?? 'full_text'}
                  selectedIds={selectedParsedDocIds}
                  onChange={setSelectedParsedDocIds}
                />
              </div>
            )}

            {/* Step 5: Chunking & Embedding */}
            {currentStep === 5 && (
              <div className="space-y-8">
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Chunking</h3>
                  {config.sourceRepresentation === 'full_markdown' ? (
                    <>
                      <div className="space-y-2">
                        <Label>Heading split level</Label>
                        <ToggleGroup
                          type="single"
                          value={String(config.splitHeadingLevel ?? 2)}
                          onValueChange={(v) => v && updateConfig('splitHeadingLevel', parseInt(v))}
                          className="justify-start"
                        >
                          <ToggleGroupItem value="1">H1 only</ToggleGroupItem>
                          <ToggleGroupItem value="2">H1 + H2</ToggleGroupItem>
                          <ToggleGroupItem value="3">H1 + H2 + H3</ToggleGroupItem>
                        </ToggleGroup>
                      </div>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <Label>Max section size</Label>
                          <span className="text-sm text-muted-foreground">
                            {(config.maxSectionChars ?? 4000).toLocaleString()} chars
                          </span>
                        </div>
                        <Slider
                          min={500} max={16000} step={500}
                          value={[config.maxSectionChars ?? 4000]}
                          onValueChange={([v]) => updateConfig('maxSectionChars', v)}
                        />
                        <p className="text-xs text-muted-foreground">
                          Sections larger than this are split further.
                        </p>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label>Strategy</Label>
                          <Select
                            value={config.chunkingStrategy}
                            onValueChange={(v) =>
                              updateConfig('chunkingStrategy', v as IndexConfig['chunkingStrategy'])
                            }
                          >
                            <SelectTrigger><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="recursive_character">
                                Recursive Character (Recommended)
                              </SelectItem>
                              <SelectItem value="fixed_size">Fixed Size</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="space-y-2">
                          <Label>Unit</Label>
                          <Select
                            value={config.chunkUnit}
                            onValueChange={(v) =>
                              updateConfig('chunkUnit', v as IndexConfig['chunkUnit'])
                            }
                          >
                            <SelectTrigger><SelectValue /></SelectTrigger>
                            <SelectContent>
                              <SelectItem value="characters">Characters</SelectItem>
                              <SelectItem value="tokens">Tokens</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="chunk-size">Chunk Size</Label>
                          <Input
                            id="chunk-size"
                            type="number" min={100} max={8000}
                            value={config.chunkSize}
                            onChange={(e) =>
                              updateConfig('chunkSize', parseInt(e.target.value) || 512)
                            }
                          />
                          <p className="text-xs text-muted-foreground">
                            Target size per chunk (100–8000)
                          </p>
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="chunk-overlap">Overlap</Label>
                          <Input
                            id="chunk-overlap"
                            type="number" min={0} max={(config.chunkSize || 512) / 2}
                            value={config.chunkOverlap}
                            onChange={(e) =>
                              updateConfig('chunkOverlap', parseInt(e.target.value) || 0)
                            }
                          />
                          <p className="text-xs text-muted-foreground">
                            512–1024 characters works well for most documents.
                          </p>
                        </div>
                      </div>
                      <Alert>
                        <Info className="h-4 w-4" />
                        <AlertDescription>
                          Smaller chunks provide more precise retrieval but may increase costs.
                        </AlertDescription>
                      </Alert>
                    </>
                  )}
                </div>

                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Embedding</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Provider</Label>
                      <Select
                        value={config.embeddingProvider}
                        onValueChange={(v) => {
                          updateConfig('embeddingProvider', v)
                          if (v === 'openai') updateConfig('embeddingModel', 'text-embedding-3-small')
                          else if (v === 'voyage') updateConfig('embeddingModel', 'voyage-large-2')
                          else if (v === 'local') updateConfig('embeddingModel', 'nomic-embed-text')
                        }}
                      >
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="openai">OpenAI</SelectItem>
                          <SelectItem value="voyage">Voyage AI</SelectItem>
                          <SelectItem value="local">Local (Ollama)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>Model</Label>
                      <Select
                        value={config.embeddingModel}
                        onValueChange={(v) => updateConfig('embeddingModel', v)}
                      >
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {config.embeddingProvider === 'openai' && (
                            <>
                              <SelectItem value="text-embedding-3-small">text-embedding-3-small (1536)</SelectItem>
                              <SelectItem value="text-embedding-3-large">text-embedding-3-large (3072)</SelectItem>
                              <SelectItem value="text-embedding-ada-002">text-embedding-ada-002 (1536)</SelectItem>
                            </>
                          )}
                          {config.embeddingProvider === 'voyage' && (
                            <>
                              <SelectItem value="voyage-large-2">voyage-large-2 (1536)</SelectItem>
                              <SelectItem value="voyage-code-2">voyage-code-2 (1536)</SelectItem>
                              <SelectItem value="voyage-2">voyage-2 (1024)</SelectItem>
                            </>
                          )}
                          {config.embeddingProvider === 'local' && (
                            <>
                              <SelectItem value="nomic-embed-text">nomic-embed-text (768)</SelectItem>
                              <SelectItem value="mxbai-embed-large">mxbai-embed-large (1024)</SelectItem>
                            </>
                          )}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Step 6: Preview + Submit */}
            {currentStep === 6 && (
              <div className="space-y-6">
                <div className="rounded-lg border bg-muted/30 p-4">
                  <h3 className="font-medium mb-3">Configuration Summary</h3>
                  <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Parser:</span>
                      <span className="font-medium">{selectedFamily?.parser}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Source:</span>
                      <span className="font-medium">{config.sourceRepresentation}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Parsed docs:</span>
                      <span className="font-medium">{selectedParsedDocIds.length}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Strategy:</span>
                      <span className="font-medium">{config.chunkingStrategy}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Chunk size:</span>
                      <span className="font-medium">
                        {config.chunkSize} {config.chunkUnit}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Model:</span>
                      <span className="font-medium">{config.embeddingModel}</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Select document to preview</Label>
                  <Select
                    value={previewDocId ?? ''}
                    onValueChange={(v) => { setPreviewDocId(v); setPreview(null) }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Choose a parsed document..." />
                    </SelectTrigger>
                    <SelectContent>
                      {selectedParsedDocIds.map((id) => (
                        <SelectItem key={id} value={id}>
                          {id.slice(0, 8)}…
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <ChunkPreviewPanel
                  preview={preview}
                  isLoading={isPreviewLoading}
                  onPreview={handlePreview}
                  disabled={!previewDocId}
                />
              </div>
            )}
          </CardContent>

          <CardFooter className="flex justify-between border-t pt-6">
            <div>
              {currentStep > 1 ? (
                <Button variant="outline" onClick={handleBack} disabled={isSubmitting}>
                  <ChevronLeft className="w-4 h-4 mr-2" />Back
                </Button>
              ) : (
                <Button variant="outline" onClick={() => navigate('/index')} disabled={isSubmitting}>
                  Cancel
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={() => handleSubmit(false)}
                disabled={
                  isSubmitting ||
                  !name.trim() ||
                  !selectedFamily ||
                  selectedParsedDocIds.length === 0
                }
              >
                {isSubmitting ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Saving...</>
                ) : (
                  'Save as Draft'
                )}
              </Button>
              {currentStep < STEPS.length ? (
                <Button
                  onClick={handleNext}
                  disabled={!canProceedFromStep(currentStep)}
                >
                  Continue<ChevronRight className="w-4 h-4 ml-2" />
                </Button>
              ) : (
                <Button onClick={() => handleSubmit(true)} disabled={isSubmitting}>
                  {isSubmitting ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Creating...</>
                  ) : (
                    'Create & Build Index'
                  )}
                </Button>
              )}
            </div>
          </CardFooter>
        </Card>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `npx --prefix frontend vitest run src/pages/CreateIndexPage.test.tsx`
Expected: PASS — all 4 tests green

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/CreateIndexPage.tsx frontend/src/pages/CreateIndexPage.test.tsx
git commit -m "feat(indexes): rebuild CreateIndexPage as 6-step wizard with explicit parse-config + parsed-doc picker"
```

---

### Task 5: Delete `IndexCreateDialog` (dead code)

**Files:**
- Delete: `frontend/src/components/indexes/IndexCreateDialog.tsx`
- Delete: `frontend/src/components/indexes/IndexCreateDialog.test.tsx`

`IndexCreateDialog` is not imported by any page or component in the application. It predates the full-page wizard and has no callers.

- [ ] **Step 1: Confirm no callers**

Run:
```bash
grep -rn "IndexCreateDialog" frontend/src --include="*.tsx" --include="*.ts" \
  | grep -v "IndexCreateDialog\."
```
Expected: no output (only definition files, no imports)

- [ ] **Step 2: Delete the files**

```bash
git rm frontend/src/components/indexes/IndexCreateDialog.tsx \
       frontend/src/components/indexes/IndexCreateDialog.test.tsx
```

- [ ] **Step 3: Verify the build still passes**

Run: `npm run --prefix frontend build 2>&1 | grep "error TS" | head -10`
Expected: no TypeScript errors

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(indexes): delete unused IndexCreateDialog (no callers; CreateIndexPage is the canonical wizard)"
```

---

### Task 6: Remove the wide-net resolver bridge

**Files:**
- Modify: `frontend/src/lib/parsed-documents.ts`

- [ ] **Step 1: Confirm no callers of the bridge remain**

Run:
```bash
grep -rn "resolveLatestParsedDocsForDocuments\|ResolvedFamily" \
  frontend/src --include="*.tsx" --include="*.ts"
```
Expected: only the definitions in `lib/parsed-documents.ts`

- [ ] **Step 2: Delete `ResolvedFamily` and `resolveLatestParsedDocsForDocuments` from `lib/parsed-documents.ts`**

Remove everything from the `export interface ResolvedFamily` declaration through the end of `resolveLatestParsedDocsForDocuments` (currently lines ~31–86).

The file should end after `listParsedDocuments` (plus the new `ParseConfigOption` + `listParseConfigs` added in Task 1).

- [ ] **Step 3: Run the full frontend test suite**

Run: `npx --prefix frontend vitest run`
Expected: all tests PASS, no references to the removed symbols

- [ ] **Step 4: Verify TypeScript build**

Run: `npm run --prefix frontend build 2>&1 | grep "error TS" | head -10`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/parsed-documents.ts
git commit -m "chore(indexes): remove wide-net resolver bridge (Unit 4 ships explicit parsed-doc picker)"
```

---

## Self-Review Against Spec

### Spec coverage

| Spec requirement | Covered by |
|---|---|
| Parse-config family selector (Step 2) showing parser name, config summary, markdown badge, count | Task 2 (`ParseConfigFamilySelector`) |
| `full_markdown` greyed out when family lacks markdown | Task 4 Step 3 (`disabled={!selectedFamily?.hasFullMarkdown}`) |
| Empty state when no parse families exist | Task 2 (empty state in selector) |
| Parsed-doc picker defaults to latest-per-source | Task 3 (`latestPerSource` init = `true`) |
| Toggle off reveals all runs per source | Task 3 (toggle → refetch with `latestPerSource: false`) |
| Picker selection feeds `parsedDocumentIds` | Task 4 (`selectedParsedDocIds` → `createIndex` call) |
| Create disabled when no parsed-docs selected | Task 4 (`disabled={... selectedParsedDocIds.length === 0}`) |
| Submit uses new shape (`parsedDocumentIds`, `config.parser`, `config.parseConfigHash`) | Task 4 `handleSubmit` |
| Bridge removed | Task 6 |
| `IndexCreateDialog` dead code cleaned up | Task 5 |

### Missing from this unit (Unit 5 scope)
- Index detail "Documents" tab → "Parsed Documents" with new columns
- "Add Documents" flow on index detail page
