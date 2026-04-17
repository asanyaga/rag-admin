# Bulk Document Upload — Design Spec

**Date:** 2026-04-17  
**Status:** Approved  

---

## Overview

Add bulk document upload to the RAG admin app, allowing users to select up to 20 files at once and upload them to a project with a single parser configuration. The feature is optimised for onboarding speed: titles are auto-populated from filenames, parser type is set once for the whole batch, and each file processes independently so a single failure does not block the rest.

---

## Background

The current upload flow handles one file at a time. Each upload requires a title, description, parser type, and parse config, and returns `202 Accepted` while a background task handles parsing. The backend uses SHA-256 checksums for duplicate detection and `asyncio`-based background tasks for parsing via LlamaParse or a simple extractor.

LlamaParse recommends a concurrency cap of 5–10 simultaneous parse jobs for typical API accounts. The current adapter has no concurrency limiting, which is safe for single-file uploads but would cause rate limit errors under bulk load.

---

## Decisions

| Question | Decision | Rationale |
|---|---|---|
| Title per file | Auto-use filename | Bulk upload is about speed; filenames are good enough defaults; rename-after already supported |
| Failure handling | Per-file independent | Failures are isolated; rest of batch continues |
| Parser type | Single setting for whole batch | Consistent with speed goal; per-file parser adds UI complexity for minimal gain |
| Max files per batch | 20 | With semaphore of 5, processes in 4 LlamaParse waves; beyond this, UX degrades with no benefit |
| Implementation approach | New `POST /documents/bulk` endpoint | Enforces limits server-side; reuses all existing logic; clean API boundary |
| Retry in v1 | No | Keep scope tight; failed files require re-upload |
| Duplicate handling | Return existing record silently | User may not know file was already uploaded; not an error condition in bulk context |

---

## Architecture

No new DB models or migrations required. Changes are additive across existing layers.

```
Frontend
  DocumentUploadZone        ← add multiple prop (default false, no regression)
  BulkUploadQueue           ← new component: queue UI with per-file status
  useDocuments              ← add uploadDocumentsBulk()
  api/documents             ← add bulkUploadDocuments()

Backend
  POST /documents/bulk      ← new endpoint
  DocumentService           ← add initiate_bulk_upload()
  LlamaParseAdapter         ← add asyncio.Semaphore(5)
  (repositories, models, background tasks unchanged)
```

---

## Backend

### Endpoint: `POST /documents/bulk`

- **Auth:** Required (same as existing document endpoints)
- **Request:** `multipart/form-data`
  - `project_id: UUID`
  - `parser_type: str` (default: `"simple"`)
  - `parse_config: str | None` (JSON string)
  - `files: list[UploadFile]` (1–20 files)
- **Response:** `202 Accepted`
  ```json
  {
    "results": [
      { "filename": "doc.pdf", "document": { ...DocumentResponse } },
      { "filename": "bad.pdf", "error": "File exceeds 25MB limit" }
    ]
  }
  ```
- **Validation at endpoint:**
  - Reject entire request if `len(files) > 20` with `400 Bad Request`
  - Per-file: MIME type and size (25MB) — same rules as single upload
  - Invalid files returned with `error` field; valid files proceed

### `DocumentService.initiate_bulk_upload()`

Loops over the validated file list and calls the existing `initiate_upload()` per file with:
- `title` set to the original filename (stem only, without extension)
- `parser_type` and `parse_config` from the batch-level settings

Returns a mixed list of `DocumentResponse` or error dicts. The router then loops over the successful responses and registers the existing `process_document_parsing` / `process_document_extraction` background tasks — one per file — matching the pattern used in the single-file endpoint.

### LlamaParse Concurrency Cap

A class-level `asyncio.Semaphore(5)` added to `LlamaParseAdapter` wraps the `client.parsing.parse()` call. This caps concurrent LlamaParse jobs globally across all background tasks, not just within a single batch.

```python
_semaphore = asyncio.Semaphore(5)  # class-level

async def parse(self, file_path, config=None):
    async with self._semaphore:
        result = await self.client.parsing.parse(...)
```

---

## Frontend

### `DocumentUploadZone`

Add a `multiple: boolean` prop (default `false`). When `true`:
- File picker accepts multiple files
- Drag-drop accepts multiple files
- Calls `onBulkUpload(files: File[])` handler instead of `onUpload`

Existing single-file behaviour is unchanged when `multiple=false`.

### `BulkUploadQueue` (new component)

Rendered inside `DocumentUploadDialog` when multiple files are selected. Contains:

- File list showing filename and file size for each queued file
- Filename shown as greyed placeholder to indicate it will be used as the title
- Single parser type selector (applies to all files)
- Per-file status chip: `pending → uploading → processing → ready / failed`
- Per-file inline error message for validation or upload failures
- "Upload N files" submit button — disabled until at least one valid file is present
- Enforces 20-file cap with message "Maximum 20 files per batch" if exceeded; truncates to first 20

### `useDocuments.uploadDocumentsBulk()`

1. Calls `bulkUploadDocuments()` API function
2. Receives mixed results list
3. For each successful document response: starts existing polling on `document.id` (reuses current `status === 'processing'` polling — no new polling mechanism)
4. For each error response: marks that file `failed` in queue state immediately

### `api/documents.bulkUploadDocuments()`

Builds a single `FormData` with all files appended under the `files` key, posts to `POST /documents/bulk`. Returns the raw results list.

---

## Error Handling

### Frontend validation (before upload)
- Files exceeding 25MB: flagged immediately with a red chip, excluded from submission
- Unsupported MIME types: rejected at drop/select with inline message
- Batch exceeds 20 files: show "Maximum 20 files per batch", keep first 20

### API response
- Mixed results list: hook separates successes (start polling) from failures (mark failed in queue)
- Network-level failure (whole request fails): all files in queue marked `failed`, single error banner shown

### During processing
- Per-file `failed` status from polling: shown inline in queue, does not affect other files
- Duplicate detected server-side: existing document record returned silently (not treated as error)

---

## Testing

### Backend
- `backend/tests/routers/test_documents_router.py`
  - `POST /documents/bulk` with all valid files
  - Mixed valid/invalid files (partial success response)
  - More than 20 files (400 rejection)
  - All-invalid batch
- `backend/tests/services/test_document_service.py`
  - `initiate_bulk_upload()`: duplicate handling, per-file validation failures
- `backend/tests/adapters/test_llamaparse_adapter.py`
  - Semaphore limits concurrent calls to 5

### Frontend
- `frontend/src/hooks/useDocuments.test.ts`
  - `uploadDocumentsBulk()`: mixed success/failure responses, polling started for successful files only
- `frontend/src/components/documents/BulkUploadQueue.test.tsx`
  - File count cap enforcement
  - Per-file status rendering
  - Error state display

### Manual verification
- Drag-and-drop multi-file selection in the browser
- Visual queue state transitions during a live upload

---

## Out of Scope (v1)

- Per-file parser type selection
- Retry button for failed files
- Batch-level status record / aggregate progress polling
- Cancel batch in progress
- Progress percentage per file (status chips only)
