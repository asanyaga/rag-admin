# Export Tool Enhancement — Field Mapping, Array Fan-Out & Source Metadata

## Overview

Enhance the export tool to support explicit field mapping with dot-path notation, automatic array fan-out for nested extraction results, and a system-managed `source_metadata` column on all data store rows for traceability. Add an Export Playground page for testing field mappings in isolation.

### Scope

- **`source_metadata`** — system JSONB column on all dynamic tables, auto-populated by insertion method
- **`field_mapping`** — explicit source→destination column config on the export tool, replacing name-matching
- **Array fan-out** — dot-paths referencing arrays produce multiple rows automatically
- **Export Playground** — standalone page to build mappings, preview fan-out, and test exports
- **Config validation** — reject unsupported patterns (nested arrays) at config time, not runtime

### Out of Scope

- Nested array support beyond one level (e.g., `items.subitems.name`)
- Build-time validation of source paths against extraction schemas
- Integration into the Agent Composer UI (playground components will be reused later)

---

## 1. `source_metadata` System Column

### Column Definition

Every dynamic data store table gets a new system column:

```sql
source_metadata JSONB NULL DEFAULT NULL
```

Added alongside the existing system columns: `id`, `created_at`, `updated_at`.

### Auto-Population by Insertion Method

The system populates `source_metadata` automatically. Users never provide it directly.

| Source | Value |
|---|---|
| Pipeline export | `{"source": "pipeline", "run_id": "...", "document_id": "...", "extraction_result_id": "..."}` |
| CSV import | `{"source": "csv_import", "filename": "...", "imported_at": "..."}` |
| Manual entry | `{"source": "manual", "created_at": "..."}` |
| Export playground | `{"source": "playground", "created_at": "..."}` |

### Rules

- `source_metadata` is a **reserved column name** — users cannot create a user-defined column with this name
- It is **not part of `schema_definition`** — it's a system column like `id`
- It is **read-only** in the data grid — displayed as an expandable element, not an editable cell
- Existing data stores get the column via migration; existing rows get `null`

### Migration Strategy

A new Alembic migration that:

1. Adds `source_metadata JSONB NULL` to the `create_table()` DDL template (for new stores)
2. Queries `project_data_stores` for all existing `table_name` values and runs `ALTER TABLE "{table_name}" ADD COLUMN source_metadata JSONB NULL` for each

---

## 2. Export Tool `field_mapping` Config

### Current Behavior

The export node does naive name-matching: it takes keys from the extraction state and matches them to column names in the data store. No user control, no nested data support.

### New Config Schema

```json
{
  "data_store_id": "uuid",
  "field_mapping": {
    "receipt_date": "receipt_date",
    "vendor": "vendor",
    "items.description": "item_description",
    "items.price": "item_price",
    "items.units": "item_units"
  }
}
```

**Left side** = source dot-path into the extraction result. **Right side** = destination column name in the data store.

### Dot-Path Rules

- **Scalar path** (`vendor`) — resolves to a top-level field in state. Copied to every output row.
- **Array path** (`items.description`) — first segment (`items`) resolves to an array in state; second segment (`description`) resolves to a field within each element. Produces one output row per element.
- **Max depth: one dot.** Paths like `items.subitems.name` (2+ dots) are rejected at config validation time with: "Nested array paths are not supported — only `array.field` is allowed."

### Mapping Behavior

- **Unmapped source fields** are silently dropped — the user picks what gets exported
- **Unmapped destination columns** get `null` if nullable, or cause a validation error if not nullable (same behavior as manual row insert)
- **Empty mapping** is a validation error — at least one mapping is required
- **Flat extractions** work identically: `{"vendor": "vendor", "total": "total"}` produces one row, same as current behavior but explicit

### Config Validation

Validation runs when the agent config is saved/updated with an export node — not at runtime:

1. All dot-paths have at most one dot
2. All destination column names exist in the target data store's `schema_definition`
3. All non-nullable destination columns have a source mapping
4. No duplicate destination columns
5. `field_mapping` is not empty

Validation endpoint: existing agent config save endpoint. The export tool registration exposes the updated `config_schema`, and the save logic validates against it.

---

## 3. Array Fan-Out Logic

### Example

**Extraction state:**
```json
{
  "receipt_date": "2026-04-15",
  "vendor": "Costco",
  "items": [
    {"description": "Bread", "price": 2.50, "units": 1},
    {"description": "Milk", "price": 1.20, "units": 2}
  ]
}
```

**Field mapping:**
```json
{
  "receipt_date": "receipt_date",
  "vendor": "vendor",
  "items.description": "item_description",
  "items.price": "item_price",
  "items.units": "item_units"
}
```

**Output: 2 rows:**

| receipt_date | vendor | item_description | item_price | item_units |
|---|---|---|---|---|
| 2026-04-15 | Costco | Bread | 2.50 | 1 |
| 2026-04-15 | Costco | Milk | 1.20 | 2 |

