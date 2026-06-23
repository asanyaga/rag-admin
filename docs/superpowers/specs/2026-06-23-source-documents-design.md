# Source Documents — Design Spec

**Date:** 2026-06-23
**Status:** Approved (iteration 1 scoped)

---

## Summary

Surface the existing `source_documents` table as a browsable tenant-level document library in the UI. Source documents are content-addressed (dedup by sha256) and persist independently of project documents — deleting a project document does not delete the underlying source document or its file.

The upload flow is unchanged. This iteration adds:
1. A **Source Documents page** where users can browse the full document library.
2. A rename of the existing "Documents" section to "Project Documents" for clarity.

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

### New endpoint — List source documents

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

### New files

| File | Purpose |
|---|---|
| `backend/app/schemas/source_document.py` | `SourceDocumentResponse` Pydantic schema |
| `backend/app/routers/source_documents.py` | List endpoint |

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

No upload button on this page — uploading lives in Project Documents.

### Project Documents changes

**File:** `frontend/src/pages/DocumentsPage.tsx`
- Page heading renamed from "Documents" → "Project Documents"

### New frontend files

| File | Purpose |
|---|---|
| `frontend/src/types/sourceDocument.ts` | `SourceDocument` TypeScript type |
| `frontend/src/api/sourceDocuments.ts` | `listSourceDocuments()` API call |
| `frontend/src/hooks/useSourceDocuments.ts` | `useSourceDocuments` hook (fetch + loading/error state) |
| `frontend/src/pages/SourceDocumentsPage.tsx` | New page |

### Router changes

`frontend/src/App.tsx`:
- Add route `{ path: 'source-documents', element: <SourceDocumentsPage />, handle: { breadcrumb: 'Source Documents' } }`
- Update breadcrumb for `documents` path to `'Project Documents'`

---

## Constraints & Edge Cases

| Case | Behaviour |
|---|---|
| Source document has null filename | Display "—" |
| `byteSize` is null | Display "—" instead of a size |
| User deletes project document | Source document row remains visible in Source Documents page |
| No source documents exist yet | Empty state with explanatory message |

---

## Out of Scope (this iteration)

- "Add from Library" action (adding a source document to a project without re-uploading) — deferred to iteration 2
- Uploading files directly from the Source Documents page
- Deleting source documents
- Google Drive / external source ingestion (future `source_type` variants)
- Filtering source documents by MIME type or project
