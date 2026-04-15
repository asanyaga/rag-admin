# Export Tool Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit field mapping with array fan-out to the export tool, a `source_metadata` traceability column to all data store rows, and an Export Playground page for testing mappings.

**Architecture:** The core logic lives in a new pure-function module (`field_mapper.py`) that transforms extraction state + field mapping → flat rows. The export node, playground endpoints, and service layer all call into it. `source_metadata` is a system JSONB column auto-populated by insertion method.

**Tech Stack:** Python/FastAPI, SQLAlchemy (async), Alembic, React/TypeScript, shadcn/ui, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-04-15-export-field-mapping-design.md`

---

## File Structure

### Backend — New Files
- `backend/app/services/agent/field_mapper.py` — `validate_field_mapping()` + `flatten_to_rows()` pure functions
- `backend/tests/services/test_field_mapper.py` — unit tests for field mapper
- `backend/alembic/versions/xxxx_add_source_metadata_column.py` — migration for source_metadata

### Backend — Modified Files
- `backend/app/repositories/data_store_repository.py` — `source_metadata` in DDL, `insert_row()`, `bulk_insert()`
- `backend/app/services/data_store_service.py` — auto-populate `source_metadata`, add `source_metadata` to reserved names, pass filename for CSV
- `backend/app/schemas/data_store.py` — `DataStoreRowResponse.source_metadata`, new `ExportPreviewRequest`/`ExportPreviewResponse`/`ExportExecuteResponse` schemas
- `backend/app/routers/data_stores.py` — pass filename to service, add `preview-export` and `execute-export` endpoints
- `backend/app/services/agent/tools/export.py` — updated `config_schema` with `field_mapping`
- `backend/app/services/agent/nodes.py` — rewritten `export_node` using `flatten_to_rows()`

### Frontend — New Files
- `frontend/src/components/export/FieldMappingEditor.tsx` — reusable mapping editor
- `frontend/src/components/export/FanOutPreview.tsx` — preview table
- `frontend/src/pages/ExportPlaygroundPage.tsx` — playground page

### Frontend — Modified Files
- `frontend/src/types/dataStore.ts` — `sourceMetadata` on `DataStoreRow`, new export types
- `frontend/src/api/dataStores.ts` — `previewExport()`, `executeExport()` API wrappers
- `frontend/src/components/data-stores/DataGrid.tsx` — read-only "Source" column
- `frontend/src/config/navigation.ts` — Export nav item
- `frontend/src/App.tsx` — Export route

---

## Task 1: Field Mapper — Pure Functions + Tests

**Files:**
- Create: `backend/app/services/agent/field_mapper.py`
- Create: `backend/tests/services/test_field_mapper.py`

This is the core logic — pure functions with no database access. TDD.

- [ ] **Step 1: Write tests for `validate_field_mapping`**

```python
# backend/tests/services/test_field_mapper.py
"""Unit tests for field_mapper — pure functions, no DB needed."""
import pytest

from app.services.agent.field_mapper import validate_field_mapping, flatten_to_rows


# ── validate_field_mapping ────────────────────────────────────────

SAMPLE_SCHEMA = [
    {"name": "receipt_date", "type": "text", "nullable": False},
    {"name": "vendor", "type": "text", "nullable": False},
    {"name": "item_description", "type": "text", "nullable": True},
    {"name": "item_price", "type": "numeric", "nullable": True},
    {"name": "item_units", "type": "integer", "nullable": True},
]


def test_validate_valid_mapping():
    mapping = {
        "receipt_date": "receipt_date",
        "vendor": "vendor",
        "items.description": "item_description",
    }
    errors = validate_field_mapping(mapping, SAMPLE_SCHEMA)
    assert errors == []


def test_validate_empty_mapping():
    errors = validate_field_mapping({}, SAMPLE_SCHEMA)
    assert any("at least one" in e.lower() for e in errors)


def test_validate_nested_array_path():
    mapping = {"items.subitems.name": "item_description"}
    errors = validate_field_mapping(mapping, SAMPLE_SCHEMA)
    assert any("nested" in e.lower() for e in errors)


def test_validate_unknown_destination():
    mapping = {"vendor": "nonexistent_column"}
    errors = validate_field_mapping(mapping, SAMPLE_SCHEMA)
    assert any("nonexistent_column" in e for e in errors)


def test_validate_duplicate_destination():
    mapping = {"vendor": "receipt_date", "date": "receipt_date"}
    errors = validate_field_mapping(mapping, SAMPLE_SCHEMA)
    assert any("duplicate" in e.lower() for e in errors)


def test_validate_missing_required_destination():
    # receipt_date and vendor are NOT nullable, only mapping one of them
    mapping = {"vendor": "vendor"}
    errors = validate_field_mapping(mapping, SAMPLE_SCHEMA)
    assert any("receipt_date" in e for e in errors)
```

- [ ] **Step 2: Write tests for `flatten_to_rows`**

Add to the same test file:

```python
# ── flatten_to_rows ────��──────────────────────────────────────────

def test_flatten_scalar_only():
    state = {"receipt_date": "2026-04-15", "vendor": "Costco"}
    mapping = {"receipt_date": "receipt_date", "vendor": "vendor"}
    rows = flatten_to_rows(state, mapping)
    assert len(rows) == 1
    assert rows[0] == {"receipt_date": "2026-04-15", "vendor": "Costco"}


def test_flatten_single_array():
    state = {
        "receipt_date": "2026-04-15",
        "vendor": "Costco",
        "items": [
            {"description": "Bread", "price": 2.50, "units": 1},
            {"description": "Milk", "price": 1.20, "units": 2},
        ],
    }
    mapping = {
        "receipt_date": "receipt_date",
        "vendor": "vendor",
        "items.description": "item_description",
        "items.price": "item_price",
        "items.units": "item_units",
    }
    rows = flatten_to_rows(state, mapping)
    assert len(rows) == 2
    assert rows[0] == {
        "receipt_date": "2026-04-15",
        "vendor": "Costco",
        "item_description": "Bread",
        "item_price": 2.50,
        "item_units": 1,
    }
    assert rows[1] == {
        "receipt_date": "2026-04-15",
        "vendor": "Costco",
        "item_description": "Milk",
        "item_price": 1.20,
        "item_units": 2,
    }


