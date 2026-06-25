# Document Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `ParseRunDetailPage` into a full parse-run audit workspace — react-pdf rendering with CDM bbox overlays on the left, all inspection tabs (Pages, Markdown, Text, JSON, Raw Payload, Metrics) on the right, with click-through block selection between the two panels.

**Architecture:** No new route or backend changes. `ParseRunDetailPage` (at `/documents/:documentId/runs/:runId`) is restructured: left panel becomes `DocumentPdfViewer` (new component), right panel becomes a `Tabs` container holding content that was previously split between the drawer and the page. A shared `selectedBlockId` state at the page level wires click-through between the PDF overlay and the block list.

**Tech Stack:** React 18, TypeScript, react-pdf (new), Vite, shadcn/ui, Tailwind CSS, Vitest + Testing Library

## Global Constraints

- Frontend only — no backend changes
- All new components go in `frontend/src/components/parse-runs/`
- Follow existing test pattern: `describe` + `it`, `render` + `screen`, `userEvent` for interactions
- Use `import type` for type-only imports
- No new shadcn components beyond what's already installed
- Run `npm run lint` and `npm run build` (in `frontend/`) after every task to catch errors early
- Commit after every task

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `frontend/src/components/parse-runs/DocumentPdfViewer.tsx` | **Create** | PDF rendering + SVG bbox overlays + click-through |
| `frontend/src/components/parse-runs/DocumentPdfViewer.test.tsx` | **Create** | Tests for DocumentPdfViewer |
| `frontend/src/components/parse-runs/ParsedDocumentPane.tsx` | **Modify** | Add `selectedBlockId` + `onBlockSelect` click-through props |
| `frontend/src/components/parse-runs/ParsedDocumentPane.test.tsx` | **Create** | Tests for ParsedDocumentPane click-through |
| `frontend/src/components/documents/ParsedDocumentViewer.tsx` | **Modify** | Export `MetricsTab` so `ParseRunDetailPage` can use it |
| `frontend/src/pages/ParseRunDetailPage.tsx` | **Modify** | Restructure layout — PDF viewer left, tabs right |

---

## Task 1: Install react-pdf

**Files:**
- Modify: `frontend/package.json` (via npm install)

**Interfaces:**
- Produces: `react-pdf` available as `import { Document, Page, pdfjs } from 'react-pdf'`

- [ ] **Step 1: Install the package**

```bash
npm --prefix frontend install react-pdf
```

Expected output: react-pdf and pdfjs-dist added to `frontend/package.json` dependencies.

- [ ] **Step 2: Verify the build still passes**

```bash
npm --prefix frontend run build
```

