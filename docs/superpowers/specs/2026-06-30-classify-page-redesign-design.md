# Classify Page Redesign — Design Spec

**Date:** 2026-06-30
**Status:** Approved for implementation

---

## 1. Problem & Motivation

The current classify flow is a three-page wizard: a global run list (`ClassificationPage`), a three-step wizard (`NewClassificationRunPage` — pick doc → pick parse run → configure), and a standalone detail page (`ClassificationRunDetailPage`). This creates unnecessary navigation friction and doesn't match the single-page pattern established by the extraction feature.

Three concrete problems:

1. **Wizard is redundant.** Selecting doc and parse run as separate steps adds clicks without adding clarity. The extraction page handles this inline.
2. **`ClassificationRunForm` is not reusable.** The classify config (labels, classifier type, provider/model) will be needed by extraction and agent workflow tool config. The form currently owns its own submit button and is tightly coupled to the wizard page.
3. **Results have no spatial context.** The `ClassificationResultsViewer` shows blocks grouped by label but gives no indication of where in the document those regions fall. `ParsedDocumentPane` already supports block-level selection and scroll-to — it just needs label overlays wired in.

---

## 2. Target Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ Header: Classify / <project name>                   [New Run button] │
├──────────────┬──────────────────────────────────────────────────────┤
│              │  Run history (compact list, latest auto-selected)     │
│  Document    ├──────────────────────────┬───────────────────────────┤
│  Selector    │  ClassificationResults   │  ParsedDocumentViewer     │
│  (~220px)    │  Viewer                  │  with label overlays      │
│              │  (~320px)                │  (remaining space)        │
│              │                          │  [collapse toggle]        │
└──────────────┴──────────────────────────┴───────────────────────────┘
```

"New Run" opens a **wide sheet (~60% viewport)** sliding from the right:

```
┌─────────────────────────────────────────────────┐
│ New classification run — <document name>    [✕]  │
├─────────────────────────────────────────────────┤
│  ParseMethodSelector                             │
│  ─────────────────────────────────────────────  │
│  ClassificationConfig                            │
│    · Labels                                      │
│    · Classifier type                             │
│    · Conditional provider config                 │
│                                                  │
│                        [Start classification]    │
└─────────────────────────────────────────────────┘
```

---

## 3. Composable Pipeline Architecture

Classification config is one stage in a composable pipeline:

```
ParseConfig  →  ClassificationConfig  →  ExtractionConfig
```

Each stage is a standalone controlled component with a `value/onChange` interface and no submit button. Host contexts assemble the stages they need and own the submit action.

- **Classify page sheet**: `ParseConfig` + `ClassificationConfig`
- **Extraction page** (current): `ParseConfig` + `ExtractionConfig`
- **Extraction with classification** (future workstream): `ParseConfig` + `ClassificationConfig` + `ExtractionConfig`
- **Agent workflow tool config** (future workstream): `ClassificationConfig` standalone

`ClassificationConfig` must not contain `ParseConfig` — they are separate composable pieces.

---

## 4. Workstreams

### WS1 — `ClassificationConfig` Component (independent)

**Goal:** Extract the classifier UI from `ClassificationRunForm` into a reusable controlled component.

**New component:** `frontend/src/components/classification/ClassificationConfig.tsx`

```typescript
interface ClassificationConfigValue {
  labels: string[]
  classifierType: string
  classifierConfig: Record<string, unknown>
}

