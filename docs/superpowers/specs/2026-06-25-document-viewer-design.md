# Document Viewer — Design Spec

> **Status**: Approved, ready for implementation planning.
> **Scope**: Extend `ParseRunDetailPage` into a full parse-run audit workspace: PDF rendering with CDM bbox overlays on the left, all inspection tabs on the right, click-through selection between the two panels.
> **Out of scope**: Backend changes (all endpoints exist), routing changes, reuse in classification/extraction (noted for future), pagination or virtualization for very large PDFs.
> **Depends on**: Existing `ParseRunDetailPage`, `ParsedDocumentPane`, `RawPayloadViewer`, `RunHeader`, `ParsedDocumentViewer` components; existing `GET /documents/{id}/file` and `GET /parse-runs/{id}/parsed-document` endpoints.

---

## 1. Goals

1. Let a user open a parse run and see the parsed document blocks (bboxes) overlaid on the real PDF page.
2. Click-through: clicking a block in the Pages tab highlights its bbox on the PDF and vice versa.
3. All existing inspection surfaces (Markdown, Text, CDM JSON, Raw Payload, Metrics) remain accessible on the same page.
4. The drawer (`ParsedDocumentViewer`) is unchanged except for a new "Open in Viewer" button.

---

## 2. Route

No new route. The viewer is `ParseRunDetailPage` at the existing path:

```
/documents/:documentId/runs/:runId
```

The drawer adds an "Open in Viewer →" button that navigates to this URL with the currently selected run.

---

## 3. Page Layout

```
┌─ RunHeader (parser · status · duration · tokens · cost) ──────────────────┐
│ [Left 55%] DocumentPdfViewer     [Right 45%] Tabs                          │
│                                  ┌──────────────────────────────────────┐  │
│  ┌──────────────────────────┐    │ Pages │ Markdown │ Text │ JSON        │  │
│  │                          │    │ Raw Payload │ Metrics                 │  │
│  │  PDF page (react-pdf)    │    ├──────────────────────────────────────┤  │
│  │  [SVG bbox overlay]      │    │  (active tab content)                │  │
│  │                          │    │                                      │  │
│  └──────────────────────────┘    └──────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────┘
```

Both panels are independently scrollable. The page uses `h-[calc(100vh-3.5rem)]` and `overflow-hidden` (matching the existing `ParseRunDetailPage` shell).

---

## 4. Components

### 4.1 `ParseRunDetailPage` — restructured

File: `frontend/src/pages/ParseRunDetailPage.tsx`

Changes:
- Add `selectedBlockId: string | null` state (starts `null`).
- Replace the current two-panel layout (Raw Payload | CDM Blocks) with the new layout (PDF viewer | tabs).
- Pass `selectedBlockId` / `onBlockSelect` down to both panels.
- Data fetching unchanged: `useParseRunDetail`, `useParseRunRawPayload`, manual `getParsedDocument` fetch.

### 4.2 `DocumentPdfViewer` — new component

File: `frontend/src/components/parse-runs/DocumentPdfViewer.tsx`

```ts
interface DocumentPdfViewerProps {
  documentId: string
  blocks: Block[]
  selectedBlockId: string | null
  onBlockSelect: (blockId: string) => void
}
```

**PDF fetch:** Uses react-pdf `<Document file={{ url: '/api/documents/{id}/file', httpHeaders: { Authorization: `Bearer ${token}` } }}>`. Token sourced from `AuthContext`. No blob URL required.

**Rendering structure per page:**
```
<div className="relative"> // sized to match react-pdf <Page> output
  <Page pageNumber={n} onRenderSuccess={({ width, height }) => captureSize(n, { width, height })} />
  <svg className="absolute inset-0 pointer-events-none" style={{ width, height }}>
    {blocksOnPage.map(b => <rect ... onClick={() => onBlockSelect(b.id)} />)}
  </svg>
</div>
```

`pointer-events-none` on the SVG except on `<rect>` elements (override to `pointer-events-auto`).

**Bbox coordinate math:**
```
rect.x      = bbox.x0 * pageWidth
rect.y      = bbox.y0 * pageHeight
rect.width  = (bbox.x1 - bbox.x0) * pageWidth
rect.height = (bbox.y1 - bbox.y0) * pageHeight
```

CDM bboxes are normalized (0.0–1.0), origin top-left.

**Color coding by block role:**

| Role | Fill color (RGBA) |
|------|-------------------|
| title | `rgba(59,130,246,0.25)` — blue |
| heading | `rgba(99,102,241,0.25)` — indigo |
| paragraph | `rgba(107,114,128,0.15)` — gray |
| list | `rgba(245,158,11,0.25)` — amber |
| table | `rgba(16,185,129,0.25)` — green |
| figure | `rgba(139,92,246,0.25)` — purple |
| caption | `rgba(249,115,22,0.25)` — orange |
| header / footer | `rgba(148,163,184,0.15)` — slate |
| code | `rgba(6,182,212,0.25)` — cyan |
| formula | `rgba(236,72,153,0.25)` — pink |
| other | `rgba(107,114,128,0.15)` — gray |

**Selected block:** fill opacity increased to `0.5` (regardless of role default) + `strokeWidth=2` solid `stroke` in the role color (full opacity).

