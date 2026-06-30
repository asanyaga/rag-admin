# WS2: Document Viewer Overlay Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `ParsedDocumentPane` with optional label overlay props (block-level and page-level label badges coloured by label), and extend `ParsedDocumentViewer` to accept classification region/block data and derive those overlay maps — wiring the viewer up for classification result display without affecting any existing caller.

**Architecture:** All new props are optional so existing callers (`ParsedDocumentViewer.tsx:280`, `ParseRunDetailPage.tsx:179`) require zero changes. `ParsedDocumentPane` renders label badges inline using inline `style` colour from a `Map<string, string>`. `ParsedDocumentViewer` derives the maps from `regions` and `annotatedBlocks` props using a fixed 8-colour palette cycling by label index, and overrides the auto-selected parse run when `defaultParseRunId` is provided via a `useEffect`.

**Tech Stack:** React 18, TypeScript, Vitest + @testing-library/react, shadcn/ui

## Global Constraints

- All changes are additive optional props — no existing call site changes required
- Run tests: `npm --prefix frontend exec -- npx vitest run <path>`
- Run lint: `npm --prefix frontend run lint`
- No backend changes in this workstream
- `ParsedDocumentPane.test.tsx` existing tests must still pass after changes

---

### Task 1: Extend ParsedDocumentPane with label overlay props

**Files:**
- Modify: `frontend/src/components/parse-runs/ParsedDocumentPane.tsx`
- Modify: `frontend/src/components/parse-runs/ParsedDocumentPane.test.tsx`

**Interfaces:**
- Consumes: nothing new — all inputs are new optional props
- Produces (for Task 2 to pass down):
  ```typescript
  blockLabels?: Map<string, string>   // blockId → label name
  pageLabels?: Map<number, string>    // page index (0-based) → label name
  labelColors?: Map<string, string>   // label name → CSS color string e.g. 'hsl(221 83% 53%)'
  ```

- [ ] **Step 1: Add new tests to ParsedDocumentPane.test.tsx**

Append the following `describe` block to the end of `frontend/src/components/parse-runs/ParsedDocumentPane.test.tsx` (after the closing `}` of the existing `describe`):

```typescript
describe('ParsedDocumentPane — label overlays', () => {
  const makeDocWithBlock = (): ParsedDocumentDetail => ({
    parseRunId: 'run-1',
    sourceDocumentId: 'src-1',
    pageCount: 1,
    blockCount: 1,
    fullText: 'hello',
    fullMarkdown: '# Hello',
    content: {
      pages: [{ index: 0 }],
      blocks: [{ id: 'b1', page_index: 0, role: 'paragraph', text: 'Block one' }],
    },
  })

  it('renders a label badge on a block row when blockLabels contains its id', () => {
    const blockLabels = new Map([['b1', 'income_statement']])
    const labelColors = new Map([['income_statement', 'hsl(221 83% 53%)']])
    render(
      <ParsedDocumentPane
        parsedDocument={makeDocWithBlock()}
        blockLabels={blockLabels}
        labelColors={labelColors}
      />,
    )
    expect(screen.getByText('income_statement')).toBeInTheDocument()
  })

  it('renders a label badge on the page header when pageLabels contains the page index', () => {
    const pageLabels = new Map([[0, 'balance_sheet']])
    const labelColors = new Map([['balance_sheet', 'hsl(142 71% 45%)']])
    render(
      <ParsedDocumentPane
        parsedDocument={makeDocWithBlock()}
        pageLabels={pageLabels}
        labelColors={labelColors}
      />,
    )
    expect(screen.getAllByText('balance_sheet').length).toBeGreaterThan(0)
  })

  it('renders nothing extra when overlay props are omitted (backward compat)', () => {
    render(<ParsedDocumentPane parsedDocument={makeDocWithBlock()} />)
    // No label badges — only the existing role badge
    expect(screen.queryByText('income_statement')).not.toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```