### Algorithm

1. **Parse mappings** — separate into scalar mappings (`key` → no dot) and array mappings (`array.field` → has dot)
2. **Group array mappings** by array name — `items.description`, `items.price`, `items.units` all belong to the `items` array
3. **Resolve arrays** — for each array name, look up the value in state. Must be a `list`. If it's not a list, treat it as a single-element list (graceful degradation for optional arrays).
4. **Compute rows:**
   - **No arrays:** single row from scalar mappings only
   - **One array:** one row per element; scalars copied to every row
   - **Multiple arrays:** cartesian product across all arrays; scalars copied to every row
5. **Map fields** — for each row, apply the field mapping to produce `{destination_col: value}` pairs
6. **Attach `source_metadata`** — same value for all rows from a single export

### Edge Cases

| Case | Behavior |
|---|---|
| Empty array (`items: []`) | Zero rows exported. Not an error. |
| Array element missing a mapped field | `null` for that column |
| Source path resolves to `null` | `null` for that column |
| Source path doesn't exist in state | `null` for that column |
| State field is an array but not referenced by any mapping | Ignored (treated as any other unmapped field) |

### Module

New file: `backend/app/services/agent/field_mapper.py`

Two public functions:

```python
def validate_field_mapping(field_mapping: dict[str, str], schema_definition: list[dict]) -> list[str]:
    """Validate a field mapping against a data store schema.
    Returns a list of error messages (empty = valid)."""

def flatten_to_rows(state: dict, field_mapping: dict[str, str]) -> list[dict]:
    """Apply field mapping to extraction state, producing flattened rows.
    Handles scalar fields, array fan-out, and cartesian products."""
```

Pure functions, no database access, independently testable.

---

## 4. Export Node Changes

### Current Flow

```
export_node(state) → name-match fields → insert single row
```

### New Flow

```
export_node(state) → read field_mapping from config → flatten_to_rows() → bulk_insert with source_metadata
```

### Updated `export_node` Logic

1. Read `data_store_id` and `field_mapping` from `state["node_config"]`
2. If no `data_store_id`, skip (same as today)
3. Look up the data store
4. Call `flatten_to_rows(state, field_mapping)` to get the list of row dicts
5. If zero rows, return success with `rows_exported: 0`
6. Build `source_metadata`:
   ```python
   {
       "source": "pipeline",
       "run_id": state.get("run_id"),
       "document_id": state.get("document_id"),
       "extraction_result_id": state.get("extraction_result_id"),
   }
   ```
7. Bulk-insert all rows with `source_metadata`
8. Update row count
9. Return state with `exported: True`, `rows_exported: len(rows)`

### Updated `config_schema`

```python
config_schema={
    "type": "object",
    "properties": {
        "data_store_id": {
            "type": "string",
            "format": "uuid",
            "description": "Target data store to export rows into",
        },
        "field_mapping": {
            "type": "object",
            "additionalProperties": {"type": "string"},
            "description": "Source dot-path → destination column name mapping",
        },
    },
    "required": ["data_store_id"],
}
```

### Backward Compatibility

The current export tool has `field_mapping` as not required — existing agent configs that don't have it would break. To handle this:

- If `field_mapping` is missing or empty, fall back to the current name-matching behavior
- Log a deprecation warning when name-matching is used
- This lets existing agents keep working while new ones use explicit mappings

---

## 5. Backend Changes to Data Store Layer

### Repository (`data_store_repository.py`)

**`create_table()`** — add to DDL:
```sql
source_metadata JSONB NULL
```

**`insert_row()`** — accept optional `source_metadata` parameter:
```python
async def insert_row(self, table_name, schema_definition, data, source_metadata=None) -> dict:
```
If provided, include `source_metadata` in the INSERT column list and params.

**`bulk_insert()`** — same: accept optional `source_metadata` applied to all rows in the batch.

### Service (`data_store_service.py`)

**`_validate_schema()`** — add `source_metadata` to reserved names set:
```python
reserved = {"id", "created_at", "updated_at", "source_metadata"}
```

**`insert_row()`** — populate source_metadata:
```python
source_metadata = {"source": "manual", "created_at": datetime.utcnow().isoformat()}
```

**`import_csv()`** — populate source_metadata:
```python
source_metadata = {"source": "csv_import", "filename": filename, "imported_at": datetime.utcnow().isoformat()}
```
Note: the CSV import endpoint needs to pass the filename through to the service.

**`_row_to_response()`** — include `source_metadata` in the response (pull from raw row dict).

### Schemas (`schemas/data_store.py`)

**`DataStoreRowResponse`** — add field:
```python
source_metadata: dict | None = Field(None, alias="sourceMetadata")
```

### Router (`routers/data_stores.py`)

**CSV import endpoint** — pass filename to service:
```python
result = await service.import_csv(store_id, project_id, csv_content, mapping, filename=file.filename)
```