**Scroll-to-page on external selection:** `useEffect` on `selectedBlockId` — find the block's `page_index`, call `scrollIntoView` on the page container element (identified by `data-page-index` attribute).

**Loading state:** skeleton placeholder while react-pdf loads. Error state for failed fetch.

### 4.3 `ParsedDocumentPane` — enhanced

File: `frontend/src/components/parse-runs/ParsedDocumentPane.tsx`

New optional props (backward-compatible):
```ts
selectedBlockId?: string | null
onBlockSelect?: (blockId: string) => void
```

Changes:
- Each block row gets `data-block-id={b.id}` attribute.
- Each block tracks its own `localOpen: boolean` state (useState, starts false). The `Collapsible` `open` prop is `localOpen || b.id === selectedBlockId` — so an externally selected block always opens, and the user can still open/close others independently.
- Block row click calls `onBlockSelect(b.id)` if provided (in addition to toggling `localOpen`).
- `useEffect` on `selectedBlockId`: when it changes, `document.querySelector('[data-block-id="${selectedBlockId}"]')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })`.

Existing tests and callers unaffected (props are optional).

### 4.4 `ParsedDocumentViewer` — one addition

File: `frontend/src/components/documents/ParsedDocumentViewer.tsx`

Add "Open in Viewer →" button to the header, visible when a run is selected. Navigates to `/documents/${documentId}/runs/${selectedRun.id}`. Uses `useNavigate` from react-router-dom.

---

## 5. Right Panel Tabs

Default tab: **Pages**.

| Tab label | Content | Existing source |
|-----------|---------|-----------------|
| Pages | `ParsedDocumentPane` with click-through props | Drawer Pages tab |
| Markdown | `react-markdown` of `parsedDoc.fullMarkdown` | Drawer Markdown tab |
| Text | `<pre className="whitespace-pre-wrap font-mono text-xs">` of `parsedDoc.fullText` | Drawer Text tab |
| JSON | `<pre>` of `JSON.stringify(parsedDoc.content, null, 2)` | Drawer Raw JSON tab |
| Raw Payload | `<RawPayloadViewer payload={rawPayload} />` | Detail page left panel (moved) |
| Metrics | Key-value rows from run fields — reuse `MetricsTab` extracted from `ParsedDocumentViewer` | Drawer Metrics tab |

`MetricsTab` is currently a private function inside `ParsedDocumentViewer.tsx`. It is extracted to `frontend/src/components/parse-runs/RunMetricsTab.tsx` and imported by both files.

---

## 6. Click-Through Wiring

`selectedBlockId` state lives in `ParseRunDetailPage`. Both panels receive it as a prop.

**PDF → Pages tab:**
1. User clicks a `<rect>` on the SVG overlay.
2. `onBlockSelect(blockId)` fires.
3. Pages tab becomes active (controlled `activeTab` state, switches to `"pages"`).
4. `ParsedDocumentPane` opens that block's `Collapsible` and scrolls it into view.

**Pages tab → PDF:**
1. User clicks a block row in `ParsedDocumentPane`.
2. `onBlockSelect(blockId)` fires.
3. `DocumentPdfViewer` effect runs: finds block, gets `page_index`, scrolls PDF container to `[data-page-index="${pageIndex}"]`.
4. Block bbox highlighted with stronger fill + border.

---

## 7. New Dependency

`react-pdf` — wraps PDF.js, well-maintained, ~40KB gzip.

```bash
cd frontend && npm install react-pdf
```

Worker setup: react-pdf requires a PDF.js worker. Standard pattern — set `pdfjs.GlobalWorkerOptions.workerSrc` once at module level in `DocumentPdfViewer.tsx`:

```ts
import { pdfjs } from 'react-pdf'
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).toString()
```

Vite handles the worker URL resolution via `import.meta.url`. No extra Vite config needed.

---

## 8. Testing

**`DocumentPdfViewer.test.tsx`**
- Renders correct number of bbox rects for blocks with bboxes.
- Fires `onBlockSelect` with correct `blockId` when a rect is clicked.
- Highlighted rect (selected block) has distinct visual treatment.
- Shows loading state while PDF loads.

**`ParsedDocumentPane.test.tsx`** (additions to existing)
- `selectedBlockId` prop opens that block's collapsible.
- Clicking a block row fires `onBlockSelect` with the block's id.
- Existing tests continue to pass.

**Manual verification checklist**
- Open a document with a succeeded CDM parse run → "Open in Viewer →" button appears in drawer.
- Button navigates to `/documents/:id/runs/:runId`.
- PDF renders on the left; all tabs render on the right.
- Bbox overlays appear on the PDF, color-coded by role.
- Clicking a bbox → Pages tab activates, matching block expands and scrolls into view.
- Clicking a block in Pages tab → PDF scrolls to that page, bbox highlights.
- All other tabs (Markdown, Text, JSON, Raw Payload, Metrics) render their content correctly.
- Documents without a PDF file show an appropriate error state in the PDF panel.

---

## 9. Future Reuse (out of scope this sprint)

`DocumentPdfViewer` accepts `blocks`, `selectedBlockId`, and `onBlockSelect` with no coupling to parse-run concepts. Future callers — classification result pages, extraction result pages — can pass a filtered or annotated block set and reuse the same visual with different highlight semantics (e.g. blocks labelled by class, blocks mapped to extraction fields). No changes to the component are anticipated; the wiring is deferred to those features.