interface ClassificationConfigProps {
  value: ClassificationConfigValue
  onChange: (value: ClassificationConfigValue) => void
  defaultValues?: Partial<ClassificationConfigValue>
}
```

Renders:
1. Labels input + tag list (add on Enter or button click, remove with ✕)
2. Classifier type select (`llm` | `llamaindex_split`)
3. Conditional config panel:
   - `llm` → `PromptConfigEditor` + batch settings collapsible (batch size, batch overlap)
   - `llamaindex_split` → placeholder note
4. No submit button — the host owns submission

**Modified:** `ClassificationRunForm.tsx` becomes a thin wrapper — it renders `ClassificationConfig` + a "Start classification" submit button. Existing callers (`NewClassificationRunPage`) are deleted in WS3 so this wrapper can be deleted then too.

---

### WS2 — Document Viewer Overlay Wiring (independent)

**Goal:** Wire classification label overlays into `ParsedDocumentPane` and `ParsedDocumentViewer`.

#### `ParsedDocumentPane` changes

New optional props:

```typescript
interface ParsedDocumentPaneProps {
  // existing
  parsedDocument: ParsedDocumentDetail | undefined
  isLoading?: boolean
  error?: string | null
  selectedBlockId?: string | null
  onBlockSelect?: (id: string) => void
  // new
  blockLabels?: Map<string, string>   // blockId → label
  pageLabels?: Map<number, string>    // pageIndex → label (first/dominant label for that page)
  labelColors?: Map<string, string>   // label → CSS color class or hex
}
```

**`BlockRow`**: renders a small colored label badge when `blockLabels.get(block.id)` exists, alongside the existing role badge.

**Page headers**: render a colored label badge from `pageLabels.get(p.index)` in the page collapsible trigger, so the label is visible without expanding the page.

#### `ParsedDocumentViewer` changes

New optional props:

```typescript
interface ParsedDocumentViewerProps {
  documentId: string
  // new
  defaultParseRunId?: string          // pre-selects the run used by the classification
  regions?: ClassificationRegion[]    // for page-level label derivation
  annotatedBlocks?: AnnotatedBlock[]  // for block-level label derivation
}
```

`ParsedDocumentViewer` derives the overlay maps internally:

- `blockLabels`: `new Map(annotatedBlocks.map(b => [b.blockId, b.label ?? '']))`  filtered to non-null labels
- `pageLabels`: from `regions`, map each page index in `pageStart..pageEnd` to that region's label (first region wins on overlap)
- `labelColors`: assigns colors from a fixed 8-color palette cycling by label index

**Color palette** (Tailwind-compatible CSS vars, accessible):

| Index | Label color token |
|-------|------------------|
| 0 | `hsl(221 83% 53%)` — blue |
| 1 | `hsl(142 71% 45%)` — green |
| 2 | `hsl(32 95% 44%)` — amber |
| 3 | `hsl(346 77% 49%)` — red |
| 4 | `hsl(262 80% 58%)` — purple |
| 5 | `hsl(199 89% 48%)` — cyan |
| 6 | `hsl(25 95% 53%)` — orange |
| 7 | `hsl(316 70% 50%)` — pink |

Colors cycle if there are more than 8 labels.

`ParsedDocumentViewer` passes derived maps down to `ParsedDocumentPane` via the new props. The viewer also respects `defaultParseRunId` by passing it as the initial selected run to `useParseRuns`.

`useParseRuns` may need a minor update to accept an optional `defaultRunId` for initial selection — check the hook before modifying.

---

### WS3 — Page & Sheet Redesign (depends on WS1 + WS2)

**Goal:** Replace the three-page wizard with the single-page layout. WS3 is the assembly step.

#### Deleted files

- `frontend/src/pages/NewClassificationRunPage.tsx`
- `frontend/src/pages/ClassificationRunDetailPage.tsx`
- Routes `/classify/new` and `/classify/:runId` removed from the router

#### New components

**`ClassificationRunHistory`** (`frontend/src/components/classification/ClassificationRunHistory.tsx`)

Compact list of runs for the selected document. Shows: labels (truncated), status badge, provider/model summary, relative date. Auto-selects the latest completed or most recent run on document change. "New Run" button opens the sheet.

```typescript
interface ClassificationRunHistoryProps {
  documentId: string
  selectedRunId: string | null
  onSelectRun: (runId: string) => void
  onNewRun: () => void
}
```

**`ClassificationRunDetail`** (`frontend/src/components/classification/ClassificationRunDetail.tsx`)

Shows the full detail view for a selected run. Replaces the content of the deleted `ClassificationRunDetailPage`.

```typescript
interface ClassificationRunDetailProps {
  runId: string
  documentId: string
}
```

Renders:
1. Metadata strip: labels requested, regions count, tokens (in/out), duration, status badge
2. Error alert when `run.status === 'failed'`
3. Running pulse when `run.status === 'running'`
4. Horizontal split (when `run.status === 'completed'`):
   - Left panel (~320px, shrink-0): `ClassificationResultsViewer` (unchanged component)
   - Right panel (flex-1): `ParsedDocumentViewer` with `defaultParseRunId={run.parseRunId}`, `regions={run.regions}`, and `annotatedBlocks` fetched via `useClassificationRunBlocks(runId)`. Collapse toggle button in the panel header.

**`ClassificationRunSheet`** (`frontend/src/components/classification/ClassificationRunSheet.tsx`)

Wide sheet (~60% viewport via `className="w-[60vw] max-w-3xl"` on shadcn `SheetContent`).

```typescript
interface ClassificationRunSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  documentId: string
  documentTitle: string
  defaultValues?: ClassificationConfigValue & { parser?: string; parserConfig?: ParseConfig }
  onStarted: (runId: string) => void  // called after API responds, triggers auto-select
}
```

Sheet body:
1. `ParseMethodSelector` (parse config, seeded from `defaultValues`)
2. `ClassificationConfig` (seeded from `defaultValues`)
3. Submit button "Start classification" — calls `createClassificationRun`, then calls `onStarted(run.id)`

Pre-population: when opening the sheet from a selected run, pass that run's `classifierType`/`classifierConfig` as `defaultValues`. The parse config defaults to the latest viable parse run for the document (same logic as extraction).

#### Rewritten `ClassificationPage`

`frontend/src/pages/ClassificationPage.tsx` — complete rewrite.

Layout mirrors `ExtractionPage`: `-m-6 flex flex-col h-[calc(100vh-3.5rem)]` with a fixed header, then a two-panel body.

State:
- `selectedDocumentId` (from `?documentId=` URL param, same as extraction)
- `selectedRunId` — driven by `ClassificationRunHistory` auto-select
- `sheetOpen` — controls the new-run sheet
- `sheetDefaultValues` — pre-populated from the selected run

Data:
- `useDocuments(projectId)` — left panel
- Run history and run detail are owned by `ClassificationRunHistory` and `ClassificationRunDetail` respectively (each fetches its own data)

```
ClassificationPage
├── Header (title, project)
├── Left panel: DocumentSelector
└── Right panel
    ├── Empty state (no doc selected)
    └── When doc selected:
        ├── ClassificationRunHistory
        │   └── "New Run" → opens ClassificationRunSheet
        └── ClassificationRunDetail (for selectedRunId)
            ├── Metadata strip + Re-run button
            └── Split: ClassificationResultsViewer | ParsedDocumentViewer