def test_flatten_empty_array():
    state = {"vendor": "Costco", "items": []}
    mapping = {"vendor": "vendor", "items.description": "item_description"}
    rows = flatten_to_rows(state, mapping)
    assert len(rows) == 0


def test_flatten_multiple_arrays_cartesian():
    state = {
        "vendor": "Costco",
        "items": [{"name": "A"}, {"name": "B"}],
        "taxes": [{"rate": 0.08}, {"rate": 0.10}],
    }
    mapping = {
        "vendor": "vendor",
        "items.name": "item_name",
        "taxes.rate": "tax_rate",
    }
    rows = flatten_to_rows(state, mapping)
    assert len(rows) == 4  # 2 items × 2 taxes
    vendors = {r["vendor"] for r in rows}
    assert vendors == {"Costco"}
    item_names = [r["item_name"] for r in rows]
    assert item_names.count("A") == 2
    assert item_names.count("B") == 2


def test_flatten_missing_field_in_element():
    state = {
        "items": [
            {"description": "Bread", "price": 2.50},
            {"description": "Milk"},  # no price
        ],
    }
    mapping = {
        "items.description": "item_description",
        "items.price": "item_price",
    }
    rows = flatten_to_rows(state, mapping)
    assert len(rows) == 2
    assert rows[0]["item_price"] == 2.50
    assert rows[1]["item_price"] is None


def test_flatten_missing_source_path():
    state = {"vendor": "Costco"}
    mapping = {"vendor": "vendor", "total": "total_amount"}
    rows = flatten_to_rows(state, mapping)
    assert len(rows) == 1
    assert rows[0]["vendor"] == "Costco"
    assert rows[0]["total_amount"] is None


def test_flatten_non_list_treated_as_single():
    """If a dot-path's first segment is not a list, wrap it as [value]."""
    state = {"item": {"description": "Solo", "price": 5.00}}
    mapping = {"item.description": "item_description", "item.price": "item_price"}
    rows = flatten_to_rows(state, mapping)
    assert len(rows) == 1
    assert rows[0] == {"item_description": "Solo", "item_price": 5.00}
```

- [ ] **Step 3: Run tests to verify they fail**

Run:
```bash
cd backend && uv run python -m pytest tests/services/test_field_mapper.py -v -o "addopts="
```

Expected: FAIL — `field_mapper` module doesn't exist yet.

- [ ] **Step 4: Implement `field_mapper.py`**

```python
# backend/app/services/agent/field_mapper.py
"""Pure functions for field mapping and array fan-out.

Transforms extraction state + field mapping config into flat rows
suitable for bulk insert into a data store.
"""
from itertools import product
from collections import defaultdict


def validate_field_mapping(
    field_mapping: dict[str, str],
    schema_definition: list[dict],
) -> list[str]:
    """Validate a field mapping against a data store schema.

    Returns a list of error messages. Empty list = valid.
    """
    errors: list[str] = []

    if not field_mapping:
        errors.append("Field mapping must contain at least one entry")
        return errors

    col_names = {col["name"] for col in schema_definition}
    required_cols = {col["name"] for col in schema_definition if not col.get("nullable", True)}

    # Check each mapping entry
    seen_destinations: dict[str, str] = {}
    for source_path, dest_col in field_mapping.items():
        # Max one dot
        if source_path.count(".") > 1:
            errors.append(
                f"Nested array paths are not supported — only 'array.field' is allowed: '{source_path}'"
            )

        # Destination must exist in schema
        if dest_col not in col_names:
            errors.append(
                f"Destination column '{dest_col}' does not exist in the data store schema"
            )

        # No duplicate destinations
        if dest_col in seen_destinations:
            errors.append(
                f"Duplicate destination column '{dest_col}' — mapped from both "
                f"'{seen_destinations[dest_col]}' and '{source_path}'"
            )
        seen_destinations[dest_col] = source_path

    # All non-nullable columns must have a mapping
    mapped_destinations = set(field_mapping.values())
    for req_col in required_cols:
        if req_col not in mapped_destinations:
            errors.append(
                f"Required column '{req_col}' has no source mapping"
            )

    return errors


