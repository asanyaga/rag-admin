---
title: Extract Page Redesign
date: 2026-06-30
---

# Extract Page Redesign

Refactor the Extract section into a three-page flow matching the Classify pattern: a main list page, a dedicated new-run config page, and a dedicated result detail page with bidirectional PDF provenance.

---

## Scope

**In scope:**
- Shared `DocumentPickerPanel` component extracted from the existing Classify/Parse inline pattern, used on the Extract main page
- `/extract` main page refactored to use `DocumentPickerPanel` + history list (no inline form)
- `/extract/new` — dedicated new-run configuration page
- `/extract/:resultId` — dedicated result detail page with PDF provenance wiring
- `ExtractionHistory` simplified to a flat navigation list

**Out of scope:**
- Migrating `DocumentsPage` (Parse) or `ClassificationPage` (Classify) to use `DocumentPickerPanel` — deferred to a follow-up cleanup
- Backend changes
- Changes to `ExtractionResultViewer` content — display logic is unchanged; only the layout wrapper and new props change

---

## Route Structure

| Route | Component | Purpose |
|---|---|---|
| `/extract` | `ExtractionPage` (refactored) | Document picker + schema manager + history list |
| `/extract/new?documentId=` | `NewExtractionRunPage` (new) | Configure and submit a new extraction run |
| `/extract/:resultId` | `ExtractionResultDetailPage` (new) | View result with PDF provenance |

---

## Navigation Flow

```
/extract
  ├─ "New Run" button ──────────────→ /extract/new?documentId=...
  │                                       │
  │                                       └─ submit ──→ /extract/:resultId  (immediate redirect)
  │                                       └─ cancel ──→ /extract?documentId=...
  │
  ├─ history row click ─────────────→ /extract/:resultId
  │
/extract/:resultId
  ├─ "Back" link ───────────────────→ /extract?documentId=...
  └─ "View document" link ──────────→ /parse?documentId=...  (cross-app link)
```

Submit on `/extract/new` navigates immediately to `/extract/:resultId`, which shows processing status while the run is pending — matching the Classify pattern exactly.

---

## 1. Shared `DocumentPickerPanel` Component

**File:** `frontend/src/components/shared/DocumentPickerPanel.tsx`

Replaces the extraction-specific `components/extraction/DocumentSelector.tsx` (which is deleted). The new component matches the richer pattern used inline on the Classify and Parse pages.

### Props

```ts
interface DocumentPickerPanelProps {
  documents: DocumentListItem[]
  folders: Folder[]
  isLoading: boolean
  selectedDocumentId: string | null
  onSelect: (documentId: string) => void
  onUploadClick: () => void
}
```

### Layout (top to bottom, fills panel height)

1. **Folder filter** — `Select` dropdown; "All folders" default; changing folder clears document selection
2. **Search** — text input with search icon; filters document list by title
3. **Document list** — `ScrollArea`, one button per document; shows title + `DocumentStatusBadge`; selected row highlighted with `bg-muted`; disabled/non-clickable for `processing` status
4. **Upload button** — pinned to bottom of panel, full-width outline button

### Behaviour

- Folder filter and search are independent; both applied simultaneously
- Selecting a document fires `onSelect` with the document ID
- Processing documents are visually dimmed and cannot be selected (same as current `DocumentSelector`)

---

## 2. `/extract` — Refactored Main Page

**File:** `frontend/src/pages/ExtractionPage.tsx` (refactored in place)

### Layout

```
┌─ header: "Extract" / project name ──────────────────────────────────────────┐
├──────────────────────┬──────────────────────────────────────────────────────┤
│  DocumentPickerPanel │  (empty state when no doc selected)                  │
│  w-72, border-r      │                                                      │
│                      │  OR when doc selected:                               │
│                      │  ┌─ SchemaManager ─────────────────────────────────┐ │
│                      │  │ (create / edit / delete schemas)                │ │
│                      │  └─────────────────────────────────────────────────┘ │
│                      │  ┌─ Document title + status badge ─────────────────┐ │
│                      │  └─────────────────────────────────────────────────┘ │
│                      │  ┌─ "New Run" button ──────────────────────────────┐ │
│                      │  └─────────────────────────────────────────────────┘ │
│                      │  ┌─ ExtractionHistory (simplified) ────────────────┐ │
│                      │  │ flat list of past runs, click → navigate        │ │
│                      │  └─────────────────────────────────────────────────┘ │
└──────────────────────┴──────────────────────────────────────────────────────┘
```

### State

- `selectedDocumentId` — synced with `?documentId=` search param (same as today)
- `uploadDialogOpen` — controls `DocumentUploadDialog`
- `schemaEditorOpen` + `editingSchema` — passed to `ExtractionSchemaEditor` modal

### Key changes from current

