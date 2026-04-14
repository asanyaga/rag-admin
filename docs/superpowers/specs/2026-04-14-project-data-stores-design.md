# Project Data Stores — Design Spec

## Overview

Project data stores give each project its own user-defined relational tables in PostgreSQL. Users create stores, define schemas (columns + types), populate them via manual entry, CSV import, or agent export, and use them as lookup tables or output targets within agent pipelines.

### First Increment Scope

- **Store type:** PostgreSQL tables only (rdb). No CSV-file, JSON, or document DB store types.
- **Schema changes:** Add or remove columns only. No column rename or type change.
- **CSV import:** All-or-nothing. No partial imports.
- **Export tool:** Enhanced to write to a data store. No new tools (categorize is out of scope).

---

## Data Model

### `project_data_stores` table (metadata)

| Column            | Type          | Notes                                    |
|-------------------|---------------|------------------------------------------|
| id                | UUID          | PK, auto-generated                       |
| project_id        | UUID          | FK to projects, CASCADE delete            |
| name              | VARCHAR(255)  | Display name, e.g. "Budget Items"        |
| description       | VARCHAR(500)  | Optional                                 |
| table_name        | VARCHAR(100)  | Auto-generated, e.g. `pd_a1b2c3d4`      |
| schema_definition | JSONB         | Array of column definitions              |
| row_count         | INTEGER       | Cached count, updated on insert/delete   |
| created_at        | TIMESTAMPTZ   |                                          |
| updated_at        | TIMESTAMPTZ   |                                          |

**Constraints:**
- UNIQUE(project_id, name) — no duplicate store names per project
- UNIQUE(table_name) — globally unique physical table names

### `schema_definition` structure

```json
[
  {"name": "item_name", "type": "text", "nullable": false, "description": "Item description"},
  {"name": "quantity", "type": "integer", "nullable": false, "description": ""},
  {"name": "price", "type": "numeric", "nullable": true, "description": "Unit price"}
]
```

**Allowed column types:** `text`, `integer`, `numeric`, `boolean`, `timestamptz`

These map 1:1 to PostgreSQL types. Intentionally small set — covers extraction schema types and common lookup table needs without exposing the full PostgreSQL type system.

### Dynamic tables (actual data)

Each data store gets a real PostgreSQL table created at runtime:

```sql
CREATE TABLE pd_a1b2c3d4 (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  item_name TEXT NOT NULL,
  quantity INTEGER NOT NULL,
  price NUMERIC,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
```

Every dynamic table automatically includes `id`, `created_at`, and `updated_at` columns. User-defined columns go in between.

**Table naming:** `pd_` prefix + 8-character hex from UUID. Auto-generated, never user-provided. Users interact with the display name only.

---

## Backend Architecture

### Repository — `ProjectDataStoreRepository`

Two categories of operations:

**Metadata operations** (SQLAlchemy ORM against `project_data_stores`):
- `create(project_id, name, description, schema_definition)` → INSERT metadata row
- `get_by_id(id, project_id)` → SELECT with project scoping
- `list_by_project(project_id)` → SELECT all stores for a project
- `update(id, project_id, name?, description?, schema_definition?)` → UPDATE metadata
- `delete(id, project_id)` → DELETE metadata row

**Dynamic table operations** (raw SQL via SQLAlchemy `text()`):
- `create_table(table_name, schema_definition)` → CREATE TABLE
- `drop_table(table_name)` → DROP TABLE
- `alter_table(table_name, columns_to_add, columns_to_drop)` → ALTER TABLE ADD/DROP COLUMN
- `insert_rows(table_name, schema_definition, rows)` → parameterized INSERT
- `get_rows(table_name, limit, offset)` → SELECT with pagination
- `get_row(table_name, row_id)` → SELECT by id
- `update_row(table_name, row_id, data)` → parameterized UPDATE
- `delete_row(table_name, row_id)` → DELETE by id
- `count_rows(table_name)` → SELECT COUNT(*)
- `bulk_insert(table_name, schema_definition, rows)` → batch INSERT for CSV import

**SQL safety:**
- Table and column names validated against allowlist pattern: `^[a-z][a-z0-9_]{0,62}$`
- Column types validated against the allowed type set
- All values are parameterized — never interpolated into SQL strings
- No user-provided strings go directly into DDL/DML

### Service — `ProjectDataStoreService`

Orchestrates metadata + dynamic table operations:

- **create_store** — validates schema definition, creates metadata row, executes CREATE TABLE
- **update_store** — if schema changed: diffs old vs new columns, runs ALTER TABLE (ADD/DROP COLUMN), updates metadata
- **delete_store** — drops the dynamic table, deletes metadata row
- **import_csv** — parses CSV server-side, validates column types against schema, calls bulk_insert, updates row_count. Rejects entire batch on any validation error.
- **Row CRUD** — resolves table_name from store id, delegates to repository

Schema change constraints (first increment):
- Adding columns: allowed (new columns must be nullable or have a default)
- Removing columns: allowed (data in dropped columns is lost)
- Renaming columns: not supported
- Changing column types: not supported