npm --prefix frontend exec -- npx vitest run src/components/parse-runs/ParsedDocumentPane.test.tsx
```

Expected: the 3 new overlay tests fail; the 4 existing tests still pass.

- [ ] **Step 3: Update ParsedDocumentPane.tsx**

Replace the entire contents of `frontend/src/components/parse-runs/ParsedDocumentPane.tsx` with the following. The only structural changes are: (a) three new optional props on `ParsedDocumentPaneProps`, (b) `blockLabels`/`labelColors` passed into `BlockRow`, (c) a label span added to each page header, (d) `BlockRow` receives and renders the label. All existing logic is preserved verbatim.

```typescript
import { useEffect, useMemo, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { Badge } from '@/components/ui/badge'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import type { Block, ParsedDocumentDetail } from '@/types/cdm'

export interface ParsedDocumentPaneProps {
  parsedDocument: ParsedDocumentDetail | undefined
  isLoading?: boolean
  error?: string | null
  selectedBlockId?: string | null
  onBlockSelect?: (id: string) => void
  /** blockId → label name — renders a coloured badge on matching block rows */
  blockLabels?: Map<string, string>
  /** page index (0-based) → label name — renders a coloured badge on matching page headers */
  pageLabels?: Map<number, string>
  /** label name → CSS colour string e.g. 'hsl(221 83% 53%)' */
  labelColors?: Map<string, string>
}

function BlockRow({
  block,
  isSelected,
  onBlockSelect,
  label,
  labelColor,
}: {
  block: Block
  isSelected: boolean
  onBlockSelect?: (id: string) => void
  label?: string
  labelColor?: string
}) {
  const [localOpen, setLocalOpen] = useState(false)
  const confidence = block.quality?.confidence

  useEffect(() => {
    if (isSelected) setLocalOpen(true)
  }, [isSelected])

  const preview = (block.text ?? block.markdown ?? '').slice(0, 140)

  return (
    <Collapsible
      open={localOpen}
      onOpenChange={(open) => {
        setLocalOpen(open)
        if (open && onBlockSelect) onBlockSelect(block.id)
      }}
    >
      <CollapsibleTrigger asChild>
        <button
          data-block-id={block.id}
          className={`w-full text-left border rounded-md px-2 py-1 hover:bg-muted/50 ${
            isSelected ? 'border-primary ring-1 ring-primary' : ''
          }`}
        >
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="text-xs">
              {block.role}
            </Badge>
            {label && (
              <span
                className="text-xs px-1.5 py-0.5 rounded font-medium text-white shrink-0"
                style={{ backgroundColor: labelColor }}
              >
                {label}
              </span>
            )}
            {typeof confidence === 'number' && (
              <Badge variant="outline" className="text-xs">
                {confidence.toFixed(2)}
              </Badge>
            )}
            <span className="text-xs text-muted-foreground truncate flex-1">
              {preview || <em>empty</em>}
            </span>
          </div>
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="border border-t-0 rounded-b-md px-3 py-2 space-y-2 -mt-px">
        {block.markdown ? (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <Markdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
              {block.markdown}
            </Markdown>
          </div>
        ) : block.text ? (
          <pre className="whitespace-pre-wrap font-mono text-xs">{block.text}</pre>
        ) : (
          <p className="text-xs text-muted-foreground">No text/markdown.</p>
        )}
        <div className="text-xs text-muted-foreground space-y-0.5">
          {block.native_type && <div>native_type: {block.native_type}</div>}
          {block.bbox && (
            <div>
              bbox: ({block.bbox.x0.toFixed(3)}, {block.bbox.y0.toFixed(3)}) →
              ({block.bbox.x1.toFixed(3)}, {block.bbox.y1.toFixed(3)})
            </div>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

export function PageBlockList({
  blocks,
  selectedBlockId,
  onBlockSelect,
  blockLabels,
  labelColors,
}: {
  blocks: Block[]
  selectedBlockId?: string | null
  onBlockSelect?: (id: string) => void
  blockLabels?: Map<string, string>
  labelColors?: Map<string, string>
}) {
  if (blocks.length === 0) {
    return <p className="text-xs text-muted-foreground">No blocks on this page.</p>
  }
  return (
    <div className="space-y-2">
      {blocks.map((b) => {
        const label = blockLabels?.get(b.id)
        const labelColor = label ? labelColors?.get(label) : undefined
        return (
          <BlockRow
            key={b.id}
            block={b}
            isSelected={selectedBlockId === b.id}
            onBlockSelect={onBlockSelect}
            label={label}
            labelColor={labelColor}
          />
        )
      })}
    </div>
  )
}

export function ParsedDocumentPane({
  parsedDocument,
  isLoading = false,
  error = null,
  selectedBlockId,
  onBlockSelect,
  blockLabels,
  pageLabels,
  labelColors,
}: ParsedDocumentPaneProps) {
  const blocksByPage = useMemo<Map<number, Block[]>>(() => {
    const map = new Map<number, Block[]>()
    const blocks = parsedDocument?.content?.blocks ?? []
    for (const b of blocks) {
      const arr = map.get(b.page_index) ?? []
      arr.push(b)
      map.set(b.page_index, arr)
    }
    return map
  }, [parsedDocument])

  useEffect(() => {
    if (!selectedBlockId) return
    const el = document.querySelector(`[data-block-id="${selectedBlockId}"]`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [selectedBlockId])

  if (isLoading) {
    return <div className="p-4 text-sm text-muted-foreground">Loading…</div>
  }
  if (error) {
    return <div className="p-4 text-sm text-destructive">{error}</div>
  }
  if (!parsedDocument) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        No adapted document for this run.
      </div>
    )
  }

  const pages = parsedDocument.content?.pages ?? []
  if (pages.length === 0) {
    return <div className="p-4 text-sm text-muted-foreground">No pages.</div>
  }

  return (
    <div className="space-y-3 p-3">
      {pages.map((p) => {
        const pageBlocks = blocksByPage.get(p.index) ?? []
        const confidence = p.quality?.confidence
        const pageLabel = pageLabels?.get(p.index)
        const pageLabelColor = pageLabel ? labelColors?.get(pageLabel) : undefined

        return (
          <Collapsible key={p.index} defaultOpen>
            <CollapsibleTrigger asChild>
              <button className="w-full text-left border rounded-md px-3 py-2 hover:bg-muted/50">
                <div className="flex items-center gap-3 text-sm">
                  <span className="font-medium">Page {p.index + 1}</span>
                  <span className="text-muted-foreground text-xs">
                    {pageBlocks.length} block{pageBlocks.length === 1 ? '' : 's'}
                  </span>
                  {pageLabel && (
                    <span
                      className="text-xs px-1.5 py-0.5 rounded font-medium text-white shrink-0"
                      style={{ backgroundColor: pageLabelColor }}
                    >
                      {pageLabel}
                    </span>
                  )}
                  {typeof confidence === 'number' && (
                    <Badge variant="outline" className="text-xs ml-auto">
                      confidence {confidence.toFixed(2)}
                    </Badge>
                  )}
                </div>
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent className="border border-t-0 rounded-b-md p-3 -mt-px">
              <PageBlockList
                blocks={pageBlocks}
                selectedBlockId={selectedBlockId}
                onBlockSelect={onBlockSelect}
                blockLabels={blockLabels}
                labelColors={labelColors}
              />
            </CollapsibleContent>
          </Collapsible>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 4: Run all ParsedDocumentPane tests**

```
npm --prefix frontend exec -- npx vitest run src/components/parse-runs/ParsedDocumentPane.test.tsx
```

Expected: all 7 tests pass (4 original + 3 new overlay tests).

- [ ] **Step 5: Commit**

```
git add frontend/src/components/parse-runs/ParsedDocumentPane.tsx frontend/src/components/parse-runs/ParsedDocumentPane.test.tsx
git commit -m "feat(viewer): add label overlay props to ParsedDocumentPane"
```

---

### Task 2: Extend ParsedDocumentViewer with region overlay wiring

**Files:**
- Modify: `frontend/src/components/documents/ParsedDocumentViewer.tsx`

**Interfaces:**
- Consumes: `ClassificationRegion` from `@/types/classification`, `AnnotatedBlock` from `@/types/classification`, `ParsedDocumentPaneProps` with new overlay props from Task 1
- Produces (for WS3 to use):
  ```typescript
  // New optional props on ParsedDocumentViewer:
  defaultParseRunId?: string       // pre-selects a specific parse run on load
  regions?: ClassificationRegion[] // used to derive pageLabels
  annotatedBlocks?: AnnotatedBlock[] // used to derive blockLabels
  ```

**Note on `pageStart`/`pageEnd` indexing:** `ClassificationRegion.pageStart` and `pageEnd` match the same 0-based indexing used by `ParsedDocumentPane`'s `p.index`. Verify this against the backend `ClassifiedRegion` model if there is any doubt — a page-off-by-one will make overlays appear on the wrong pages.

- [ ] **Step 1: Add new props and overlay derivation to ParsedDocumentViewer.tsx**

The diff is three additions to the existing file:
1. Import `ClassificationRegion` and `AnnotatedBlock` types
2. Add three new optional props to `ParsedDocumentViewerProps`
3. Add a `useEffect` for `defaultParseRunId` override and `useMemo` for the overlay maps
4. Pass the derived maps to `ParsedDocumentPane` in the Pages tab

Open `frontend/src/components/documents/ParsedDocumentViewer.tsx`.

**Add to the imports at the top** (after the existing imports):

```typescript
import { useEffect, useMemo } from 'react'
import type { ClassificationRegion, AnnotatedBlock } from '@/types/classification'
```

Note: `useState` is already imported. Only add `useEffect` and `useMemo` if not already present in the existing import from `'react'`. Merge with the existing `import { useState } from 'react'` line.

**Replace the `ParsedDocumentViewerProps` interface** (currently just `{ documentId: string }`) with:

```typescript
interface ParsedDocumentViewerProps {
  documentId: string
  defaultParseRunId?: string
  regions?: ClassificationRegion[]
  annotatedBlocks?: AnnotatedBlock[]
}
```

**Inside `ParsedDocumentViewer`**, add this `useEffect` immediately after the `useParseRuns` destructure (after line `const { parseRuns, selectedRun, parsedDocument, isLoading, isLoadingContent, error, selectRun } = useParseRuns(documentId)`):

```typescript
// Pre-select the parse run used by a classification run when provided
useEffect(() => {
  if (!defaultParseRunId || parseRuns.length === 0) return
  const match = parseRuns.find((r) => r.id === defaultParseRunId)
  if (match) selectRun(defaultParseRunId)
}, [defaultParseRunId, parseRuns, selectRun])
```

**Add the label color palette at module level** (outside the component, before `export function ParsedDocumentViewer`):

```typescript
const LABEL_COLORS = [
  'hsl(221 83% 53%)',
  'hsl(142 71% 45%)',
  'hsl(32 95% 44%)',
  'hsl(346 77% 49%)',
  'hsl(262 80% 58%)',
  'hsl(199 89% 48%)',
  'hsl(25 95% 53%)',
  'hsl(316 70% 50%)',
]
```

**Add the overlay map derivation** inside the component body after the `useEffect` above:

```typescript
const labelColors = useMemo<Map<string, string>>(() => {
  const labels = regions?.map((r) => r.label) ?? []
  const unique = [...new Set(labels)]
  return new Map(unique.map((l, i) => [l, LABEL_COLORS[i % LABEL_COLORS.length]]))
}, [regions])

const blockLabels = useMemo<Map<string, string>>(() => {
  if (!annotatedBlocks) return new Map()
  const map = new Map<string, string>()
  for (const b of annotatedBlocks) {
    if (b.label) map.set(b.blockId, b.label)
  }
  return map
}, [annotatedBlocks])

const pageLabels = useMemo<Map<number, string>>(() => {
  if (!regions) return new Map()
  const map = new Map<number, string>()
  for (const r of regions) {
    for (let p = r.pageStart; p <= r.pageEnd; p++) {
      if (!map.has(p)) map.set(p, r.label)
    }
  }
  return map
}, [regions])
```

**Update the `<ParsedDocumentPane />` call** in the Pages `TabsContent` (currently `<ParsedDocumentPane parsedDocument={parsedDocument} />`). Replace it with:

```typescript
<ParsedDocumentPane
  parsedDocument={parsedDocument}
  blockLabels={blockLabels.size > 0 ? blockLabels : undefined}
  pageLabels={pageLabels.size > 0 ? pageLabels : undefined}
  labelColors={labelColors.size > 0 ? labelColors : undefined}
/>
```

- [ ] **Step 2: Verify TypeScript compiles**

```
npm --prefix frontend run build 2>&1 | head -50
```

Expected: no TypeScript errors.

- [ ] **Step 3: Run lint**

```
npm --prefix frontend run lint
```

Expected: no lint errors.

- [ ] **Step 4: Run existing tests**

```
npm --prefix frontend exec -- npx vitest run src/components/parse-runs/ParsedDocumentPane.test.tsx
```

Expected: all 7 tests still pass.

- [ ] **Step 5: Commit**

```
git add frontend/src/components/documents/ParsedDocumentViewer.tsx
git commit -m "feat(viewer): add classification region overlay wiring to ParsedDocumentViewer"
```

---

## Manual Verification (Human + Browser)

Start the dev server if not already running:
```
npm --prefix frontend run dev
```

**Regression check — existing pages must be unchanged:**

1. Navigate to any document that has a completed parse run (e.g. via **Parse** in the sidebar).
2. Open the document's parse run viewer. Verify:
   - Pages render with their blocks.
   - Block rows show the role badge and text preview as before.
   - Page headers show "Page N" and block count as before.
   - **No label badges appear** (since no overlay data is passed by existing callers).
3. Navigate to **Parse → [any run] → Pages tab** — same check.

**Visual smoke-test of overlays (optional but recommended):**

4. Open the browser DevTools console on any page that renders `ParsedDocumentViewer`.
5. This test cannot be done in the UI until WS3 wires real data — verify instead by inspecting the compiled JS or by temporarily editing `ParsedDocumentViewer.tsx` to pass hardcoded test data:

```typescript
// TEMPORARY — revert after testing
const blockLabels = new Map([['b1', 'income_statement']])
const pageLabels = new Map([[0, 'income_statement']])
const labelColors = new Map([['income_statement', 'hsl(221 83% 53%)']])
```

Then confirm the label badge renders in the Pages tab. Revert the temporary change before committing.
