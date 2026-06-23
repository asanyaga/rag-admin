# Source Documents — Design Spec

**Date:** 2026-06-23
**Status:** Approved

---

## Summary

Surface the existing `source_documents` table as a browsable tenant-level document library in the UI. Source documents are content-addressed (dedup by sha256) and persist independently of project documents — deleting a project document does not delete the underlying source document or its file.

The upload flow is unchanged. This feature adds:
1. A **Source Documents page** where users can browse the full document library.
2. An **"Add from Library"** action in Project Documents that creates a project document reference to an existing source document without re-uploading the file.
3. A rename of the existing "Documents" section to "Project Documents" for clarity.

---

## Context

### Existing data model

```
SourceDocument (tenant-level, content-addressed)
  id, sha256, filename, mime_type, byte_size, storage_uri, created_at

Document (project-scoped)
  id, project_id, source_document_id (FK → source_documents), source_type,
  source_identifier, title, description, status, ...
```

**Upload flow (unchanged):**
1. File is SHA-256 hashed; `ensure_source_document` upserts a `SourceDocument` row (dedup).
2. A `Document` row is created with `source_type="upload"`, `source_identifier=sha256`, `source_document_id=<id>`, `status="processing"`.
3. Background task runs CDM parse, sets `status="ready"`.

**Delete behaviour (unchanged):**
When a `Document` with `source_document_id` set is deleted, the `SourceDocument` row and its file are **not** removed — other projects may reference the same bytes.

---

## Backend

### New endpoint 1 — List source documents

```
GET /api/v1/source-documents
Auth: any authenticated user
```

Returns all source documents at tenant level (no project filter). Each item includes a computed `projectCount` — the number of distinct projects that have a `Document` referencing this `SourceDocument.id`.

**Response schema `SourceDocumentResponse`:**

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `sha256` | string | 64-char hex |
| `filename` | string \| null | Original filename |
| `mimeType` | string \| null | |
| `byteSize` | int \| null | Bytes |
| `createdAt` | datetime | |
| `projectCount` | int | Derived via join |

### New endpoint 2 — Add source document to project

```
POST /api/v1/projects/{project_id}/documents/from-source
Auth: authenticated user with access to project
```

**Request body:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `sourceDocumentId` | UUID | yes | Must exist in `source_documents` |
| `title` | string | no | Defaults to `source_document.filename` |
| `description` | string | no | |

**Behaviour:**
- Verifies project exists and user has access.
- Returns **409** if the project already has any `Document` with the same `source_document_id` (regardless of `source_type`).
- Creates a `Document` with:
  - `source_type = "library"`
  - `source_identifier = str(source_document_id)`
  - `source_document_id = <source_document_id>`
  - `status = "processing"`
- Dispatches the same background CDM parse as upload (`process_cdm_parsing`). The `SourceDocument.storage_uri` provides the file path — no file transfer needed.
- Returns `DocumentResponse` (202 Accepted).

### New files

| File | Purpose |
|---|---|
| `backend/app/schemas/source_document.py` | `SourceDocumentResponse` Pydantic schema |
| `backend/app/routers/source_documents.py` | Both endpoints above |

`source_documents` router is registered in `backend/app/main.py` under `/api/v1`.

---

## Frontend

### Navigation

`frontend/src/config/navigation.ts`:
- Rename label `"Documents"` → `"Project Documents"` (href `/documents` unchanged)
- Add new item `"Source Documents"` at `/source-documents` with a `Library` icon

### New page — Source Documents

**Route:** `/source-documents`
**File:** `frontend/src/pages/SourceDocumentsPage.tsx`

Table columns: filename, MIME type, size (human-readable), created date, "Used in N projects" badge.

Per-row action: **"Add to project"** — calls `POST /projects/{currentProject.id}/documents/from-source` with the source document's id and filename as the default title. Shows a toast on success/failure. Button is disabled (with tooltip) if no project is selected or the source doc is already in the current project.

No upload button on this page — uploading lives in Project Documents.

### Project Documents changes

**File:** `frontend/src/pages/DocumentsPage.tsx`
- Page heading renamed from "Documents" → "Project Documents"
- New **"Add from Library"** button in the header (alongside "Upload Document" and "Bulk Upload")
- Opens `SourceDocumentPickerDialog`

**File:** `frontend/src/components/documents/SourceDocumentPickerDialog.tsx`

A modal dialog containing:
- Searchable table of source documents **not yet linked to the current project** (filtered client-side by comparing each source document's `id` against the `sourceDocumentId` field of already-loaded project documents)
- Single-select row
- Title input pre-filled from the selected source document's filename
- Optional description input
- "Add to Project" confirm button — calls `POST /projects/{projectId}/documents/from-source`, closes on success, refreshes document list

### New frontend files

| File | Purpose |
|---|---|
| `frontend/src/types/sourceDocument.ts` | `SourceDocument` TypeScript type |
| `frontend/src/api/sourceDocuments.ts` | `listSourceDocuments()` API call; `addSourceDocumentToProject()` lives in `documents.ts` |
| `frontend/src/hooks/useSourceDocuments.ts` | `useSourceDocuments` hook (fetch + loading/error state) |
| `frontend/src/pages/SourceDocumentsPage.tsx` | New page |
| `frontend/src/components/documents/SourceDocumentPickerDialog.tsx` | Picker modal |

### Router changes

`frontend/src/App.tsx`:
- Add route `{ path: 'source-documents', element: <SourceDocumentsPage />, handle: { breadcrumb: 'Source Documents' } }`
- Update breadcrumb for `documents` path to `'Project Documents'`

---

## Constraints & Edge Cases

| Case | Behaviour |
|---|---|
| Source doc already in project (via upload or library) | 409 from backend; frontend shows toast error |
| No project selected on Source Documents page | "Add to project" button disabled |
| Source document has null filename | Title defaults to `"Untitled"` in picker and on Source Documents page |
| `byteSize` is null | Display "—" instead of a size |
| User deletes project document | Source document row remains visible in Source Documents page |

---

## Out of Scope

- Uploading files directly from the Source Documents page
- Deleting source documents (no endpoint or UI)
- Google Drive / external source ingestion (future `source_type` variants)
- Filtering source documents by MIME type or project