- `DocumentSelector` (extraction-specific) replaced with `DocumentPickerPanel`
- `ExtractionForm` removed — moved to `/extract/new`
- `ExtractionHistory` now renders a flat list with `Link` navigation instead of inline collapsibles
- `SchemaManager` remains here as the primary home for schema CRUD
- `parseRuns`, `useExtractionResults`, `inProgressPhase` logic removed from this page — owned by the new/detail pages respectively
- `DocumentUploadDialog` stays here; after upload, `handleSelectDocument` fires as before

---

## 3. `ExtractionHistory` — Simplified

**File:** `frontend/src/components/extraction/ExtractionHistory.tsx` (modified)

### Changes

- Remove `Collapsible` and `CollapsibleContent` — no inline result expansion
- Remove `selectedResult`, `isLoadingResult`, `onSelectResult`, `onDeselectResult` props
- Remove `ExtractionResultViewer` import and usage
- Each result row becomes a `<Link to={/extract/${r.id}}>` wrapping the row content
- Row content unchanged: schema name badge, method badge, status badge, relative date
- Export (CSV) and delete icon buttons remain on hover — `e.stopPropagation()` to prevent navigation
- `inProgressPhase` synthetic row (parsing/extracting/failed spinner) removed — the detail page owns that state; this page only shows persisted results from the API
- Empty state and loading skeletons unchanged

### Simplified props

```ts
interface ExtractionHistoryProps {
  results: ExtractionResultListItem[]
  isLoading: boolean
  schemas?: ExtractionSchema[]
  onDeleteResult: (resultId: string) => Promise<void>
  onExportResult: (resultId: string) => Promise<void>
}
```

---

## 4. `/extract/new` — New Run Page

**File:** `frontend/src/pages/NewExtractionRunPage.tsx` (new)

Mirrors `NewClassificationRunPage` in structure: back link, document context header, card sections, submit/cancel.

### URL & state

- `documentId` from `?documentId=` search param
- `documentTitle` from `location.state.documentTitle` (passed by the calling page, same as Classify)

### Layout

```
← Back                         [page header]

New extraction run
<document title>

┌─ Card: Parse configuration ──────────────────────────────────────────────┐
│  ParseMethodSelector (parser type + config)                              │
└──────────────────────────────────────────────────────────────────────────┘

┌─ Card: Extraction ────────────────────────────────────────────────────────┐
│  Schema selector dropdown                                                 │
│  [Edit schema] shortcut (opens ExtractionSchemaEditor modal)             │
│  Extraction method selector                                              │
│  Method-specific fields (LLM config, chunking, etc.)                    │
└──────────────────────────────────────────────────────────────────────────┘

[Start extraction]   [Cancel]
```

### Schema shortcut

- Schema dropdown shows all project schemas (loaded via `useExtractionSchemas`)
- "Edit" icon button next to the dropdown opens `ExtractionSchemaEditor` in edit mode for the selected schema
- "New schema" link below dropdown opens `ExtractionSchemaEditor` in create mode
- This is the same `ExtractionSchemaEditor` modal used on the main page — no duplication of logic, just a second trigger

### Behaviour

- Parse config seeded from latest viable parse run for the document (same logic as current `ExtractionForm`)
- On submit: calls `runExtractionWithParse`, navigates immediately to `/extract/<newResultId>`
- On cancel: navigates to `/extract?documentId=<documentId>`
- If no `documentId` in params: redirect to `/extract` (guard)

### State owned

- `parserType`, `parserConfig`
- `schemaId`, `extractionMethod`, all method-specific config fields
- `isSubmitting`, `error`
- `schemaEditorOpen`, `editingSchema`

---

## 5. `/extract/:resultId` — Result Detail Page

**File:** `frontend/src/pages/ExtractionResultDetailPage.tsx` (new)

### Layout

```
┌─ header ──────────────────────────────────────────────────────────────────┐
│  ← Back to extract    [doc title → /parse?documentId=...]   [Re-run] [⋯] │
├───────────────────────────────────┬───────────────────────────────────────┤
│  DocumentPdfViewer                │  ExtractionResultViewer               │
│  (left ~55%, border-r)            │  (right ~45%, overflow-y-auto, p-4)   │
│                                   │                                       │
│  shown only when                  │  existing component, unchanged        │
│  sourceParseRunId is set          │  + new optional props (see below)     │
│                                   │                                       │
│  OR full-width when no            │                                       │
│  sourceParseRunId                 │                                       │
└───────────────────────────────────┴───────────────────────────────────────┘
```

### Header

- **Back link**: `← Back` → `/extract?documentId=<result.documentId>`
- **Document link**: document title as a clickable link → `/parse?documentId=<result.documentId>` (opens the parse page pre-selected on the source document)
- **Re-run button**: navigates to `/extract/new?documentId=<result.documentId>` with `location.state` carrying the previous run's config as defaults (same pattern as Classify re-run)
- Status badge + method badge + relative timestamp in header