### Router — `/api/v1/projects/{project_id}/data-stores`

| Method | Path                       | Description                        |
|--------|----------------------------|------------------------------------|
| POST   | `/`                        | Create data store                  |
| GET    | `/`                        | List data stores for project       |
| GET    | `/{store_id}`              | Get store metadata                 |
| PATCH  | `/{store_id}`              | Update store (name, desc, schema)  |
| DELETE | `/{store_id}`              | Delete store + underlying table    |
| GET    | `/{store_id}/rows`         | List rows (paginated)              |
| POST   | `/{store_id}/rows`         | Insert single row                  |
| GET    | `/{store_id}/rows/{row_id}`| Get single row                     |
| PATCH  | `/{store_id}/rows/{row_id}`| Update row                         |
| DELETE | `/{store_id}/rows/{row_id}`| Delete row                         |
| POST   | `/{store_id}/import`       | CSV file upload + bulk import      |

All endpoints scoped to current user via project ownership check.

---

## Export Tool Enhancement

The existing export tool (`backend/app/services/agent/tools/export.py`) is upgraded from a stub to write data into a project data store.

### Node Configuration

When adding an export node in the agent composer, the user selects a target data store:

```json
{
  "data_store_id": "uuid-of-target-store"
}
```

The composer UI presents a dropdown of the project's data stores.

### Export Node Behavior

1. Reads current state from the agent graph (data flowing through the pipeline)
2. Resolves the target data store and its schema_definition
3. Maps state fields to table columns by **exact name match**
4. Inserts the matched fields as a row into the dynamic table
5. Updates the cached row_count on the metadata record
6. Passes state through with `exported=True`

**Field mapping rules:**
- State field name matches column name → value is inserted
- State field has no matching column → ignored (silently skipped)
- Required column has no matching state field → export fails with a descriptive error
- Nullable column has no matching state field → inserted as NULL

---

## Frontend Architecture

### Navigation & Routing

Data stores are a project-level resource, independent of any specific agent. They get their own nav entry:

```
Projects
├── Documents
├── Extraction
├── Data Stores    ← new
├── Agents
└── Evaluation
```

Route: `/projects/{projectId}/data-stores`

### Pages

**DataStoresPage** (`/projects/{projectId}/data-stores`)
- Lists all data stores for the project (name, description, row count, created date)
- "Create Data Store" button opens create dialog
- Click a store navigates to detail page

**DataStoreDetailPage** (`/projects/{projectId}/data-stores/{storeId}`)
- Header: store name, description, edit/delete actions
- Schema section: displays column definitions (name, type, nullable)
- Data grid: paginated table rendering columns dynamically from schema_definition
- Row actions: "Add Row" button, "Import CSV" button, per-row edit/delete
- Inline editing in the data grid

### Components

- **DataStoreCreateDialog** — name, description, schema editor. Optional "seed from extraction schema" dropdown that pre-fills columns from an existing extraction schema. Schema is fully editable after seeding.
- **DataStoreEditDialog** — edit name, description, add/remove columns
- **DataStoreSchemaEditor** — reusable column list editor: add, remove, reorder columns. Each column has name, type (dropdown), nullable (checkbox), description fields. Column names are auto-normalized to lowercase with underscores (e.g., "Item Name" → "item_name") to match PostgreSQL naming constraints.
- **DataGrid** — generic schema-driven table with pagination, inline editing, row delete. Columns render based on schema_definition. Input types adapt to column type (text input, number input, checkbox for boolean, date picker for timestamptz).
- **CsvImportDialog** — file upload, header preview, column mapping, import trigger

### Hooks & API

- `useDataStores()` — list, create, update, delete stores for current project
- `useDataStoreRows(storeId)` — paginated row listing, single row CRUD, CSV import
- `api/data-stores.ts` — HTTP wrappers for all `/data-stores` endpoints

### CSV Import UX Flow

1. User clicks "Import CSV" on the data store detail page
2. CsvImportDialog opens — user selects a CSV file
3. Frontend parses the CSV header and first 5 rows for preview (client-side, for UX only)
4. Column mapping table:
   - Left: CSV column headers
   - Right: dropdown of data store columns (auto-matched by name)
   - Unmapped CSV columns are skipped
   - Required store columns without a mapping show a warning
5. User confirms → file uploaded to `POST /{store_id}/import`
6. Backend parses the full CSV, validates types against schema, inserts rows
7. Success: returns inserted row count, UI refreshes grid
8. Failure: entire batch rejected, error indicates which row/column failed

CSV parsing is authoritative on the backend (Python `csv` module). Frontend preview is purely for UX.

---

## Out of Scope (Future Increments)

- CSV, JSON, and document DB store types
- Column rename and type change
- Partial CSV imports (insert valid rows, skip invalid)
- Categorize agent tool
- Data store queries/filtering in the grid UI
- Cross-store joins or views
- Row-level permissions
- Data store versioning or audit log