def flatten_to_rows(
    state: dict,
    field_mapping: dict[str, str],
) -> list[dict]:
    """Apply field mapping to extraction state, producing flattened rows.

    Scalar source paths (no dot) are copied to every row.
    Array source paths (one dot: 'array.field') fan out — one row per element.
    Multiple arrays produce a cartesian product.
    """
    # Separate scalar vs array mappings
    scalar_mappings: dict[str, str] = {}  # source_key -> dest_col
    array_mappings: dict[str, list[tuple[str, str]]] = defaultdict(list)  # array_name -> [(field, dest_col)]

    for source_path, dest_col in field_mapping.items():
        if "." in source_path:
            array_name, field_name = source_path.split(".", 1)
            array_mappings[array_name].append((field_name, dest_col))
        else:
            scalar_mappings[source_path] = dest_col

    # Build the scalar part (same for every row)
    scalar_row: dict = {}
    for source_key, dest_col in scalar_mappings.items():
        scalar_row[dest_col] = state.get(source_key)

    # If no arrays, return a single row
    if not array_mappings:
        return [scalar_row]

    # Resolve each array from state
    resolved_arrays: dict[str, list[dict]] = {}
    for array_name in array_mappings:
        value = state.get(array_name)
        if value is None:
            resolved_arrays[array_name] = []
        elif isinstance(value, list):
            resolved_arrays[array_name] = value
        else:
            # Non-list treated as single-element list
            resolved_arrays[array_name] = [value]

    # If any array is empty, the fan-out produces zero rows
    for arr in resolved_arrays.values():
        if len(arr) == 0:
            return []

    # Compute cartesian product across all arrays
    array_names = list(resolved_arrays.keys())
    array_values = [resolved_arrays[name] for name in array_names]
    combinations = list(product(*array_values))

    rows: list[dict] = []
    for combo in combinations:
        row = dict(scalar_row)  # copy scalars
        for i, array_name in enumerate(array_names):
            element = combo[i]
            for field_name, dest_col in array_mappings[array_name]:
                if isinstance(element, dict):
                    row[dest_col] = element.get(field_name)
                else:
                    row[dest_col] = None
        rows.append(row)

    return rows
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
cd backend && uv run python -m pytest tests/services/test_field_mapper.py -v -o "addopts="
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/agent/field_mapper.py backend/tests/services/test_field_mapper.py
git commit -m "feat: add field_mapper with flatten_to_rows and validation"
```

---

## Task 2: Migration — `source_metadata` Column

**Files:**
- Create: `backend/alembic/versions/e6f7a8b9c0d1_add_source_metadata_column.py`
- Modify: `backend/app/repositories/data_store_repository.py`

- [ ] **Step 1: Create the migration**

```python
# backend/alembic/versions/e6f7a8b9c0d1_add_source_metadata_column.py
"""add_source_metadata_column

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-04-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add source_metadata to all existing dynamic tables
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT table_name FROM project_data_stores"))
    for row in result:
        table_name = row[0]
        op.add_column(table_name, sa.Column('source_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT table_name FROM project_data_stores"))
    for row in result:
        table_name = row[0]
        op.drop_column(table_name, 'source_metadata')
```

- [ ] **Step 2: Update `create_table()` DDL in repository**

In `backend/app/repositories/data_store_repository.py`, find the `create_table` method and add `source_metadata` after the `updated_at` column:

Replace this line:
```python
        columns.append("updated_at TIMESTAMPTZ NOT NULL DEFAULT now()")
```

With:
```python
        columns.append("updated_at TIMESTAMPTZ NOT NULL DEFAULT now()")
        columns.append("source_metadata JSONB NULL")
```

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/e6f7a8b9c0d1_add_source_metadata_column.py backend/app/repositories/data_store_repository.py
git commit -m "feat: add source_metadata JSONB column to dynamic tables"
```

---

## Task 3: Repository — `source_metadata` in Insert/Bulk-Insert

**Files:**
- Modify: `backend/app/repositories/data_store_repository.py`

- [ ] **Step 1: Update `insert_row()` signature and implementation**

Replace the current `insert_row` method (lines 174-191) with:

```python
    async def insert_row(self, table_name: str, schema_definition: list[dict], data: dict, source_metadata: dict | None = None) -> dict:
        """Insert a single row and return it."""
        if not TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"Invalid table name: {table_name}")

        col_names = [col["name"] for col in schema_definition if col["name"] in data]
        if not col_names:
            raise ValueError("No valid columns to insert")

        # Add source_metadata if provided
        if source_metadata is not None:
            col_names.append("source_metadata")
            data = {**data, "source_metadata": source_metadata}

        placeholders = ", ".join(f":{name}" for name in col_names)
        col_list = ", ".join(f'"{name}"' for name in col_names)
        sql = f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders}) RETURNING *'

        params = {name: data[name] for name in col_names}
        result = await self.session.execute(text(sql), params)
        await self.session.commit()
        row = result.mappings().one()
        return dict(row)
```

- [ ] **Step 2: Update `bulk_insert()` signature and implementation**

Replace the current `bulk_insert` method (lines 251-272) with:

```python
    async def bulk_insert(self, table_name: str, schema_definition: list[dict], rows: list[dict], source_metadata: dict | None = None) -> int:
        """Bulk insert rows. Returns count of inserted rows."""
        if not TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"Invalid table name: {table_name}")
        if not rows:
            return 0

        col_names = [col["name"] for col in schema_definition]

        # Add source_metadata column if provided
        if source_metadata is not None:
            col_names = col_names + ["source_metadata"]

        placeholders = ", ".join(f":{name}" for name in col_names)
        col_list = ", ".join(f'"{name}"' for name in col_names)
        sql = f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders})'

        params_list = []
        for row in rows:
            params = {name: row.get(name) for name in [c["name"] for c in schema_definition]}
            if source_metadata is not None:
                params["source_metadata"] = source_metadata
            params_list.append(params)

        for params in params_list:
            await self.session.execute(text(sql), params)

        await self.session.commit()
        return len(params_list)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/repositories/data_store_repository.py
git commit -m "feat: add source_metadata parameter to insert_row and bulk_insert"
```

---

## Task 4: Service Layer — Auto-Populate `source_metadata`

**Files:**
- Modify: `backend/app/services/data_store_service.py`
- Modify: `backend/app/schemas/data_store.py`

- [ ] **Step 1: Add `source_metadata` to reserved names**

In `backend/app/services/data_store_service.py`, find the `_validate_schema` method and replace the `reserved` set:

```python
        reserved = {"id", "created_at", "updated_at", "source_metadata"}
```

- [ ] **Step 2: Add `datetime` import at top of service file**

The file already imports from `uuid`. Add `datetime` to the imports section at the top of `backend/app/services/data_store_service.py`:

```python
from datetime import datetime, timezone
```

- [ ] **Step 3: Update `insert_row()` to populate `source_metadata`**

In the `insert_row` method, change the call to `self.repo.insert_row` to include `source_metadata`:

Replace:
```python
        self._validate_row_data(data, store.schema_definition)
        row = await self.repo.insert_row(store.table_name, store.schema_definition, data)
```

With:
```python
        self._validate_row_data(data, store.schema_definition)
        source_metadata = {"source": "manual", "created_at": datetime.now(tz=timezone.utc).isoformat()}
        row = await self.repo.insert_row(store.table_name, store.schema_definition, data, source_metadata=source_metadata)
```

- [ ] **Step 4: Update `import_csv()` signature and implementation**

Change the method signature to accept `filename`:

Replace:
```python
    async def import_csv(self, store_id: UUID, project_id: UUID, csv_content: str, column_mapping: dict[str, str]) -> CsvImportResponse:
```

With:
```python
    async def import_csv(self, store_id: UUID, project_id: UUID, csv_content: str, column_mapping: dict[str, str], filename: str | None = None) -> CsvImportResponse:
```

Then change the `bulk_insert` call at the end of the method. Replace:

```python
        count = await self.repo.bulk_insert(store.table_name, store.schema_definition, rows)
```

With:
```python
        source_metadata = {
            "source": "csv_import",
            "filename": filename or "unknown",
            "imported_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        count = await self.repo.bulk_insert(store.table_name, store.schema_definition, rows, source_metadata=source_metadata)
```

- [ ] **Step 5: Update `_row_to_response()` to include `source_metadata`**

Replace the `_row_to_response` method:

```python
    def _row_to_response(self, row: dict, schema_definition: list[dict]) -> DataStoreRowResponse:
        """Convert a raw row dict to a DataStoreRowResponse."""
        col_names = {col["name"] for col in schema_definition}
        data = {k: v for k, v in row.items() if k in col_names}
        return DataStoreRowResponse(
            id=row["id"],
            data=data,
            source_metadata=row.get("source_metadata"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
```

- [ ] **Step 6: Update `DataStoreRowResponse` schema**

In `backend/app/schemas/data_store.py`, add `source_metadata` to `DataStoreRowResponse`:

Replace:
```python
class DataStoreRowResponse(BaseModel):
    """Schema for a single row in a data store."""
    id: UUID
    data: dict
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)
```

With:
```python
class DataStoreRowResponse(BaseModel):
    """Schema for a single row in a data store."""
    id: UUID
    data: dict
    source_metadata: dict | None = Field(None, alias="sourceMetadata")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)
```

- [ ] **Step 7: Update CSV import router to pass filename**

In `backend/app/routers/data_stores.py`, in the `import_csv` endpoint, replace:

```python
        return await service.import_csv(store_id, project_id, csv_text, mapping)
```

With:
```python
        return await service.import_csv(store_id, project_id, csv_text, mapping, filename=file.filename)
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/data_store_service.py backend/app/schemas/data_store.py backend/app/routers/data_stores.py
git commit -m "feat: auto-populate source_metadata on insert and CSV import"
```

---

## Task 5: Export Schemas + Preview/Execute Endpoints

**Files:**
- Modify: `backend/app/schemas/data_store.py`
- Modify: `backend/app/routers/data_stores.py`
- Modify: `backend/app/services/data_store_service.py`

- [ ] **Step 1: Add export request/response schemas**

At the end of `backend/app/schemas/data_store.py`, add:

```python
class ExportPreviewRequest(BaseModel):
    """Request body for preview-export endpoint."""
    source_data: dict = Field(..., alias="sourceData")
    field_mapping: dict[str, str] = Field(..., alias="fieldMapping")

    model_config = ConfigDict(populate_by_name=True)


class ExportPreviewResponse(BaseModel):
    """Response from preview-export endpoint."""
    rows: list[dict]
    row_count: int = Field(..., alias="rowCount")

    model_config = ConfigDict(populate_by_name=True)


class ExportExecuteResponse(BaseModel):
    """Response from execute-export endpoint."""
    rows_imported: int = Field(..., alias="rowsImported")

    model_config = ConfigDict(populate_by_name=True)
```

- [ ] **Step 2: Add service methods for preview and execute**

At the end of the row operations section in `backend/app/services/data_store_service.py` (before the `# ── Helpers` comment), add:

```python
    # ── Export operations ────────���────────────────────────────────────

    async def preview_export(
        self, store_id: UUID, project_id: UUID, source_data: dict, field_mapping: dict[str, str]
    ) -> dict:
        """Preview export: validate mapping and return flattened rows without inserting."""
        from app.services.agent.field_mapper import validate_field_mapping, flatten_to_rows

        store = await self.repo.get_by_id(store_id, project_id)
        if not store:
            raise NotFoundError(f"Data store {store_id} not found")

        errors = validate_field_mapping(field_mapping, store.schema_definition)
        if errors:
            raise ValidationError("Field mapping errors: " + "; ".join(errors))

        rows = flatten_to_rows(source_data, field_mapping)
        return {"rows": rows, "row_count": len(rows)}

    async def execute_export(
        self, store_id: UUID, project_id: UUID, source_data: dict, field_mapping: dict[str, str]
    ) -> int:
        """Execute export: validate, flatten, and insert rows."""
        from app.services.agent.field_mapper import validate_field_mapping, flatten_to_rows

        store = await self.repo.get_by_id(store_id, project_id)
        if not store:
            raise NotFoundError(f"Data store {store_id} not found")

        errors = validate_field_mapping(field_mapping, store.schema_definition)
        if errors:
            raise ValidationError("Field mapping errors: " + "; ".join(errors))

        rows = flatten_to_rows(source_data, field_mapping)
        if not rows:
            return 0

        source_metadata = {
            "source": "playground",
            "created_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        count = await self.repo.bulk_insert(store.table_name, store.schema_definition, rows, source_metadata=source_metadata)
        await self._refresh_row_count(store)
        return count
```

- [ ] **Step 3: Add router endpoints**

At the end of `backend/app/routers/data_stores.py`, add the new import and endpoints. First update the imports:

Replace:
```python
from app.schemas.data_store import (
    DataStoreCreate,
    DataStoreUpdate,
    DataStoreResponse,
    DataStoreRowResponse,
    DataStoreRowsResponse,
    CsvImportResponse,
)
```

With:
```python
from app.schemas.data_store import (
    DataStoreCreate,
    DataStoreUpdate,
    DataStoreResponse,
    DataStoreRowResponse,
    DataStoreRowsResponse,
    CsvImportResponse,
    ExportPreviewRequest,
    ExportPreviewResponse,
    ExportExecuteResponse,
)
```

Then add at the end of the file, after the CSV import endpoint:

```python
# ���─ Export Preview/Execute ────────────────────────────────────────

@router.post("/{store_id}/preview-export", response_model=ExportPreviewResponse)
async def preview_export(
    project_id: UUID,
    store_id: UUID,
    data: ExportPreviewRequest,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Preview export: validate mapping and return flattened rows without inserting."""
    try:
        return await service.preview_export(store_id, project_id, data.source_data, data.field_mapping)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{store_id}/execute-export", response_model=ExportExecuteResponse)