Expected: exits 0, no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "feat(viewer): install react-pdf"
```

---

## Task 2: Export MetricsTab from ParsedDocumentViewer

`MetricsTab` is a private function inside `ParsedDocumentViewer.tsx`. `ParseRunDetailPage` needs it for the Metrics tab. The change is a single keyword addition.

**Files:**
- Modify: `frontend/src/components/documents/ParsedDocumentViewer.tsx`

**Interfaces:**
- Produces: `export function MetricsTab({ run }: { run: ParseRunListItem }): JSX.Element`

- [ ] **Step 1: Export MetricsTab**

In `frontend/src/components/documents/ParsedDocumentViewer.tsx`, find line ~112:

```tsx
function MetricsTab({ run }: { run: ParseRunListItem }) {
```

Change it to:

```tsx
export function MetricsTab({ run }: { run: ParseRunListItem }) {
```

No other changes to this file.

- [ ] **Step 2: Verify lint and build**

```bash
npm --prefix frontend run lint
npm --prefix frontend run build
```

Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/documents/ParsedDocumentViewer.tsx
git commit -m "feat(viewer): export MetricsTab for reuse in ParseRunDetailPage"
```

---

## Task 3: Add click-through props to ParsedDocumentPane

Add `selectedBlockId` and `onBlockSelect` as optional props. When `selectedBlockId` matches a block, that block's `Collapsible` opens and scrolls into view. Clicking a block fires `onBlockSelect`. All existing callers are unaffected (props are optional).

**Files:**
- Modify: `frontend/src/components/parse-runs/ParsedDocumentPane.tsx`
- Create: `frontend/src/components/parse-runs/ParsedDocumentPane.test.tsx`

**Interfaces:**
- Consumes: `Block`, `ParsedDocumentDetail` from `@/types/cdm`
- Produces:
  - `ParsedDocumentPaneProps` extended with `selectedBlockId?: string | null` and `onBlockSelect?: (id: string) => void`
  - `PageBlockListProps` extended with the same two optional props

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/parse-runs/ParsedDocumentPane.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ParsedDocumentPane } from './ParsedDocumentPane'
import type { ParsedDocumentDetail } from '@/types/cdm'

const makeDoc = (overrides = {}): ParsedDocumentDetail => ({
  parseRunId: 'run-1',
  sourceDocumentId: 'src-1',
  pageCount: 1,
  blockCount: 2,
  fullText: 'hello world',
  fullMarkdown: '# Hello',
  content: {
    pages: [{ index: 0 }],
    blocks: [
      { id: 'b1', page_index: 0, role: 'paragraph', text: 'Block one' },
      { id: 'b2', page_index: 0, role: 'table', text: 'Block two' },
    ],
  },
  ...overrides,
})

describe('ParsedDocumentPane', () => {
  it('renders block roles', () => {
    render(<ParsedDocumentPane parsedDocument={makeDoc()} />)
    expect(screen.getAllByText('paragraph').length).toBeGreaterThan(0)
    expect(screen.getAllByText('table').length).toBeGreaterThan(0)
  })

  it('expands the selected block when selectedBlockId is provided', async () => {
    render(
      <ParsedDocumentPane
        parsedDocument={makeDoc()}
        selectedBlockId="b1"
      />
    )
    // Collapsible content for b1 should be visible
    expect(screen.getByText('Block one')).toBeInTheDocument()
  })

  it('calls onBlockSelect with block id when a block row is clicked', async () => {
    const onBlockSelect = vi.fn()
    render(
      <ParsedDocumentPane
        parsedDocument={makeDoc()}
        onBlockSelect={onBlockSelect}
      />
    )
    // Click the first block trigger (role badge is inside the trigger button)
    const triggers = screen.getAllByRole('button')
    await userEvent.click(triggers[0])
    expect(onBlockSelect).toHaveBeenCalledWith('b1')
  })

  it('renders loading state', () => {
    render(<ParsedDocumentPane parsedDocument={undefined} isLoading />)
    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npm --prefix frontend exec -- npx vitest run src/components/parse-runs/ParsedDocumentPane.test.tsx
```

Expected: `FAIL` — `onBlockSelect` tests fail because the prop doesn't exist yet.

- [ ] **Step 3: Rewrite ParsedDocumentPane.tsx with click-through support**

Replace `frontend/src/components/parse-runs/ParsedDocumentPane.tsx` entirely:

```tsx
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
}

function BlockRow({
  block,
  isSelected,
  onBlockSelect,
}: {
  block: Block
  isSelected: boolean
  onBlockSelect?: (id: string) => void
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
}: {
  blocks: Block[]
  selectedBlockId?: string | null
  onBlockSelect?: (id: string) => void
}) {
  if (blocks.length === 0) {
    return <p className="text-xs text-muted-foreground">No blocks on this page.</p>
  }
  return (
    <div className="space-y-2">
      {blocks.map((b) => (
        <BlockRow
          key={b.id}
          block={b}
          isSelected={selectedBlockId === b.id}
          onBlockSelect={onBlockSelect}
        />
      ))}
    </div>
  )
}

export function ParsedDocumentPane({
  parsedDocument,
  isLoading = false,
  error = null,
  selectedBlockId,
  onBlockSelect,
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
        return (
          <Collapsible key={p.index} defaultOpen>
            <CollapsibleTrigger asChild>
              <button className="w-full text-left border rounded-md px-3 py-2 hover:bg-muted/50">
                <div className="flex items-center gap-3 text-sm">
                  <span className="font-medium">Page {p.index + 1}</span>
                  <span className="text-muted-foreground text-xs">
                    {pageBlocks.length} block{pageBlocks.length === 1 ? '' : 's'}
                  </span>
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
              />
            </CollapsibleContent>
          </Collapsible>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
npm --prefix frontend exec -- npx vitest run src/components/parse-runs/ParsedDocumentPane.test.tsx
```

Expected: all tests pass.

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
npm --prefix frontend exec -- npx vitest run
```

Expected: all existing tests pass.

- [ ] **Step 6: Lint and build**

```bash
npm --prefix frontend run lint
npm --prefix frontend run build
```

Expected: exits 0.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/parse-runs/ParsedDocumentPane.tsx \
        frontend/src/components/parse-runs/ParsedDocumentPane.test.tsx
git commit -m "feat(viewer): add selectedBlockId click-through to ParsedDocumentPane"
```

---

## Task 4: Build DocumentPdfViewer

New component that fetches the document's PDF via the existing `GET /api/v1/documents/{id}/file` endpoint, renders each page with react-pdf, and overlays an SVG with colored bbox rectangles for each CDM block. Clicking a rect fires `onBlockSelect`. When `selectedBlockId` changes from outside, the viewer scrolls to that block's page.

**Files:**
- Create: `frontend/src/components/parse-runs/DocumentPdfViewer.tsx`
- Create: `frontend/src/components/parse-runs/DocumentPdfViewer.test.tsx`

**Interfaces:**
- Consumes:
  - `getAccessToken` from `@/api/client`
  - `Block` from `@/types/cdm`
  - `Document`, `Page`, `pdfjs` from `react-pdf`
- Produces:
  ```ts
  interface DocumentPdfViewerProps {
    documentId: string
    blocks: Block[]
    selectedBlockId: string | null
    onBlockSelect: (blockId: string) => void
  }
  export function DocumentPdfViewer(props: DocumentPdfViewerProps): JSX.Element
  ```

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/parse-runs/DocumentPdfViewer.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock react-pdf before importing the component
vi.mock('react-pdf', () => ({
  Document: ({ children, onLoadSuccess }: {
    children: React.ReactNode
    onLoadSuccess?: (pdf: { numPages: number }) => void
  }) => {
    onLoadSuccess?.({ numPages: 1 })
    return <div data-testid="pdf-document">{children}</div>
  },
  Page: ({ pageNumber, onRenderSuccess }: {
    pageNumber: number
    onRenderSuccess?: () => void
  }) => {
    onRenderSuccess?.()
    return <div data-testid={`pdf-page-${pageNumber}`} />
  },
  pdfjs: { GlobalWorkerOptions: { workerSrc: '' } },
}))

vi.mock('@/api/client', () => ({
  getAccessToken: () => 'test-token',
}))

import { DocumentPdfViewer } from './DocumentPdfViewer'
import type { Block } from '@/types/cdm'

const makeBlock = (id: string, role: string, overrides = {}): Block => ({
  id,
  page_index: 0,
  role,
  text: `${role} content`,
  bbox: { x0: 0.1, y0: 0.1, x1: 0.5, y1: 0.2 },
  ...overrides,
})

describe('DocumentPdfViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders a bbox rect for each block with a bbox', () => {
    const blocks = [
      makeBlock('b1', 'paragraph'),
      makeBlock('b2', 'table'),
    ]
    render(
      <DocumentPdfViewer
        documentId="doc-1"
        blocks={blocks}
        selectedBlockId={null}
        onBlockSelect={vi.fn()}
      />
    )
    expect(screen.getByTestId('bbox-rect-b1')).toBeInTheDocument()
    expect(screen.getByTestId('bbox-rect-b2')).toBeInTheDocument()
  })

  it('does not render a rect for blocks without a bbox', () => {
    const blocks = [makeBlock('b1', 'paragraph', { bbox: null })]
    render(
      <DocumentPdfViewer
        documentId="doc-1"
        blocks={blocks}
        selectedBlockId={null}
        onBlockSelect={vi.fn()}
      />
    )
    expect(screen.queryByTestId('bbox-rect-b1')).not.toBeInTheDocument()
  })

  it('calls onBlockSelect with the block id when a rect is clicked', async () => {
    const onBlockSelect = vi.fn()
    const blocks = [makeBlock('b1', 'heading')]
    render(
      <DocumentPdfViewer
        documentId="doc-1"
        blocks={blocks}
        selectedBlockId={null}
        onBlockSelect={onBlockSelect}
      />
    )
    await userEvent.click(screen.getByTestId('bbox-rect-b1'))
    expect(onBlockSelect).toHaveBeenCalledWith('b1')
  })

  it('applies selected styling to the matching rect', () => {
    const blocks = [makeBlock('b1', 'paragraph')]
    render(
      <DocumentPdfViewer
        documentId="doc-1"
        blocks={blocks}
        selectedBlockId="b1"
        onBlockSelect={vi.fn()}
      />
    )
    const rect = screen.getByTestId('bbox-rect-b1')
    // Selected block has higher fillOpacity
    expect(rect).toHaveAttribute('fill-opacity', '0.5')
  })

  it('renders the pdf document container', () => {
    render(
      <DocumentPdfViewer
        documentId="doc-1"
        blocks={[]}
        selectedBlockId={null}
        onBlockSelect={vi.fn()}
      />
    )
    expect(screen.getByTestId('pdf-document')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
npm --prefix frontend exec -- npx vitest run src/components/parse-runs/DocumentPdfViewer.test.tsx
```

Expected: `FAIL` — `DocumentPdfViewer` does not exist yet.

- [ ] **Step 3: Create DocumentPdfViewer.tsx**

Create `frontend/src/components/parse-runs/DocumentPdfViewer.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { getAccessToken } from '@/api/client'
import type { Block } from '@/types/cdm'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

const ROLE_COLOR: Record<string, string> = {
  title: 'rgb(59,130,246)',
  heading: 'rgb(99,102,241)',
  paragraph: 'rgb(107,114,128)',
  list: 'rgb(245,158,11)',
  table: 'rgb(16,185,129)',
  figure: 'rgb(139,92,246)',
  caption: 'rgb(249,115,22)',
  header: 'rgb(148,163,184)',
  footer: 'rgb(148,163,184)',
  code: 'rgb(6,182,212)',
  formula: 'rgb(236,72,153)',
  other: 'rgb(107,114,128)',
}
const DEFAULT_COLOR = 'rgb(107,114,128)'

interface DocumentPdfViewerProps {
  documentId: string
  blocks: Block[]
  selectedBlockId: string | null
  onBlockSelect: (blockId: string) => void
}

export function DocumentPdfViewer({
  documentId,
  blocks,
  selectedBlockId,
  onBlockSelect,
}: DocumentPdfViewerProps) {
  const [numPages, setNumPages] = useState<number>(0)
  const [loadError, setLoadError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Memoized so react-pdf doesn't re-fetch the PDF on every render
  const pdfFile = useMemo(
    () => ({
      url: `${API_BASE_URL}/documents/${documentId}/file`,
      httpHeaders: (() => {
        const token = getAccessToken()
        return token ? { Authorization: `Bearer ${token}` } : {}
      })(),
    }),
    [documentId],
  )

  // Scroll to the page containing selectedBlockId when it changes from outside
  useEffect(() => {
    if (!selectedBlockId) return
    const block = blocks.find((b) => b.id === selectedBlockId)
    if (!block) return
    const el = containerRef.current?.querySelector(
      `[data-page-index="${block.page_index}"]`,
    )
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [selectedBlockId, blocks])

  if (loadError) {
    return (
      <div className="p-4 text-sm text-destructive">
        Failed to load PDF: {loadError}
      </div>
    )
  }

  return (
    <div ref={containerRef} className="overflow-auto bg-muted/20 p-4">
      <Document
        file={pdfFile}
        onLoadSuccess={({ numPages: n }) => setNumPages(n)}
        onLoadError={(err) => setLoadError(err.message)}
        loading={
          <div className="p-4 text-sm text-muted-foreground">Loading PDF…</div>
        }
      >
        {Array.from({ length: numPages }, (_, i) => {
          const pageBlocks = blocks.filter(
            (b) => b.page_index === i && b.bbox != null,
          )
          return (
            <div
              key={i}
              data-page-index={i}
              className="relative mb-4 shadow-sm"
            >
              <Page
                pageNumber={i + 1}
                width={600}
                renderAnnotationLayer={false}
                renderTextLayer={false}
              />
              {/* SVG overlay — viewBox matches normalized 0-1 bbox space */}
              <svg
                className="absolute inset-0 w-full h-full"
                viewBox="0 0 1 1"
                preserveAspectRatio="none"
                style={{ pointerEvents: 'none' }}
              >
                {pageBlocks.map((b) => {
                  const bbox = b.bbox!
                  const isSelected = b.id === selectedBlockId
                  const color = ROLE_COLOR[b.role] ?? DEFAULT_COLOR
                  return (
                    <rect
                      key={b.id}
                      data-testid={`bbox-rect-${b.id}`}
                      x={bbox.x0}
                      y={bbox.y0}
                      width={bbox.x1 - bbox.x0}
                      height={bbox.y1 - bbox.y0}
                      fill={color}
                      fillOpacity={isSelected ? 0.5 : 0.2}
                      stroke={color}
                      strokeOpacity={isSelected ? 1 : 0}
                      strokeWidth={2}
                      vectorEffect="non-scaling-stroke"
                      style={{ pointerEvents: 'auto', cursor: 'pointer' }}
                      onClick={() => onBlockSelect(b.id)}
                    />
                  )
                })}
              </svg>
            </div>
          )
        })}
      </Document>
    </div>
  )
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
npm --prefix frontend exec -- npx vitest run src/components/parse-runs/DocumentPdfViewer.test.tsx
```

Expected: all tests pass.

- [ ] **Step 5: Run full test suite**

```bash
npm --prefix frontend exec -- npx vitest run
```

Expected: all tests pass.

- [ ] **Step 6: Lint and build**

```bash
npm --prefix frontend run lint
npm --prefix frontend run build
```

Expected: exits 0.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/parse-runs/DocumentPdfViewer.tsx \
        frontend/src/components/parse-runs/DocumentPdfViewer.test.tsx
git commit -m "feat(viewer): add DocumentPdfViewer with react-pdf and CDM bbox overlays"
```

---

## Task 5: Restructure ParseRunDetailPage

Replace the current two-panel layout (Raw Payload | CDM Blocks) with the new layout: `DocumentPdfViewer` on the left, a six-tab panel on the right. Add `selectedBlockId` and `activeTab` state. Wire click-through: clicking a bbox switches to the Pages tab and highlights the block; clicking a block in the Pages tab highlights its bbox on the PDF.

**Files:**
- Modify: `frontend/src/pages/ParseRunDetailPage.tsx`

**Interfaces:**
- Consumes:
  - `DocumentPdfViewer` from `@/components/parse-runs/DocumentPdfViewer`
  - `ParsedDocumentPane` from `@/components/parse-runs/ParsedDocumentPane`
  - `RawPayloadViewer` from `@/components/parse-runs/RawPayloadViewer`
  - `RunHeader` from `@/components/parse-runs/RunHeader`
  - `MetricsTab` from `@/components/documents/ParsedDocumentViewer`
  - `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent` from `@/components/ui/tabs`
  - `Markdown` from `react-markdown`, `remarkGfm` from `remark-gfm`, `rehypeRaw` from `rehype-raw`
  - `useParseRunDetail`, `useParseRunRawPayload` hooks (unchanged)
  - `parseRunsApi.getParsedDocument` (unchanged)

- [ ] **Step 1: Replace ParseRunDetailPage.tsx**

Replace `frontend/src/pages/ParseRunDetailPage.tsx` entirely:

```tsx
import { useState, useCallback, useEffect } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ChevronLeft } from 'lucide-react'
import { RunHeader } from '@/components/parse-runs/RunHeader'
import { RawPayloadViewer } from '@/components/parse-runs/RawPayloadViewer'
import { ParsedDocumentPane } from '@/components/parse-runs/ParsedDocumentPane'
import { DocumentPdfViewer } from '@/components/parse-runs/DocumentPdfViewer'
import { ReParseDialog } from '@/components/documents/ReParseDialog'
import { MetricsTab } from '@/components/documents/ParsedDocumentViewer'
import { useParseRunDetail } from '@/hooks/useParseRunDetail'
import { useParseRunRawPayload } from '@/hooks/useParseRunRawPayload'
import * as parseRunsApi from '@/api/parseRuns'
import type { ParsedDocumentDetail } from '@/types/cdm'
import type { ParseConfig } from '@/types/parsing'

export function ParseRunDetailPage() {
  const { documentId, runId } = useParams<{
    documentId: string
    runId: string
  }>()
  const navigate = useNavigate()
  const [reparseOpen, setReparseOpen] = useState(false)
  const [selectedBlockId, setSelectedBlockId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('pages')

  const { run, isLoading: runLoading, error: runError } = useParseRunDetail(
    runId ?? null,
  )
  const {
    rawPayload,
    isLoading: rawLoading,
    error: rawError,
  } = useParseRunRawPayload(runId ?? null)

  const [parsedDoc, setParsedDoc] = useState<ParsedDocumentDetail | undefined>(
    undefined,
  )
  const [parsedLoading, setParsedLoading] = useState(false)
  const [parsedError, setParsedError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    if (!runId || !run) {
      setParsedDoc(undefined)
      return
    }
    if (
      run.status === 'failed' ||
      run.status === 'pending' ||
      run.status === 'running'
    ) {
      setParsedDoc(undefined)
      return
    }
    setParsedLoading(true)
    setParsedError(null)
    parseRunsApi
      .getParsedDocument(runId)
      .then((d) => {
        if (!cancelled) setParsedDoc(d)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setParsedError(
          err instanceof Error ? err.message : 'Failed to fetch parsed document',
        )
        setParsedDoc(undefined)
      })
      .finally(() => {
        if (!cancelled) setParsedLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [runId, run])

  const handleReparse = useCallback(
    async (parserType: string, config?: ParseConfig) => {
      if (!documentId) return
      await parseRunsApi.createParseRun(documentId, parserType, config)
      navigate('/documents')
    },
    [documentId, navigate],
  )

  // Clicking a bbox on the PDF also switches to the Pages tab
  const handleBlockSelectFromPdf = (blockId: string) => {
    setSelectedBlockId(blockId)
    setActiveTab('pages')
  }

  if (runLoading) return <div className="p-6">Loading run…</div>
  if (runError) return <div className="p-6 text-destructive">{runError}</div>
  if (!run) return <div className="p-6">Run not found.</div>

  const blocks = parsedDoc?.content?.blocks ?? []

  return (
    <div className="flex flex-col h-[calc(100vh-3.5rem)]">
      <div className="px-4 py-2 border-b shrink-0">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/documents">
            <ChevronLeft className="h-4 w-4 mr-1" /> Back to documents
          </Link>
        </Button>
      </div>

      <RunHeader run={run} onReparse={() => setReparseOpen(true)} />

      <div
        className="flex-1 grid overflow-hidden"
        style={{ gridTemplateColumns: '55% 45%' }}
      >
        {/* Left: PDF viewer */}
        <div className="border-r overflow-auto">
          {documentId && (parsedDoc || parsedLoading) ? (
            <DocumentPdfViewer
              documentId={documentId}
              blocks={blocks}
              selectedBlockId={selectedBlockId}
              onBlockSelect={handleBlockSelectFromPdf}
            />
          ) : (
            <div className="p-4 text-sm text-muted-foreground">
              {parsedLoading
                ? 'Loading parsed document…'
                : 'No parsed document available for this run.'}
            </div>
          )}
        </div>

        {/* Right: tabs */}
        <div className="overflow-hidden flex flex-col">
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="flex flex-col h-full"
          >
            <TabsList className="shrink-0 mx-3 mt-3 flex-wrap h-auto gap-1">
              <TabsTrigger value="pages">Pages</TabsTrigger>
              <TabsTrigger value="markdown">Markdown</TabsTrigger>
              <TabsTrigger value="text">Text</TabsTrigger>
              <TabsTrigger value="json">JSON</TabsTrigger>
              <TabsTrigger value="raw">Raw Payload</TabsTrigger>
              <TabsTrigger value="metrics">Metrics</TabsTrigger>
            </TabsList>

            <div className="flex-1 overflow-auto">
              <TabsContent value="pages" className="mt-0 h-full">
                <ParsedDocumentPane
                  parsedDocument={parsedDoc}
                  isLoading={parsedLoading}
                  error={parsedError}
                  selectedBlockId={selectedBlockId}
                  onBlockSelect={setSelectedBlockId}
                />
              </TabsContent>

              <TabsContent value="markdown" className="mt-0 p-4">
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  {parsedDoc?.fullMarkdown ? (
                    <Markdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeRaw]}
                    >
                      {parsedDoc.fullMarkdown}
                    </Markdown>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      {parsedLoading ? 'Loading…' : 'No markdown produced.'}
                    </p>
                  )}
                </div>
              </TabsContent>

              <TabsContent value="text" className="mt-0 p-4">
                <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed">
                  {parsedDoc?.fullText ||
                    (parsedLoading ? 'Loading…' : 'No text content.')}
                </pre>
              </TabsContent>

              <TabsContent value="json" className="mt-0 p-4">
                <pre className="font-mono text-xs bg-muted/30 p-3 rounded-lg overflow-auto">
                  {parsedDoc
                    ? JSON.stringify(parsedDoc.content, null, 2)
                    : parsedLoading
                      ? 'Loading…'
                      : 'No content.'}
                </pre>
              </TabsContent>

              <TabsContent value="raw" className="mt-0 h-full">
                <RawPayloadViewer
                  payload={rawPayload}
                  isLoading={rawLoading}
                  error={rawError}
                />
              </TabsContent>

              <TabsContent value="metrics" className="mt-0 p-4">
                <MetricsTab run={run} />
              </TabsContent>
            </div>
          </Tabs>
        </div>
      </div>

      <ReParseDialog
        open={reparseOpen}
        onOpenChange={setReparseOpen}
        onReparse={handleReparse}
      />
    </div>
  )
}
```

- [ ] **Step 2: Lint and build**

```bash
npm --prefix frontend run lint
npm --prefix frontend run build
```

Expected: exits 0. Fix any TypeScript or lint errors before continuing.

- [ ] **Step 3: Run full test suite**

```bash
npm --prefix frontend exec -- npx vitest run
```

Expected: all tests pass.

- [ ] **Step 4: Manual verification**

Start the app locally:

```bash
npm --prefix frontend run dev
```

Check each of the following:

1. Navigate to `/documents`. Open a document with a succeeded CDM parse run. The drawer's `RunTimeline` should show an "Open viewer" link per run. Click it.
2. `ParseRunDetailPage` loads at `/documents/:documentId/runs/:runId`.
3. **Left panel:** PDF renders. Bbox overlays appear color-coded by role. Hovering rects shows pointer cursor.
4. **Clicking a bbox rect:** Pages tab activates (if not already active), the matching block row highlights with a blue border and scrolls into view.
5. **Clicking a block row in Pages tab:** The PDF scrolls to that block's page, the matching bbox rect highlights (brighter fill + border).
6. **Markdown tab:** Full markdown renders.
7. **Text tab:** Full text renders in monospace.
8. **JSON tab:** CDM `content` object renders as formatted JSON.
9. **Raw Payload tab:** Raw parser payload renders (with Copy/Download buttons).
10. **Metrics tab:** Run metadata key-value rows render.
11. Open a run with `status=failed` — left panel shows "No parsed document available" message, all tabs still render (Metrics and Raw Payload have data; Pages/Markdown/Text/JSON show loading or empty states).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ParseRunDetailPage.tsx
git commit -m "feat(viewer): restructure ParseRunDetailPage as PDF+tabs audit workspace"
```
