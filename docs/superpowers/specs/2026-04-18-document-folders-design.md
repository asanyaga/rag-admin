# Document Folders Design

**Date:** 2026-04-18
**Status:** Approved

## Summary

Add a folder feature to organize documents within a project. Folders are project-scoped, one level deep, and purely optional — documents without a folder are "unfiled" and always visible under "All Documents". No dedicated routes or pages; all folder management is inline within the documents page.

---

## Data Model

### New `folders` table

```sql
CREATE TABLE folders (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    tags        TEXT[] NOT NULL DEFAULT '{}',
    created_by  UUID NOT NULL REFERENCES users(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_folders_project_name UNIQUE (project_id, name)
);

CREATE INDEX ix_folders_project_id ON folders(project_id);
CREATE INDEX ix_folders_tags ON folders USING GIN(tags);
```

### Documents table — one new column

```sql
ALTER TABLE documents
  ADD COLUMN folder_id UUID REFERENCES folders(id) ON DELETE SET NULL;

CREATE INDEX ix_documents_folder_id ON documents(folder_id);
```

`ON DELETE SET NULL`: deleting a folder un-assigns its documents rather than cascade-deleting them.

No migration data seeding required. Existing documents have `folder_id = NULL` and appear under "All Documents".

---

## API

All folder endpoints are nested under the project:
`/api/v1/projects/{project_id}/folders`

### Folder endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/folders` | List all folders with document counts |
| `POST` | `/folders` | Create a folder |
| `PATCH` | `/folders/{folder_id}` | Update name, description, or tags |
| `DELETE` | `/folders/{folder_id}` | Delete folder (documents become unfiled) |

**`GET /folders` response:**
```json
[
  {
    "id": "uuid",
    "project_id": "uuid",
    "name": "Bank Statements",
    "description": "Monthly bank statements",
    "tags": ["finance", "banking"],
    "document_count": 12,
    "created_at": "...",
    "updated_at": "..."
  }
]
```

`document_count` is computed in the query so the sidebar can render counts without extra round-trips.

### Document move

Single document move reuses the existing `PATCH /documents/{id}` endpoint — `folder_id` is added to `DocumentUpdate`. Pass `folder_id: null` to remove a document from its folder.

Bulk move gets a dedicated endpoint to avoid N round-trips:

```
POST /api/v1/projects/{project_id}/documents/bulk-move
Body: { "document_ids": ["uuid", ...], "folder_id": "uuid | null" }
```

`folder_id: null` removes selected documents from their folder (unfiled).

### Document list filtering

`GET /documents` gains an optional `folder_id` query param:
- `folder_id={uuid}` — documents in that folder
- `folder_id=none` — unfiled documents (where `folder_id IS NULL`)
- omitted — all documents (existing default behaviour)

---

## Frontend

### Layout

`ProjectDocumentsPage` becomes a two-column layout:

```
┌──────────────────┬────────────────────────────────────┐
│  All Documents   │  [Bulk action bar - conditional]   │
│  (42)            │  ──────────────────────────────    │
│  ─────────────── │  ☐  Title        Folder   Status  │
│  FOLDERS    [+]  │  ☑  Q1 Report    Finance  Ready   │
│  📁 Bank  (12)   │  ☑  Receipt_01   —        Ready   │
│  📁 Receipts (8) │  ☐  Statement…   Bank     Ready   │
│  📁 Invoices (3) │                                    │
│  ─────────────── │                                    │
│  Unfiled    (19) │                                    │
└──────────────────┴────────────────────────────────────┘
```

Sidebar is fixed-width (~220px). Clicking a sidebar item filters the table. "All Documents" is always the top item and is selected by default.

### Folder CRUD — all inline, no new routes

**Create:** `[+]` button in sidebar header → inline text input appears at the bottom of the folder list → Enter to save, Escape to cancel.