async def execute_export(
    project_id: UUID,
    store_id: UUID,
    data: ExportPreviewRequest,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Execute export: validate, flatten, and insert rows into the data store."""
    try:
        count = await service.execute_export(store_id, project_id, data.source_data, data.field_mapping)
        return ExportExecuteResponse(rows_imported=count)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/data_store.py backend/app/services/data_store_service.py backend/app/routers/data_stores.py
git commit -m "feat: add preview-export and execute-export endpoints"
```

---

## Task 6: Export Node — Rewrite with Field Mapping

**Files:**
- Modify: `backend/app/services/agent/tools/export.py`
- Modify: `backend/app/services/agent/nodes.py`

- [ ] **Step 1: Update export tool `config_schema`**

Replace the entire contents of `backend/app/services/agent/tools/export.py`:

```python
"""Export tool — write pipeline data to a project data store."""
from app.services.agent.nodes import export_node
from app.services.agent.tools import ToolDefinition, register_tool

register_tool(ToolDefinition(
    slug="export",
    name="Export",
    category="export",
    description="Export data to a project data store",
    input_keys=["reviewed_data", "extracted_data"],
    output_keys=["exported", "rows_exported"],
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
    },
    node_fn=export_node,
))
```

- [ ] **Step 2: Rewrite `export_node`**

Replace the entire `export_node` function in `backend/app/services/agent/nodes.py`:

```python
async def export_node(state: dict) -> dict:
    """Export data to a project data store.

    Supports explicit field_mapping with dot-path notation and array fan-out.
    Falls back to name-matching if no field_mapping is configured.
    """
    from app.database import AsyncSessionLocal
    from app.repositories.data_store_repository import DataStoreRepository
    from app.services.agent.field_mapper import flatten_to_rows

    logger.info("export_node: exporting data")

    config = state.get("node_config", {})
    data_store_id = config.get("data_store_id")

    if not data_store_id:
        logger.warning("export_node: no data_store_id configured, marking as exported only")
        return {
            **state,
            "exported": True,
            "rows_exported": 0,
            "current_step": "done",
        }

    # Use reviewed_data if available (post-review), otherwise extracted_data
    data = state.get("reviewed_data") or state.get("extracted_data") or {}

    async with AsyncSessionLocal() as session:
        repo = DataStoreRepository(session)

        store = await repo.get_by_id(data_store_id, state.get("project_id"))
        if not store:
            return {
                **state,
                "error": f"Data store {data_store_id} not found",
                "exported": False,
                "rows_exported": 0,
                "current_step": "failed",
            }

        field_mapping = config.get("field_mapping")

        if field_mapping:
            # Explicit mapping with fan-out support
            rows = flatten_to_rows(data, field_mapping)
        else:
            # Backward compat: name-match fields to columns
            logger.warning(
                "export_node: no field_mapping configured, falling back to name-matching "
                "(deprecated — configure field_mapping for explicit control)"
            )
            col_names = {col["name"] for col in store.schema_definition}
            row_data = {k: v for k, v in data.items() if k in col_names}
            rows = [row_data] if row_data else []

        if not rows:
            return {
                **state,
                "exported": True,
                "rows_exported": 0,
                "current_step": "done",
            }

        source_metadata = {
            "source": "pipeline",
            "run_id": str(state.get("run_id", "")),
            "document_id": str(state.get("document_id", "")),
            "extraction_result_id": str(state.get("extraction_result_id", "")),
        }

        count = await repo.bulk_insert(
            store.table_name, store.schema_definition, rows, source_metadata=source_metadata
        )
        new_count = await repo.count_rows(store.table_name)
        await repo.update_row_count(store.id, new_count)

    return {
        **state,
        "exported": True,
        "rows_exported": count,
        "current_step": "done",
    }
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/agent/tools/export.py backend/app/services/agent/nodes.py
git commit -m "feat: rewrite export_node with field_mapping and array fan-out"
```

---

## Task 7: Frontend — `sourceMetadata` Type + DataGrid Source Column

**Files:**
- Modify: `frontend/src/types/dataStore.ts`
- Modify: `frontend/src/components/data-stores/DataGrid.tsx`

- [ ] **Step 1: Add `sourceMetadata` to `DataStoreRow` type**

In `frontend/src/types/dataStore.ts`, replace the `DataStoreRow` interface:

```typescript
export interface DataStoreRow {
  id: string
  data: Record<string, unknown>
  sourceMetadata: Record<string, unknown> | null
  createdAt: string
  updatedAt: string
}
```

- [ ] **Step 2: Add export types**

At the end of `frontend/src/types/dataStore.ts`, add:

```typescript
export interface ExportPreviewRequest {
  sourceData: Record<string, unknown>
  fieldMapping: Record<string, string>
}

export interface ExportPreviewResponse {
  rows: Record<string, unknown>[]
  rowCount: number
}

export interface ExportExecuteResponse {
  rowsImported: number
}
```

- [ ] **Step 3: Update DataGrid to show Source column**

In `frontend/src/components/data-stores/DataGrid.tsx`, add imports at the top:

```typescript
import { Badge } from '@/components/ui/badge'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
```

Add a "Source" header after the "Created" header. Replace:

```typescript
                <th className="text-left py-3 px-4 font-medium text-sm">Created</th>
                <th className="text-right py-3 px-4 font-medium text-sm w-20">Actions</th>
```

With:

```typescript
                <th className="text-left py-3 px-4 font-medium text-sm">Created</th>
                <th className="text-left py-3 px-4 font-medium text-sm">Source</th>
                <th className="text-right py-3 px-4 font-medium text-sm w-20">Actions</th>
```

Add a Source cell in each row. After the "Created" cell (the `<td>` with `formatDistanceToNow`), add:

```typescript
                  <td className="py-2 px-4 text-sm">
                    {row.sourceMetadata ? (
                      <Popover>
                        <PopoverTrigger asChild>
                          <Badge
                            variant="outline"
                            className="cursor-pointer text-xs font-normal"
                          >
                            {(row.sourceMetadata as Record<string, unknown>).source as string || '—'}
                          </Badge>
                        </PopoverTrigger>
                        <PopoverContent className="w-80">
                          <pre className="text-xs whitespace-pre-wrap">
                            {JSON.stringify(row.sourceMetadata, null, 2)}
                          </pre>
                        </PopoverContent>
                      </Popover>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/dataStore.ts frontend/src/components/data-stores/DataGrid.tsx
git commit -m "feat: add sourceMetadata to DataStoreRow and Source column to DataGrid"
```

---

## Task 8: Frontend — API Wrappers for Export

**Files:**
- Modify: `frontend/src/api/dataStores.ts`

- [ ] **Step 1: Add export API functions**

At the end of `frontend/src/api/dataStores.ts`, add a new section. First update the type imports:

Replace:
```typescript
import type {
  DataStore,
  DataStoreCreate,
  DataStoreUpdate,
  DataStoreRow,
  DataStoreRowsResponse,
  CsvImportResponse,
} from '@/types/dataStore'
```

With:
```typescript
import type {
  DataStore,
  DataStoreCreate,
  DataStoreUpdate,
  DataStoreRow,
  DataStoreRowsResponse,
  CsvImportResponse,
  ExportPreviewRequest,
  ExportPreviewResponse,
  ExportExecuteResponse,
} from '@/types/dataStore'
```

Then add at the end of the file:

```typescript
// ── Export Preview/Execute ────────────────────────────────────────

export async function previewExport(
  projectId: string,
  storeId: string,
  data: ExportPreviewRequest
): Promise<ExportPreviewResponse> {
  const response = await apiClient.post<ExportPreviewResponse>(
    `/projects/${projectId}/data-stores/${storeId}/preview-export`,
    data
  )
  return response.data
}

export async function executeExport(
  projectId: string,
  storeId: string,
  data: ExportPreviewRequest
): Promise<ExportExecuteResponse> {
  const response = await apiClient.post<ExportExecuteResponse>(
    `/projects/${projectId}/data-stores/${storeId}/execute-export`,
    data
  )
  return response.data
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/dataStores.ts
git commit -m "feat: add previewExport and executeExport API wrappers"
```

---

## Task 9: Frontend — FieldMappingEditor Component

**Files:**
- Create: `frontend/src/components/export/FieldMappingEditor.tsx`

- [ ] **Step 1: Create the component**

```typescript
// frontend/src/components/export/FieldMappingEditor.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Plus, Trash2, Wand2 } from 'lucide-react'
import type { ColumnDefinition } from '@/types/dataStore'

interface MappingEntry {
  sourcePath: string
  destinationColumn: string
}

interface FieldMappingEditorProps {
  sourceJson: string
  destinationColumns: ColumnDefinition[]
  mapping: MappingEntry[]
  onChange: (mapping: MappingEntry[]) => void
}

function isArrayPath(sourcePath: string, parsedSource: Record<string, unknown> | null): boolean {
  if (!sourcePath.includes('.') || !parsedSource) return false
  const arrayName = sourcePath.split('.')[0]
  return Array.isArray(parsedSource[arrayName])
}

function getValidationErrors(
  mapping: MappingEntry[],
  destinationColumns: ColumnDefinition[]
): string[] {
  const errors: string[] = []

  if (mapping.length === 0) {
    errors.push('At least one mapping is required')
    return errors
  }

  const destCounts: Record<string, number> = {}
  for (const entry of mapping) {
    if (entry.sourcePath.split('.').length > 2) {
      errors.push(`Nested array paths not supported: "${entry.sourcePath}"`)
    }
    if (entry.destinationColumn) {
      destCounts[entry.destinationColumn] = (destCounts[entry.destinationColumn] || 0) + 1
    }
  }

  for (const [col, count] of Object.entries(destCounts)) {
    if (count > 1) errors.push(`Duplicate destination: "${col}"`)
  }

  const mappedDests = new Set(mapping.map((m) => m.destinationColumn).filter(Boolean))
  for (const col of destinationColumns) {
    if (!col.nullable && !mappedDests.has(col.name)) {
      errors.push(`Required column "${col.name}" has no mapping`)
    }
  }

  return errors
}

export function FieldMappingEditor({
  sourceJson,
  destinationColumns,
  mapping,
  onChange,
}: FieldMappingEditorProps) {
  let parsedSource: Record<string, unknown> | null = null
  try {
    parsedSource = JSON.parse(sourceJson)
  } catch {
    // invalid JSON — that's fine, we just won't show array indicators
  }

  const errors = getValidationErrors(mapping, destinationColumns)

  const addRow = () => {
    onChange([...mapping, { sourcePath: '', destinationColumn: '' }])
  }

  const removeRow = (index: number) => {
    onChange(mapping.filter((_, i) => i !== index))
  }

  const updateRow = (index: number, field: keyof MappingEntry, value: string) => {
    const updated = mapping.map((entry, i) =>
      i === index ? { ...entry, [field]: value } : entry
    )
    onChange(updated)
  }

  const autoDetect = () => {
    if (!parsedSource) return
    const colNames = new Set(destinationColumns.map((c) => c.name))
    const newMapping: MappingEntry[] = []

    // Match top-level scalar fields
    for (const key of Object.keys(parsedSource)) {
      if (colNames.has(key) && !Array.isArray(parsedSource[key]) && typeof parsedSource[key] !== 'object') {
        newMapping.push({ sourcePath: key, destinationColumn: key })
      }
    }

    // Match array fields
    for (const key of Object.keys(parsedSource)) {
      if (Array.isArray(parsedSource[key]) && (parsedSource[key] as unknown[]).length > 0) {
        const firstElement = (parsedSource[key] as Record<string, unknown>[])[0]
        if (typeof firstElement === 'object' && firstElement !== null) {
          for (const subKey of Object.keys(firstElement)) {
            // Try exact match: array.field -> field
            if (colNames.has(subKey)) {
              newMapping.push({ sourcePath: `${key}.${subKey}`, destinationColumn: subKey })
            }
            // Try prefixed match: array.field -> arrayfield or array_field
            for (const colName of colNames) {
              if (colName === `${key}_${subKey}` || colName === `${key}${subKey}`) {
                newMapping.push({ sourcePath: `${key}.${subKey}`, destinationColumn: colName })
              }
            }
          }
        }
      }
    }

    // Deduplicate by destination
    const seen = new Set<string>()
    const deduped = newMapping.filter((m) => {
      if (seen.has(m.destinationColumn)) return false
      seen.add(m.destinationColumn)
      return true
    })

    onChange(deduped)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Field Mapping</h3>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={autoDetect} disabled={!parsedSource}>
            <Wand2 className="h-4 w-4 mr-1" /> Auto-detect
          </Button>
          <Button variant="outline" size="sm" onClick={addRow}>
            <Plus className="h-4 w-4 mr-1" /> Add Mapping
          </Button>
        </div>
      </div>

      {mapping.length > 0 && (
        <div className="space-y-2">
          <div className="grid grid-cols-[1fr_auto_1fr_auto] gap-2 items-center text-xs text-muted-foreground font-medium px-1">
            <span>Source Path</span>
            <span />
            <span>Destination Column</span>
            <span />
          </div>
          {mapping.map((entry, index) => (
            <div key={index} className="grid grid-cols-[1fr_auto_1fr_auto] gap-2 items-center">
              <div className="relative">
                <Input
                  value={entry.sourcePath}
                  onChange={(e) => updateRow(index, 'sourcePath', e.target.value)}
                  placeholder="e.g. items.description"
                  className="text-sm"
                />
                {isArrayPath(entry.sourcePath, parsedSource) && (
                  <Badge
                    variant="secondary"
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] px-1 py-0"
                  >
                    array
                  </Badge>
                )}
              </div>
              <span className="text-muted-foreground text-sm">→</span>
              <Select
                value={entry.destinationColumn}
                onValueChange={(v) => updateRow(index, 'destinationColumn', v)}
              >
                <SelectTrigger className="text-sm">
                  <SelectValue placeholder="Select column" />
                </SelectTrigger>
                <SelectContent>
                  {destinationColumns.map((col) => (
                    <SelectItem key={col.name} value={col.name}>
                      {col.name}
                      <span className="text-muted-foreground ml-1">({col.type})</span>
                      {!col.nullable && <span className="text-red-500 ml-1">*</span>}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button variant="ghost" size="sm" onClick={() => removeRow(index)}>
                <Trash2 className="h-4 w-4 text-muted-foreground" />
              </Button>
            </div>
          ))}
        </div>
      )}

      {errors.length > 0 && (
        <Alert variant="destructive">
          <AlertDescription>
            <ul className="list-disc list-inside text-sm">
              {errors.map((err, i) => (
                <li key={i}>{err}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}

export type { MappingEntry }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/export/FieldMappingEditor.tsx
git commit -m "feat: add FieldMappingEditor component"
```

---

## Task 10: Frontend — FanOutPreview Component

**Files:**
- Create: `frontend/src/components/export/FanOutPreview.tsx`

- [ ] **Step 1: Create the component**

```typescript
// frontend/src/components/export/FanOutPreview.tsx
import type { ColumnDefinition } from '@/types/dataStore'

interface FanOutPreviewProps {
  rows: Record<string, unknown>[]
  columns: ColumnDefinition[]
}

export function FanOutPreview({ rows, columns }: FanOutPreviewProps) {
  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-center border rounded-lg">
        <p className="text-muted-foreground text-sm">No rows to preview. Check your source data and mapping.</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">
        {rows.length} row{rows.length !== 1 ? 's' : ''} will be exported
      </p>
      <div className="border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left py-2 px-3 font-medium text-xs text-muted-foreground w-10">#</th>
                {columns.map((col) => (
                  <th key={col.name} className="text-left py-2 px-3 font-medium text-xs">
                    {col.name}
                    <span className="text-muted-foreground ml-1">({col.type})</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((row, i) => (
                <tr key={i} className="hover:bg-primary/5 transition-colors">
                  <td className="py-2 px-3 text-xs text-muted-foreground">{i + 1}</td>
                  {columns.map((col) => (
                    <td key={col.name} className="py-2 px-3 text-sm">
                      {row[col.name] != null ? (
                        String(row[col.name])
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/export/FanOutPreview.tsx
git commit -m "feat: add FanOutPreview component"
```

---

## Task 11: Frontend — ExportPlaygroundPage + Route + Nav

**Files:**
- Create: `frontend/src/pages/ExportPlaygroundPage.tsx`
- Modify: `frontend/src/config/navigation.ts`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create the playground page**

```typescript
// frontend/src/pages/ExportPlaygroundPage.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { AlignLeft, Play, RotateCcw, Eye } from 'lucide-react'
import { toast } from 'sonner'
import { useProject } from '@/contexts/ProjectContext'
import { useDataStores } from '@/hooks/useDataStores'
import { FieldMappingEditor } from '@/components/export/FieldMappingEditor'
import { FanOutPreview } from '@/components/export/FanOutPreview'
import * as dataStoresApi from '@/api/dataStores'
import type { MappingEntry } from '@/components/export/FieldMappingEditor'
import type { ColumnDefinition } from '@/types/dataStore'

export default function ExportPlaygroundPage() {
  const { currentProject } = useProject()
  const projectId = currentProject?.id || null
  const { dataStores } = useDataStores(projectId)

  const [selectedStoreId, setSelectedStoreId] = useState<string>('')
  const [sourceJson, setSourceJson] = useState('')
  const [jsonError, setJsonError] = useState<string | null>(null)
  const [mapping, setMapping] = useState<MappingEntry[]>([])
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[] | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)
  const [isExecuteLoading, setIsExecuteLoading] = useState(false)

  const selectedStore = dataStores.find((s) => s.id === selectedStoreId)
  const columns: ColumnDefinition[] = selectedStore?.schemaDefinition || []

  const validateJson = (value: string) => {
    if (!value.trim()) {
      setJsonError(null)
      return
    }
    try {
      JSON.parse(value)
      setJsonError(null)
    } catch {
      setJsonError('Invalid JSON')
    }
  }

  const formatJson = () => {
    try {
      const parsed = JSON.parse(sourceJson)
      setSourceJson(JSON.stringify(parsed, null, 2))
      setJsonError(null)
    } catch {
      setJsonError('Cannot format — invalid JSON')
    }
  }

  const buildFieldMapping = (): Record<string, string> => {
    const result: Record<string, string> = {}
    for (const entry of mapping) {
      if (entry.sourcePath && entry.destinationColumn) {
        result[entry.sourcePath] = entry.destinationColumn
      }
    }
    return result
  }

  const handlePreview = async () => {
    if (!projectId || !selectedStoreId || !sourceJson.trim()) return
    setIsPreviewLoading(true)
    setPreviewError(null)
    setPreviewRows(null)
    try {
      const parsed = JSON.parse(sourceJson)
      const fieldMapping = buildFieldMapping()
      const result = await dataStoresApi.previewExport(projectId, selectedStoreId, {
        sourceData: parsed,
        fieldMapping,
      })
      setPreviewRows(result.rows)
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : 'Preview failed')
    } finally {
      setIsPreviewLoading(false)
    }
  }

  const handleExecute = async () => {
    if (!projectId || !selectedStoreId || !sourceJson.trim()) return
    setIsExecuteLoading(true)
    try {
      const parsed = JSON.parse(sourceJson)
      const fieldMapping = buildFieldMapping()
      const result = await dataStoresApi.executeExport(projectId, selectedStoreId, {
        sourceData: parsed,
        fieldMapping,
      })
      toast.success(`Exported ${result.rowsImported} rows`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Export failed')
    } finally {
      setIsExecuteLoading(false)
    }
  }

  const handleClear = () => {
    setSourceJson('')
    setJsonError(null)
    setMapping([])
    setPreviewRows(null)
    setPreviewError(null)
  }

  if (!projectId) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-muted-foreground">Select a project to use the Export Playground.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Export Playground</h1>
        <p className="text-muted-foreground">Test field mappings and preview array fan-out before exporting</p>
      </div>

      {/* Section 1: Destination */}
      <div className="space-y-3">
        <Label className="text-sm font-medium">Destination Data Store</Label>
        <Select value={selectedStoreId} onValueChange={setSelectedStoreId}>
          <SelectTrigger>
            <SelectValue placeholder="Select a data store" />
          </SelectTrigger>
          <SelectContent>
            {dataStores.map((store) => (
              <SelectItem key={store.id} value={store.id}>
                {store.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {columns.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {columns.map((col) => (
              <Badge key={col.name} variant="secondary" className="font-mono text-xs">
                {col.name}: {col.type}
                {!col.nullable && ' *'}
              </Badge>
            ))}
          </div>
        )}
      </div>

      <Separator />

      {/* Section 2: Source Data */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium">Source Data (JSON)</Label>
          <Button variant="outline" size="sm" onClick={formatJson} disabled={!sourceJson.trim()}>
            <AlignLeft className="h-4 w-4 mr-1" /> Format
          </Button>
        </div>
        <Textarea
          value={sourceJson}
          onChange={(e) => setSourceJson(e.target.value)}
          onBlur={() => validateJson(sourceJson)}
          placeholder='{"receipt_date": "2026-04-15", "vendor": "Costco", "items": [{"description": "Bread", "price": 2.50}]}'
          rows={8}
          className={`font-mono text-sm ${jsonError ? 'border-red-500' : ''}`}
        />
        {jsonError && (
          <p className="text-sm text-red-500">{jsonError}</p>
        )}
      </div>

      <Separator />

      {/* Section 3: Field Mapping */}
      {selectedStoreId && (
        <FieldMappingEditor
          sourceJson={sourceJson}
          destinationColumns={columns}
          mapping={mapping}
          onChange={setMapping}
        />
      )}

      <Separator />

      {/* Section 4: Preview & Execute */}
      <div className="space-y-4">
        <div className="flex gap-2">
          <Button
            onClick={handlePreview}
            disabled={!selectedStoreId || !sourceJson.trim() || mapping.length === 0 || isPreviewLoading}
          >
            <Eye className="h-4 w-4 mr-1" />
            {isPreviewLoading ? 'Previewing...' : 'Preview'}
          </Button>
          <Button
            variant="default"
            onClick={handleExecute}
            disabled={!previewRows || previewRows.length === 0 || isExecuteLoading}
          >
            <Play className="h-4 w-4 mr-1" />
            {isExecuteLoading ? 'Exporting...' : 'Execute'}
          </Button>
          <Button variant="outline" onClick={handleClear}>
            <RotateCcw className="h-4 w-4 mr-1" /> Clear
          </Button>
        </div>

        {previewError && (
          <Alert variant="destructive">
            <AlertDescription>{previewError}</AlertDescription>
          </Alert>
        )}

        {previewRows && (
          <FanOutPreview rows={previewRows} columns={columns} />
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add route to App.tsx**

In `frontend/src/App.tsx`, add the import after the existing page imports:

```typescript
import ExportPlaygroundPage from './pages/ExportPlaygroundPage'
```

Add the route after the `data-stores/:storeId` route entry:

```typescript
          {
            path: 'export',
            element: <ExportPlaygroundPage />,
            handle: { breadcrumb: 'Export' },
          },
```

- [ ] **Step 3: Add nav item**

In `frontend/src/config/navigation.ts`, update the import:

```typescript
import { LayoutDashboard, FolderKanban, FileText, Database, BarChart3, Settings, FileSearch, Bot, HardDrive, ArrowUpFromLine } from 'lucide-react'
```

Add the Export entry after Data Stores:

```typescript
  { label: 'Data Stores', href: '/data-stores', icon: HardDrive, activeColor: 'border-l-cyan-500' },
  { label: 'Export', href: '/export', icon: ArrowUpFromLine, activeColor: 'border-l-emerald-500' },
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ExportPlaygroundPage.tsx frontend/src/App.tsx frontend/src/config/navigation.ts
git commit -m "feat: add Export Playground page with routing and navigation"
```

---

## Task 12: Build Verification + Docker Rebuild

**Files:** None (verification only)

- [ ] **Step 1: Run frontend build**

```bash
cd frontend && node node_modules/vite/bin/vite.js build
```

Expected: Build succeeds.

- [ ] **Step 2: Run field_mapper tests**

```bash
cd backend && uv run python -m pytest tests/services/test_field_mapper.py -v -o "addopts="
```

Expected: All tests PASS.

- [ ] **Step 3: Rebuild and restart Docker containers**

```bash
cd .. && docker compose -f docker-compose.local.yml up --build -d
```

Expected: All containers start. Check backend logs:
```bash
docker logs rag-admin-backend-local --tail 20
```

Expected: Migration `e6f7a8b9c0d1` runs, server starts.

- [ ] **Step 4: Verify endpoints**

```bash
curl -s http://localhost:8000/health
```

Expected: `{"status":"healthy"}`

- [ ] **Step 5: Manual verification checklist**

Test in browser at `http://localhost:3000`:

1. Navigate to Data Stores → create or open an existing store
2. Add a row manually → verify "Source" column shows "manual" badge
3. Import a CSV → verify imported rows show "csv_import" badge
4. Click the "manual" or "csv_import" badge → verify popover shows full JSON
5. Navigate to Export (sidebar) → Export Playground page loads
6. Select a data store → destination columns appear as badges
7. Paste sample JSON: `{"vendor":"Costco","items":[{"description":"Bread","price":2.50}]}`
8. Click Auto-detect → mappings are suggested
9. Click Preview → flattened rows appear in the preview table
10. Click Execute → success toast, rows inserted
11. Navigate back to the data store → new rows visible with "playground" source badge