### Data loading

```ts
const { resultId } = useParams()
const { result, isLoading } = useExtractionResultDetail(resultId)  // fetches full result
const [parseBlocks, setParseBlocks] = useState<Block[]>([])

useEffect(() => {
  if (!result?.sourceParseRunId) return
  getParsedDocument(result.sourceParseRunId)
    .then(doc => setParseBlocks(doc.content?.blocks ?? []))
    .catch(() => setParseBlocks([]))
}, [result?.sourceParseRunId])
```

### Provenance wiring — three cases

**Case 1 — Block-level citations** (`inject_block_ids: true` + `citation_level: full` or `auto`)

- `result.citations` contains records with `blockId` and `pageIndex`
- Build `blockColors: Map<blockId, string>` — group by field or assign a single accent colour to all cited blocks
- Pass `blocks={parseBlocks}`, `blockColors={blockColors}`, `selectedBlockId`, `onBlockSelect` to `DocumentPdfViewer`
- Clicking a block in the PDF sets `selectedBlockId` → `ExtractionResultViewer` highlights the relevant citation row
- Clicking a citation row in the viewer → sets `selectedBlockId` → PDF scrolls to that block

**Case 2 — Page-level only** (`citation_level: page_only`, or chunked run without block IDs)

- Page numbers come from `result.citations[].pageIndex` (unchunked) or `meta.chunks[].pageIndices` (chunked)
- Pass `blocks={[]}` to `DocumentPdfViewer` (no bbox overlays)
- The new `onPageSelect` prop on `ExtractionResultViewer` is wired to fire when the user clicks a citation record or a chunk row in the Chunk Details panel; the page responds by scrolling the PDF container to `data-page-index="N"`
- `selectedBlockId` not used in this case; a `selectedPageIndex` state drives scroll

**Case 3 — No `sourceParseRunId`** (e.g. llamaextract, which manages its own parsing)

- `DocumentPdfViewer` not rendered
- `ExtractionResultViewer` fills the full right-hand side at `max-w-3xl mx-auto`
- No PDF panel, no provenance highlighting

### Processing / pending state

When `result.status === 'pending'`:
- PDF panel shows a loading placeholder (the result has no data yet)
- `ExtractionResultViewer` shows its existing pending state ("Extraction is in progress...")
- Page polls for status: `useExtractionResultDetail` refetches on an interval (e.g. every 3 s) while `status === 'pending'`, clears the interval once `status` transitions to `completed` or `failed`

### `ExtractionResultViewer` new optional props

```ts
// Added to ExtractionResultViewerProps — all optional, no breaking change
selectedBlockId?: string | null
onBlockSelect?: (blockId: string) => void   // fires when user clicks a cited field row
onPageSelect?: (pageIndex: number) => void  // fires when user clicks a chunk/citation row (page-level)
```

These props are only wired by `ExtractionResultDetailPage`. When absent (e.g. the viewer is used elsewhere), behaviour is unchanged.

---

## 6. Files Changed / Created / Deleted

| Action | File |
|---|---|
| **Create** | `frontend/src/components/shared/DocumentPickerPanel.tsx` |
| **Create** | `frontend/src/pages/NewExtractionRunPage.tsx` |
| **Create** | `frontend/src/pages/ExtractionResultDetailPage.tsx` |
| **Create** | `frontend/src/hooks/useExtractionResultDetail.ts` — fetches a single result by ID, polls while `status === 'pending'` |
| **Modify** | `frontend/src/pages/ExtractionPage.tsx` |
| **Modify** | `frontend/src/components/extraction/ExtractionHistory.tsx` |
| **Modify** | `frontend/src/components/extraction/ExtractionResultViewer.tsx` — add 3 optional props; fix existing bug: transform Apply navigates to `/extraction?resultId=...` (wrong path), change to `/extract/${derived.id}` |
| **Modify** | `frontend/src/App.tsx` (add 2 new routes) |
| **Delete** | `frontend/src/components/extraction/DocumentSelector.tsx` |

---

## 7. Edge Cases

| Case | Handling |
|---|---|
| No `documentId` in `/extract/new` URL | Redirect to `/extract` |
| Result not found (`/extract/:resultId`) | Error state with back link to `/extract` |
| `sourceParseRunId` set but `getParsedDocument` fails | Log error, hide PDF panel (fall through to Case 3) |
| Result `status === 'failed'` | Detail page shows failure message from `ExtractionResultViewer`; no PDF interaction |
| `citation_level: off` | Treat as Case 3 (no provenance) — no PDF panel |
| Document status `processing` or `failed` | Disabled in picker; "New Run" button disabled if doc not `ready` |
| User lands on `/extract/:resultId` directly (no prior navigation) | Back link goes to `/extract?documentId=<result.documentId>` — always computable from the result |