---

## 6. Export Playground Page

### Purpose

A standalone page for testing field mappings in isolation — pick a data store, paste sample extraction data, build the mapping, preview the fan-out, and optionally execute the export. Components built here will be reused in the Agent Composer UI later.

### Route and Navigation

- **Route:** `/export` 
- **Nav item:** `{ label: 'Export', href: '/export', icon: ArrowUpFromLine, activeColor: 'border-l-emerald-500' }` — placed after Data Stores in the sidebar
- Uses `currentProject` from ProjectContext (same as other pages)

### Page Layout

Four sections, top to bottom:

**Section 1 — Destination**
- Data store dropdown (fetches from `useDataStores` hook)
- On selection, loads the store's `schemaDefinition` and displays destination columns as badges

**Section 2 — Source Data**
- JSON textarea for pasting sample extraction state
- "Format" button to pretty-print
- Syntax validation on blur — red border + error message if invalid JSON
- Presets dropdown (optional, nice-to-have): "Receipt", "Invoice" with example JSON structures

**Section 3 — Field Mapping Editor**
- Two-column layout: source path (left) ↔ destination column (right)
- "Add Mapping" button adds a row
- Source path: text input with dot-path notation (e.g., `items.description`)
- Destination column: dropdown populated from the selected data store's schema
- Auto-detect: button that parses the source JSON and suggests mappings by matching field names to column names (same heuristic as current CSV import auto-match)
- Visual indicator on source paths that reference arrays (e.g., a small badge "array" next to `items.description`)
- Validation: shows inline errors for duplicate destinations, paths with 2+ dots, missing required columns

**Section 4 — Preview & Execute**
- **Preview button** — calls `flatten_to_rows()` logic client-side (or via a preview API endpoint) and renders the result as a read-only table matching the data store schema. Shows row count: "3 rows will be exported"
- **Execute button** — disabled until preview has been run. Inserts the previewed rows into the data store with `source_metadata: {"source": "playground", "created_at": "..."}`. Shows success toast with row count.
- **Clear button** — resets the form

### Reusable Components

These components should be built for reuse in the Agent Composer:

| Component | Props | Reuse Target |
|---|---|---|
| `FieldMappingEditor` | `sourceJson`, `destinationColumns`, `mapping`, `onChange` | Agent Composer export node config |
| `FanOutPreview` | `rows`, `columns` | Agent Composer test/debug panel |

### API

**Preview endpoint (new):**
```
POST /api/v1/projects/{project_id}/data-stores/{store_id}/preview-export
Body: { "source_data": {...}, "field_mapping": {...} }
Response: { "rows": [...], "row_count": 3 }
```

This runs `flatten_to_rows()` server-side and returns the result without inserting. Validates the mapping against the store schema.

**Execute endpoint (new):**
```
POST /api/v1/projects/{project_id}/data-stores/{store_id}/execute-export
Body: { "source_data": {...}, "field_mapping": {...} }
Response: { "rows_imported": 3 }
```

This calls `flatten_to_rows()`, then `bulk_insert()` with `source_metadata: {"source": "playground", "created_at": "..."}`. Same as preview but commits the rows.

---

## 7. Frontend Changes to Existing Components

### `types/dataStore.ts`

Add to `DataStoreRow`:
```typescript
sourceMetadata: Record<string, unknown> | null
```

### `components/data-stores/DataGrid.tsx`

- Add a "Source" column (last position, before the actions column)
- Render as a compact badge showing `source_metadata.source` value (e.g., "pipeline", "csv_import", "manual")
- On hover or click: expandable popover/tooltip showing the full JSON
- If `null`: show "—"
- Column is not editable

---

## 8. File Structure

### New Files
- `backend/app/services/agent/field_mapper.py` — flatten_to_rows + validate_field_mapping
- `frontend/src/pages/ExportPlaygroundPage.tsx` — playground page
- `frontend/src/components/export/FieldMappingEditor.tsx` — reusable mapping editor
- `frontend/src/components/export/FanOutPreview.tsx` — preview table
- `backend/alembic/versions/xxxx_add_source_metadata_column.py` — migration

### Modified Files
- `backend/app/repositories/data_store_repository.py` — source_metadata in DDL, insert, bulk_insert
- `backend/app/services/data_store_service.py` — populate source_metadata, pass filename
- `backend/app/schemas/data_store.py` — DataStoreRowResponse.source_metadata
- `backend/app/routers/data_stores.py` — pass filename, add preview-export endpoint
- `backend/app/services/agent/tools/export.py` — updated config_schema
- `backend/app/services/agent/nodes.py` — rewritten export_node
- `frontend/src/types/dataStore.ts` — sourceMetadata field
- `frontend/src/components/data-stores/DataGrid.tsx` — source column
- `frontend/src/config/navigation.ts` — Export nav item
- `frontend/src/App.tsx` — Export route