**Edit:** hovering a folder reveals a `...` icon → dropdown with "Edit" and "Delete".
- "Edit" opens a `Popover` (`FolderEditPopover`) with name, description, and tags fields.
- Tags field accepts comma-separated free-form text, stored as `TEXT[]`.

**Delete:** "Delete" in the `...` dropdown shows an inline confirm popover:
> *"Delete folder? 12 documents will become unfiled."*
One click to confirm. Documents are not deleted.

### Multi-select & bulk move

- A checkbox column is added as the first column in `DocumentsTable`.
- When ≥1 row is checked, `BulkActionBar` slides in above the table:
  `[x] 3 selected  |  Move to folder ▾  |  Clear`
- "Move to folder" is a `DropdownMenu` listing all project folders plus "Remove from folder".
- Submitting calls `POST /documents/bulk-move`.

### Existing dialog changes

**`DocumentEditDialog`:** adds a "Folder" field — a `Select` populated from `useFolders`. Shows current folder; can be changed or cleared.

**`DocumentUploadDialog` / `DocumentUploadZone`:** adds an optional "Folder" select, defaulting to none (unfiled). Upload endpoint accepts optional `folder_id` form field.

### New components & hooks

| Name | Purpose |
|------|---------|
| `FolderSidebar` | Sidebar list with inline create, hover menu, selection state |
| `FolderEditPopover` | Popover form: name, description, tags |
| `BulkActionBar` | Slides in above table when rows selected; move + clear actions |
| `useFolders` | Fetch, create, update, delete folders with optimistic updates |

`useFolders` sits alongside `useDocuments` in `frontend/src/hooks/`. `FolderSidebar` and `BulkActionBar` are scoped to `frontend/src/components/documents/`.

---

## Backend layer structure

Follows the project's standard `router → service → repository` pattern:

```
backend/app/
├── models/folder.py
├── schemas/folder.py
├── repositories/folder_repository.py
├── services/folder_service.py
├── routers/folders.py
└── alembic/versions/XXXX_add_folders.py
```

`FolderService` raises exceptions (`NotFoundError`, `ConflictError`); the router catches and maps to HTTP responses. Bulk move logic lives in `DocumentService` (it already owns document mutation).

---

## Multi-folder hierarchy: notes & tradeoffs

The current design is one level deep and forward-compatible with nesting. Adding a second level requires:

```sql
ALTER TABLE folders ADD COLUMN parent_folder_id UUID REFERENCES folders(id) ON DELETE CASCADE;
```

Existing rows get `parent_folder_id = NULL` — no data migration.

### Query strategy options when nesting is added

| Approach | How it works | Pro | Con |
|---|---|---|---|
| **Recursive CTE** | `WITH RECURSIVE` traverses tree at query time | No schema change | Slow on deep trees; complex queries everywhere |
| **Materialized path** | Full path stored as string: `finance/bank/2024` | Fast prefix queries (`LIKE 'finance/%'`) | Rename-parent updates all children |
| **Closure table** | Separate table of all ancestor→descendant pairs | Fast reads, clean queries | Complex writes; extra table |

**Recommendation when nesting is needed:** materialized path. Simple to query, readable, and rename cost is acceptable at this scale.

### Real cost of nesting is UI, not storage

A second level requires sidebar expand/collapse, breadcrumbs in the table header, and drag-and-drop becomes an expectation. That's a deliberate UX investment. The one-level constraint in this iteration is the right call.

---

## Migration strategy

1. Create `folders` table (new migration).
2. Add `folder_id` (nullable) to `documents` (same or separate migration).
3. No data seeding — existing documents are implicitly unfiled.

---

## Out of scope for this iteration

- Folder reordering / drag-and-drop
- Nested folders (see hierarchy notes above)
- Folder-level permissions
- Folder document count in the documents table column (sidebar only)
- `DocumentsPage` (global cross-project view) — folders are project-scoped so this page is unaffected; no folder column or filter is added there
