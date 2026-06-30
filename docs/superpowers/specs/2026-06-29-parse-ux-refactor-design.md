# Parse UX Refactor — Design Spec

**Date:** 2026-06-29
**Status:** Approved

## Overview

Refactor the documents/parse UX to make the parse step explicit in the nav and across the pipeline.
Delivered as three sequential workstreams. Workstream 1 (Parse) is fully specified here.
Workstreams 2 and 3 will be designed after Parse ships.

---

## Workstream 1: Parse (Nav + Two-Panel Refactor)

### Route changes

| Old path | New path |
|---|---|
| `/documents` | `/parse` |
| `/documents/:documentId/runs/:runId` | `/parse/:documentId/runs/:runId` |
| `/extraction` | `/extract` |

Update `App.tsx` path strings directly. No redirects needed — internal tool with no external
link consumers.

### Navigation order (`navigation.ts`)

```
Dashboard
Projects
Source Documents
Parse              ← was "Project Documents"  href: /parse
Classify
Extract            ← was "Extraction"          href: /extract
Index
Data Stores
Export
Agents
Evaluation
Settings
```

### Parse page — two-panel layout

`DocumentsPage` is renamed `ParsePage` and refactored from its current layout (folder sidebar +
document table + Sheet/drawer) into a two-panel layout.

```
┌──────────────────┬──────────────────────────────────────────┐
│  LEFT PANEL      │  RIGHT PANEL                             │
│  (w-72, fixed)   │  (flex-1)                                │
│                  │                                          │
│  [All folders ▾] │  No doc selected:                        │
│  🔍 Search...    │    "Select a document to view parse runs" │
│                  │                                          │
│  invoice.pdf     │  Doc selected:                           │
│  contract.pdf    │    Parse run timeline                    │
│  report.pdf ⏳   │    Re-parse button                       │
│  ...             │    Parsed document viewer                │
│                  │    Document text viewer                  │
│  [ Upload New  ] │                                          │
│  [ From Source ] │                                          │
└──────────────────┴──────────────────────────────────────────┘
```

**Left panel behaviour:**
- Shows all project documents (uploaded, processing, parsed) — full list, no parse-run filter
- Folder filter: compact dropdown above the search box, options are "All folders" + each folder
  name. Selecting a folder filters the list. Default: "All folders".
- Search filters by document title
- Selecting a document highlights it and loads the right panel
- "Upload New" opens `DocumentUploadDialog` (existing component, unchanged)
- "From Source" opens `SourceDocumentBrowser` sheet (new — see below)
- After upload or add-from-source: new document appears in the list and is auto-selected

**Right panel behaviour:**
- Empty state when no document is selected
- On document select: renders inline what the current Sheet/drawer shows:
  - `DocumentProbePanel`
  - Parse run timeline (`RunTimeline`) with delete + re-parse actions
  - `ParsedDocumentViewer`
  - `DocumentTextViewer`
- Re-parse dialog (`ReParseDialog`) continues to work the same way, triggered from the timeline
- Document actions (edit title/description, delete, download) move from table row menus into the
  right panel header as an actions menu (⋯ dropdown). `DocumentEditDialog` and
  `DocumentDeleteDialog` existing components are reused unchanged.

**Removed from the Parse page:**
- `FolderSidebar` — replaced by compact folder dropdown in left panel
- `BulkActionBar` — bulk-move no longer fits the two-panel layout; removed
- Sheet / `SheetContent` — replaced by the inline right panel

**Folder management (create, rename, delete folders):**
The `FolderSidebar` currently provides folder CRUD actions (create/edit/delete popovers). These
move to the folder dropdown in the left panel: a small gear/settings icon beside the dropdown
opens a simple folder management popover (same actions, same existing components).

### New component: `SourceDocumentBrowser`

**Path:** `frontend/src/components/documents/SourceDocumentBrowser.tsx`

A Sheet that opens from the "From Source" button in the left panel.

```
┌─────────────────────────────────────┐
│  Add from Source                 ✕  │
├─────────────────────────────────────┤
│  🔍 Search source documents...      │
│                                     │
│  ○  annual_report_2025.pdf   2.1MB  │
│  ○  contracts_batch.pdf      890KB  │
│  ○  invoices_q4.pdf          1.4MB  │
│  ...                                │
├─────────────────────────────────────┤
│  Parser:  [ LlamaParse ▾ ]          │
│  + parse options (collapsible)      │
├─────────────────────────────────────┤
│          [ Cancel ] [ Add & Parse ] │
└─────────────────────────────────────┘
```

**Behaviour:**
- Lists source documents not already present as project documents in the current project.
  Filtered client-side: `useSourceDocuments` results minus documents already in
  `useDocuments` for this project (matched by source document ID).
- Parse config reuses `ParseMethodSelector` + existing parser config sub-components
  (`LlamaParseConfig`, `LandingAIConfig`, `LocalPipelineConfig`) — same UI as `ReParseDialog`
- "Add & Parse" calls `POST /projects/{projectId}/documents/from-source`, sheet closes,
  new document appears in left panel list and is auto-selected
- "Cancel" closes without side effects

### New backend endpoint

```
POST /projects/{projectId}/documents/from-source
```

**Request body:**
```json
{
  "source_document_id": "uuid",
  "parser_type": "llamaparse | landingai | simple",
  "parse_config": {}
}
```

**Response:**
```json
{
  "document_id": "uuid",
  "parse_run_id": "uuid"
}
```

**Backend behaviour:**
1. Create a `Document` record in the project linking to the existing source file — no file transfer
2. Immediately kick off a parse run with the supplied parser type and config
3. Return both IDs so the frontend can auto-select and poll the document status

**Backend layers:** router → service → repository, following the standard data-flow pattern.

### Touch points summary

| File | Change |
|---|---|
| `frontend/src/config/navigation.ts` | Labels, hrefs, order |
| `frontend/src/App.tsx` | Route paths, breadcrumb handles |
| `frontend/src/pages/DocumentsPage.tsx` | Full two-panel refactor → rename to `ParsePage` |
| `frontend/src/pages/ExtractionPage.tsx` | `h1` heading only ("Extraction" → "Extract") |
| Any `navigate('/documents')` call-sites | Update to `/parse` |
| Any `navigate('/extraction')` call-sites | Update to `/extract` |
| `frontend/src/components/documents/SourceDocumentBrowser.tsx` | New |
| `backend/app/routers/documents.py` | New `from-source` route |
| `backend/app/services/documents.py` | New `create_from_source` method |
| `backend/app/repositories/documents.py` | New repository method |

---

## Workstream 2: Classify (TBD)

Document selection for classification will include an inline parse option matching the current
Extract flow — defaulting to the latest parse run config but allowing changes. Design to be
written after Workstream 1 ships.

---

## Workstream 3: Extract (TBD)

Design to be written after Workstream 2 ships.

---

## Backend impact summary

| Workstream | Backend changes |
|---|---|
| 1 — Parse | One new endpoint: `POST /projects/{projectId}/documents/from-source` |
| 2 — Classify | TBD |
| 3 — Extract | TBD |