```

"Re-run" button on the metadata strip opens the sheet pre-populated with the current run's config.

#### Route changes

```typescript
// Before
{ path: '/classify', element: <ClassificationPage /> }
{ path: '/classify/new', element: <NewClassificationRunPage /> }
{ path: '/classify/:runId', element: <ClassificationRunDetailPage /> }

// After
{ path: '/classify', element: <ClassificationPage /> }
// /classify/new and /classify/:runId removed
```

---

## 5. Hook Audit

| Hook | Change |
|------|--------|
| `useClassificationRuns(projectId)` | Check if it can be scoped by `documentId`; if not, add overload |
| `useClassificationRunDetail(runId)` | No change — used by `ClassificationRunDetail` |
| `useClassificationRunBlocks(runId)` | No change — used by `ClassificationRunDetail` for overlay wiring |
| `useParseRuns(documentId)` | Minor: accept optional `defaultRunId` for initial selection |
| `useDocuments(projectId)` | No change |

---

## 6. File Map

**New:**
- `frontend/src/components/classification/ClassificationConfig.tsx`
- `frontend/src/components/classification/ClassificationRunSheet.tsx`
- `frontend/src/components/classification/ClassificationRunDetail.tsx`
- `frontend/src/components/classification/ClassificationRunHistory.tsx`

**Modified:**
- `frontend/src/pages/ClassificationPage.tsx` — complete rewrite
- `frontend/src/components/parse-runs/ParsedDocumentPane.tsx` — overlay props
- `frontend/src/components/documents/ParsedDocumentViewer.tsx` — overlay props + `defaultParseRunId`
- `frontend/src/components/classification/ClassificationRunForm.tsx` — thin wrapper (can be deleted once WS3 removes its only caller)
- Router — remove two routes

**Deleted:**
- `frontend/src/pages/NewClassificationRunPage.tsx`
- `frontend/src/pages/ClassificationRunDetailPage.tsx`

**Unchanged:**
- `frontend/src/components/classification/ClassificationResultsViewer.tsx`
- `frontend/src/components/classification/ClassificationLabelSection.tsx`
- `frontend/src/components/classification/ClassificationBlockRow.tsx`
- `frontend/src/components/classification/ClassificationRunStatusBadge.tsx`
- `frontend/src/api/classification.ts`
- `frontend/src/types/classification.ts`
- All backend files

---

## 7. Out of Scope

- Extraction + classification pipeline (future workstream)
- Agent workflow classify tool config (future workstream)
- `LlamaIndexSplitClassifier` implementation
- Backend changes of any kind
- Upload-from-classify-page (DocumentUploadDialog not included; users upload via the Documents page)
- Block-level click-to-highlight cross-linking between `ClassificationResultsViewer` and `ParsedDocumentViewer` (can be a follow-on)
