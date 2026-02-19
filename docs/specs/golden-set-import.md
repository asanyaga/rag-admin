# Golden Set Import Questions — Feature Spec

## Overview

Add the ability to import questions into a golden set from CSV or JSON files. Users upload a file containing queries (and optionally expected source documents + pages), the system parses and validates the data, shows a preview with errors/duplicates flagged, and on confirmation bulk-creates the queries.

---

## Supported Formats

### CSV

Fixed column schema. Headers are case-insensitive, order-independent.

| Column | Required | Description |
|--------|----------|-------------|
| `query_text` | Yes | The question text |
| `document_name` | No | Name of the expected source document (looked up by name) |
| `pages` | No | Comma-separated page numbers, e.g. `1,3,5` |

Example:
```csv
query_text,document_name,pages
"What is the refund policy?",Returns Policy v2,"1,2"
"How long does shipping take?",Shipping Guide,"4"
"What payment methods are accepted?",,
```

Notes:
- A single query can span multiple rows if it has multiple source documents — rows with the same `query_text` are grouped together, each row adding a source.
- If `document_name` is provided but `pages` is empty, the source is linked to the document with no page locator.

### JSON

```json
{
  "queries": [
    {
      "query_text": "What is the refund policy?",
      "sources": [
        { "document_name": "Returns Policy v2", "pages": [1, 2] }
      ]
    },
    {
      "query_text": "How long does shipping take?",
      "sources": [
        { "document_name": "Shipping Guide", "pages": [4] }
      ]
    },
    {
      "query_text": "What payment methods are accepted?"
    }
  ]
}
```

---

## Data Model Changes

### Backend — `SourceMethod` enum

Add `imported` to the existing enum:

```python
class SourceMethod(str, Enum):
    manual = "manual"
    auto_generated = "auto_generated"
    imported = "imported"  # NEW
```

Requires an Alembic migration to alter the enum column.

### Frontend — `SourceMethod` type

```typescript
type SourceMethod = 'manual' | 'auto_generated' | 'imported'
```

---

## API Design

Two-step flow: **parse** (preview) → **confirm** (import).

### Step 1: Parse / Preview

```
POST /projects/{project_id}/golden-sets/{gs_id}/import/parse
Content-Type: multipart/form-data

Body:
  file: <uploaded file>  (.csv or .json)
```

**Response** `200 OK`:

```json
{
  "valid_queries": [
    {
      "row": 1,
      "query_text": "What is the refund policy?",
      "sources": [
        {
          "document_name": "Returns Policy v2",
          "document_id": "uuid-123",
          "locator": { "type": "page", "pages": [1, 2] },
          "resolved": true
        }
      ],
      "is_duplicate": false
    }
  ],
  "errors": [
    {
      "row": 3,
      "query_text": "How do I contact support?",
      "error": "Document not found: 'Nonexistent Doc'"
    }
  ],
  "duplicates": [
    {
      "row": 5,
      "query_text": "What is the refund policy?",
      "existing_query_id": "uuid-456"
    }
  ],
  "summary": {
    "total_rows": 10,
    "valid_count": 7,
    "error_count": 2,
    "duplicate_count": 1
  }
}
```

**Behavior:**
- Parses the file based on detected format (CSV vs JSON, determined by file extension or content-type).
- Looks up each `document_name` against documents in the project. If not found, the **query is still valid** but the unresolved source is reported in `errors`. The query itself moves to `valid_queries` without that source.
- Checks `query_text` against existing queries in the golden set for exact-match duplicates.
- No data is persisted — this is a read-only preview.

### Step 2: Confirm / Import

```
POST /projects/{project_id}/golden-sets/{gs_id}/import/confirm
Content-Type: application/json

Body:
{
  "queries": [
    {
      "query_text": "What is the refund policy?",
      "sources": [
        {
          "document_id": "uuid-123",
          "locator": { "type": "page", "pages": [1, 2] }
        }
      ]
    }
  ]
}
```

The frontend sends only the queries the user has confirmed (after reviewing the preview). This lets the user deselect rows from the preview if desired.

**Response** `201 Created`:

