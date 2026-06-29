# Parse UX Refactor — Design Spec

**Date:** 2026-06-29
**Status:** Approved

## Overview

Refactor the documents/parse UX to make the parse step explicit in the nav and across the pipeline.
Three rename/reorder changes plus a shared document picker component that unifies how Classify and
Extract select their input document.

Delivered as three independent workstreams: Parse → Classify → Extract.

---

## Workstream 1: Parse (Nav + Rename)

Pure frontend refactor. No new components, no backend changes.

### Route changes

| Old path | New path |
|---|---|
| `/documents` | `/parse` |
| `/documents/:documentId/runs/:runId` | `/parse/:documentId/runs/:runId` |
| `/extraction` | `/extract` |

Update `App.tsx` path strings directly. No redirects needed — internal tool with no external link consumers.

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

### Touch points

- `frontend/src/config/navigation.ts` — labels, hrefs, order
- `frontend/src/App.tsx` — route `path` strings and breadcrumb `handle` labels
- `frontend/src/pages/DocumentsPage.tsx` — page `h1` heading ("Project Documents" → "Parse")
- `frontend/src/pages/ExtractionPage.tsx` — page `h1` heading ("Extraction" → "Extract")
- `frontend/src/components/layout/Breadcrumbs.tsx` — verify breadcrumb labels render from route handles (no hardcoding)
- Any `navigate('/documents')` or `navigate('/extraction')` call-sites in other pages (e.g. `DocumentsPage` `handleExtract` navigates to `/extraction?documentId=...` → update to `/extract`)

---

## Workstream 2: Classify — DocumentPickerPanel + SourceDocumentBrowser + Backend

### New component: `DocumentPickerPanel`

**Path:** `frontend/src/components/documents/DocumentPickerPanel.tsx`

Self-contained left panel. Replaces the ad-hoc document list in `NewClassificationRunPage`.
Also used by Workstream 3 (Extract).

```ts
interface DocumentPickerPanelProps {
  projectId: string
  selectedDocumentId: string | null
  onSelect: (documentId: string) => void
}
```

**Layout (fixed width ~w-72, full height, flex column):**

```
┌─────────────────────────────┐
│  🔍 Search documents...      │
├─────────────────────────────┤
│  ✅ Invoice Q1.pdf           │  ← parsed, selectable
│  ✅ Contract_2026.pdf        │
│  ⏳ Report_draft.pdf         │  ← parsing, greyed out, auto-selects when ready
│  ...                        │
├─────────────────────────────┤
│  [ Upload New ]             │
│  [ Add from Source ]        │
└─────────────────────────────┘
```

**Document list rules:**
- Shows project documents that have at least one `succeeded` or `partial` parse run, plus any
  documents currently in `processing` status (so in-progress work is visible)
- Documents still processing are greyed out and non-interactive
- Polling: documents with `processing` status poll every 3 seconds; when status flips to `ready`,
  the document auto-selects (calls `onSelect(documentId)`)

**"Upload New" button:**
- Opens `DocumentUploadDialog` (existing component, no changes)
- After successful upload the new document appears in the list as processing and auto-selects

**"Add from Source" button:**
- Opens `SourceDocumentBrowser` sheet (see below)
- After successful add+parse the new document appears in the list as processing and auto-selects

### New component: `SourceDocumentBrowser`

**Path:** `frontend/src/components/documents/SourceDocumentBrowser.tsx`

A Sheet that opens from the "Add from Source" button.

**Layout:**

```
┌─────────────────────────────────────┐
│  Add from Source                 ✕  │
├─────────────────────────────────────┤
│  🔍 Search source documents...      │
│                                     │
│  ○  annual_report_2025.pdf   2.1MB  │
│  ○  contracts_batch.pdf      890KB  │
│  ...                                │
├─────────────────────────────────────┤
│  Parser:  [ LlamaParse ▾ ]          │
│  + parse options (collapsible)      │
├─────────────────────────────────────┤
│           [ Cancel ] [ Add & Parse ]│
└─────────────────────────────────────┘
```

**Behaviour:**
- Lists source documents not already present as project documents in the current project
  (filtered client-side using the existing `useSourceDocuments` hook + the project's document list)
- Parse config reuses `ParseMethodSelector` + existing parser config sub-components
  (`LlamaParseConfig`, `LandingAIConfig`, `LocalPipelineConfig`) — same UI as `ReParseDialog`
- "Add & Parse" calls `POST /projects/{projectId}/documents/from-source`, closes the sheet, and
  triggers the auto-select + polling flow in `DocumentPickerPanel`
- "Cancel" closes without any side effects

### `NewClassificationRunPage` refactor

The existing 3-step wizard (select doc → select parse run → configure) is replaced by a
two-panel layout:

- **Left panel:** `DocumentPickerPanel`
- **Right panel:** classifier config form (collapsing steps 2+3 — parse run selection is no longer
  needed because `DocumentPickerPanel` guarantees only docs with completed parse runs are selectable)

The right panel is empty/disabled with a prompt ("Select a document to configure") until a document
is selected. Once selected, the `ClassificationRunForm` renders immediately.

The right panel auto-selects the latest `succeeded` or `partial` parse run for the chosen document
(same pattern `ExtractionPage` uses with `latestViableRun`) and passes that `parseRunId` when
submitting the classification run. The user never has to pick a parse run manually.

Routing stays the same: `/classify/new`.

### New backend endpoint

```
POST /projects/{projectId}/documents/from-source
```

**Request body:**
```json
{
  "source_document_id": "uuid",
  "parser_type": "llamaparse | landingai | simple",
  "parse_config": { }
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
1. Create a `Document` record in the project, linking to the existing source file (no file transfer)
2. Immediately kick off a parse run with the supplied parser type and config
3. Return both IDs so the frontend can poll the document status

**Backend layers:** router → service → repository, following the standard data-flow pattern.

---

## Workstream 3: Extract — Adopt DocumentPickerPanel

**Only change:** `ExtractionPage` (`/extract`) replaces the existing
`frontend/src/components/extraction/DocumentSelector.tsx` with `DocumentPickerPanel`.

`DocumentSelector` is deleted once it has no remaining consumers.

The rest of `ExtractionPage` (schema manager, extraction form, history panel) is unchanged.

---

## What is NOT changing

- `DocumentsPage` (Parse page) internal functionality — folder sidebar, bulk actions, document
  table, re-parse sheet. Only the name and route change.
- `ClassificationPage` (the runs list at `/classify`) — unchanged.
- All backend endpoints except the one new endpoint added in Workstream 2.
- Source Documents page — unchanged.

---

## Backend impact summary

| Workstream | Backend changes |
|---|---|
| 1 — Parse | None |
| 2 — Classify | One new endpoint: `POST /projects/{projectId}/documents/from-source` |
| 3 — Extract | None |