```json
{
  "imported_count": 7,
  "queries": [ /* array of created QueryResponse objects */ ]
}
```

**Behavior:**
- Creates `GoldenSetQuery` records with `source_method = 'imported'` and `review_status = 'pending'`.
- Creates `GoldenSetSource` records for each resolved source.
- All inserts happen in a single database transaction.
- Re-checks for duplicates at confirm time (in case another user added queries between parse and confirm). Skips duplicates and includes them in the response.

---

## Frontend UX

### Entry Point

An **"Import" button** in the golden set editor page header, next to the existing "Auto-Generate" button. Uses an `Upload` (or `FileUp`) icon from Lucide.

### Import Modal — 3 steps

#### Step 1: Upload

- Drag-and-drop zone or file picker
- Accepts `.csv` and `.json` files
- Shows file name + size after selection
- "Parse" button → calls the parse endpoint
- Loading state while parsing

#### Step 2: Preview

- **Summary bar** at top: `7 valid · 2 errors · 1 duplicate`
- **Table** showing all parsed rows with columns:
  - Status icon (checkmark / warning / duplicate icon)
  - Query text (truncated with tooltip)
  - Sources (document name + pages, or "No sources")
  - Error message (if any)
- Rows are **color-coded**: valid (default), errors (red/muted), duplicates (yellow/muted)
- **Checkboxes** on valid rows — all checked by default, user can uncheck to exclude
- Error and duplicate rows are not selectable
- "Import N queries" button at bottom

#### Step 3: Result

- Success summary: `Imported 7 queries into "My Golden Set"`
- Breakdown if anything was skipped at confirm time
- "Done" button closes modal and refreshes the query list

### Template Download

A small **"Download template"** link in the upload step that downloads a sample CSV with headers and 1-2 example rows, so users know the expected format.

---

## Validation Rules

| Rule | Scope | Behavior |
|------|-------|----------|
| `query_text` is empty or whitespace | Row | Error — skip row |
| `query_text` exceeds 2000 chars | Row | Error — skip row |
| `document_name` provided but not found | Source only | Warning — query is valid, source is dropped |
| `pages` contains non-numeric values | Source only | Warning — query is valid, malformed source is dropped |
| Duplicate `query_text` in golden set | Row | Duplicate — reported separately, excluded from import |
| Duplicate `query_text` within the file | Row | Deduplicate — keep first occurrence, merge sources |
| File is empty or has no valid rows | File | Error — block import entirely |
| File exceeds 500 rows | File | Error — reject with message about row limit |
| Malformed CSV/JSON | File | Error — reject with parse error message |

---

## Error Handling

- **Parse failures** (malformed file, wrong extension): return `400` with a descriptive error message. Frontend shows the error inline in the upload step without advancing to preview.
- **Partial validation failures**: the parse response includes both `valid_queries` and `errors`. The frontend shows both. The user can proceed with valid rows only.
- **Confirm-time duplicate**: if a query was added between parse and confirm, it's silently skipped and reported in the confirm response.
- **Server error during confirm**: the entire transaction rolls back. Frontend shows an error with a "Retry" option.

---

## File Structure (Estimated)

### Backend
- `backend/app/schemas/golden_set.py` — new Pydantic models: `ImportParseResponse`, `ImportConfirmRequest`, `ImportConfirmResponse`
- `backend/app/routers/golden_sets.py` — two new endpoints: `parse_import`, `confirm_import`
- `backend/app/services/golden_set_import.py` — parsing logic (CSV + JSON), document name resolution, duplicate detection
- Alembic migration — add `imported` to `SourceMethod` enum

### Frontend
- `frontend/src/components/golden-sets/ImportModal.tsx` — the 3-step modal
- `frontend/src/api/golden-sets.ts` — two new API functions: `parseImport`, `confirmImport`
- `frontend/src/types/golden-set.ts` — new types for parse/confirm request/response, update `SourceMethod`

---

## Out of Scope (for now)

- Export / download golden set as CSV/JSON
- Importing `reference_answer` or `question_type` fields (can be added later by extending the schema)
- Drag-and-drop reordering of imported queries
- Import from URL or clipboard paste
