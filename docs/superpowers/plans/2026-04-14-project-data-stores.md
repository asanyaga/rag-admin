# Project Data Stores Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add user-defined relational data stores per project — dynamic PostgreSQL tables with schema management, CRUD, CSV import, and agent export tool integration.

**Architecture:** Each project can have multiple data stores. Each store has a metadata record in `project_data_stores` plus a dynamically-created PostgreSQL table for the actual data. The backend follows the existing router → service → repository pattern. The frontend adds a new "Data Stores" nav section with list and detail pages.

**Tech Stack:** Python/FastAPI, SQLAlchemy (async), Alembic, React/TypeScript, shadcn/ui, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-04-14-project-data-stores-design.md`

---

## File Structure

### Backend — New Files
- `backend/app/models/project_data_store.py` — SQLAlchemy model for `project_data_stores` metadata table
- `backend/app/schemas/data_store.py` — Pydantic request/response schemas
- `backend/app/repositories/data_store_repository.py` — Metadata CRUD (ORM) + dynamic table operations (raw SQL)
- `backend/app/services/data_store_service.py` — Business logic orchestrating metadata + DDL
- `backend/app/routers/data_stores.py` — REST API endpoints
- `backend/alembic/versions/xxxx_add_project_data_stores.py` — Migration (auto-generated)

### Backend — Modified Files
- `backend/app/models/__init__.py` — Register new model
- `backend/app/main.py` — Register new router
- `backend/alembic/env.py` — Import new model
- `backend/app/services/agent/tools/export.py` — Update tool definition with config_schema
- `backend/app/services/agent/nodes.py` — Enhance export_node to write to data store
- `backend/app/services/agent/tools/__init__.py` — No change needed (lazy loading handles it)

### Backend — New Test Files
- `backend/tests/services/test_data_store_service.py`
- `backend/tests/routers/test_data_stores.py`

### Frontend — New Files
- `frontend/src/types/dataStore.ts` — TypeScript interfaces
- `frontend/src/api/dataStores.ts` — HTTP wrappers
- `frontend/src/hooks/useDataStores.ts` — Store-level CRUD hook
- `frontend/src/hooks/useDataStoreRows.ts` — Row-level CRUD + CSV import hook
- `frontend/src/pages/DataStoresPage.tsx` — List page
- `frontend/src/pages/DataStoreDetailPage.tsx` — Detail page with data grid
- `frontend/src/components/data-stores/DataStoreCreateDialog.tsx` — Create form with schema editor
- `frontend/src/components/data-stores/DataStoreEditDialog.tsx` — Edit name/description/schema
- `frontend/src/components/data-stores/DataStoreSchemaEditor.tsx` — Reusable column list editor
- `frontend/src/components/data-stores/DataGrid.tsx` — Schema-driven data table with inline edit
- `frontend/src/components/data-stores/CsvImportDialog.tsx` — CSV upload + column mapping
- `frontend/src/components/data-stores/AddRowDialog.tsx` — Manual row entry form

### Frontend — Modified Files
- `frontend/src/App.tsx` — Add routes
- `frontend/src/config/navigation.ts` — Add nav item

---

## Task 1: Backend Model + Migration

**Files:**
- Create: `backend/app/models/project_data_store.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/alembic/env.py`

- [ ] **Step 1: Create the ProjectDataStore model**

```python
# backend/app/models/project_data_store.py
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Integer, String, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProjectDataStore(Base):
    """Metadata for a user-defined project data store backed by a dynamic PostgreSQL table."""
    __tablename__ = "project_data_stores"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text('gen_random_uuid()')
    )
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    schema_definition: Mapped[list] = mapped_column(JSON, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=sa.text('NOW()')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=sa.text('NOW()')
    )

    project: Mapped["Project"] = relationship()

    __table_args__ = (
        sa.UniqueConstraint('project_id', 'name', name='uq_project_data_stores_project_name'),
        sa.Index('ix_project_data_stores_project_id', 'project_id'),
    )
```

- [ ] **Step 2: Register the model in `__init__.py`**

Add to `backend/app/models/__init__.py`:

```python
from app.models.project_data_store import ProjectDataStore
```

And add `"ProjectDataStore"` to the `__all__` list.

- [ ] **Step 3: Import the model in Alembic env**

Add to the imports in `backend/alembic/env.py`:

```python
from app.models import (
    User, RefreshToken, LoginAttempt, Project, Document,
    Index, IndexDocument, Chunk, ProviderKey,
    GoldenSet, GoldenSetQuery, GoldenSetSource,
    EvalRun, EvalRunResult,
    AgentDefinition,
    AgentRun,
    ProjectDataStore,
)
```

- [ ] **Step 4: Generate the migration**

Run:
```bash
cd backend && alembic revision --autogenerate -m "add_project_data_stores_table"
```

Expected: A new migration file is created in `backend/alembic/versions/` with `CREATE TABLE project_data_stores`.

- [ ] **Step 5: Apply the migration**

Run:
```bash
cd backend && alembic upgrade head
```

Expected: Migration applied successfully.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/project_data_store.py backend/app/models/__init__.py backend/alembic/env.py backend/alembic/versions/*add_project_data_stores*
git commit -m "feat: add ProjectDataStore model and migration"
```

---

## Task 2: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/data_store.py`

- [ ] **Step 1: Create request/response schemas**

```python
# backend/app/schemas/data_store.py
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ALLOWED_COLUMN_TYPES = {"text", "integer", "numeric", "boolean", "timestamptz"}


class ColumnDefinition(BaseModel):
    """A single column in a data store schema."""
    name: str = Field(..., min_length=1, max_length=63, pattern=r'^[a-z][a-z0-9_]*$')
    type: str = Field(...)
    nullable: bool = Field(default=True)
    description: str = Field(default="", max_length=500)


class DataStoreCreate(BaseModel):
    """Schema for creating a new data store."""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    schema_definition: list[ColumnDefinition] = Field(..., min_length=1)


class DataStoreUpdate(BaseModel):
    """Schema for updating an existing data store."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    schema_definition: list[ColumnDefinition] | None = None


class DataStoreResponse(BaseModel):
    """Schema for data store API responses."""
    id: UUID
    project_id: UUID = Field(..., alias="projectId")
    name: str
    description: str | None
    table_name: str = Field(..., alias="tableName")
    schema_definition: list[ColumnDefinition] = Field(..., alias="schemaDefinition")
    row_count: int = Field(..., alias="rowCount")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class DataStoreRowResponse(BaseModel):
    """Schema for a single row in a data store."""
    id: UUID
    data: dict
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(populate_by_name=True)


class DataStoreRowsResponse(BaseModel):
    """Paginated list of rows."""
    rows: list[DataStoreRowResponse]
    total: int
    limit: int
    offset: int


class CsvImportResponse(BaseModel):
    """Response from CSV import."""
    rows_imported: int = Field(..., alias="rowsImported")

    model_config = ConfigDict(populate_by_name=True)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/data_store.py
git commit -m "feat: add Pydantic schemas for data stores"
```

---

## Task 3: Repository — Metadata Operations

**Files:**
- Create: `backend/app/repositories/data_store_repository.py`

- [ ] **Step 1: Create repository with metadata CRUD**

```python
# backend/app/repositories/data_store_repository.py
import re
from uuid import UUID, uuid4

from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project_data_store import ProjectDataStore
from app.schemas.data_store import DataStoreCreate, DataStoreUpdate, ALLOWED_COLUMN_TYPES


# Validation patterns
TABLE_NAME_PATTERN = re.compile(r'^pd_[a-f0-9]{8}$')
COLUMN_NAME_PATTERN = re.compile(r'^[a-z][a-z0-9_]{0,62}$')

# Map schema types to PostgreSQL types
PG_TYPE_MAP = {
    "text": "TEXT",
    "integer": "INTEGER",
    "numeric": "NUMERIC",
    "boolean": "BOOLEAN",
    "timestamptz": "TIMESTAMPTZ",
}


def _generate_table_name() -> str:
    """Generate a unique table name: pd_ + 8 hex chars from a UUID."""
    return f"pd_{uuid4().hex[:8]}"


def _validate_column_name(name: str) -> None:
    """Validate a column name against the allowlist pattern."""
    if not COLUMN_NAME_PATTERN.match(name):
        raise ValueError(f"Invalid column name: {name}")


def _validate_column_type(col_type: str) -> None:
    """Validate a column type against the allowed set."""
    if col_type not in ALLOWED_COLUMN_TYPES:
        raise ValueError(f"Invalid column type: {col_type}. Allowed: {ALLOWED_COLUMN_TYPES}")


class DataStoreRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Metadata CRUD ──────────────────────────────────────────────

    async def create(self, project_id: UUID, data: DataStoreCreate) -> ProjectDataStore:
        """Create a new data store metadata record."""
        table_name = _generate_table_name()
        store = ProjectDataStore(
            project_id=project_id,
            name=data.name,
            description=data.description,
            table_name=table_name,
            schema_definition=[col.model_dump() for col in data.schema_definition],
            row_count=0,
        )
        self.session.add(store)
        await self.session.commit()
        await self.session.refresh(store)
        return store

    async def get_by_id(self, store_id: UUID, project_id: UUID) -> ProjectDataStore | None:
        """Get a data store by ID, scoped to a project."""
        result = await self.session.execute(
            select(ProjectDataStore).where(
                ProjectDataStore.id == store_id,
                ProjectDataStore.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: UUID) -> list[ProjectDataStore]:
        """List all data stores for a project."""
        result = await self.session.execute(
            select(ProjectDataStore)
            .where(ProjectDataStore.project_id == project_id)
            .order_by(ProjectDataStore.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, store_id: UUID, project_id: UUID, data: DataStoreUpdate) -> ProjectDataStore | None:
        """Update a data store metadata record."""
        store = await self.get_by_id(store_id, project_id)
        if not store:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if "schema_definition" in update_data and update_data["schema_definition"] is not None:
            update_data["schema_definition"] = [
                col.model_dump() if hasattr(col, "model_dump") else col
                for col in update_data["schema_definition"]
            ]
        for key, value in update_data.items():
            setattr(store, key, value)

        await self.session.commit()
        await self.session.refresh(store)
        return store

    async def delete_metadata(self, store_id: UUID, project_id: UUID) -> bool:
        """Delete a data store metadata record."""
        result = await self.session.execute(
            delete(ProjectDataStore).where(
                ProjectDataStore.id == store_id,
                ProjectDataStore.project_id == project_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def update_row_count(self, store_id: UUID, count: int) -> None:
        """Update the cached row count for a data store."""
        store = await self.session.get(ProjectDataStore, store_id)
        if store:
            store.row_count = count
            await self.session.commit()

    # ── Dynamic Table Operations ───────────────────────────────────

    async def create_table(self, table_name: str, schema_definition: list[dict]) -> None:
        """Create a dynamic PostgreSQL table for a data store."""
        if not TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"Invalid table name: {table_name}")

        columns = [
            "id UUID PRIMARY KEY DEFAULT gen_random_uuid()",
        ]
        for col in schema_definition:
            _validate_column_name(col["name"])
            _validate_column_type(col["type"])
            pg_type = PG_TYPE_MAP[col["type"]]
            nullable = "NULL" if col.get("nullable", True) else "NOT NULL"
            columns.append(f'"{col["name"]}" {pg_type} {nullable}')

        columns.append("created_at TIMESTAMPTZ NOT NULL DEFAULT now()")
        columns.append("updated_at TIMESTAMPTZ NOT NULL DEFAULT now()")

        sql = f'CREATE TABLE "{table_name}" ({", ".join(columns)})'
        await self.session.execute(text(sql))
        await self.session.commit()

    async def drop_table(self, table_name: str) -> None:
        """Drop a dynamic table."""
        if not TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"Invalid table name: {table_name}")
        await self.session.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
        await self.session.commit()

    async def alter_table_add_columns(self, table_name: str, columns: list[dict]) -> None:
        """Add columns to a dynamic table."""
        if not TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"Invalid table name: {table_name}")
        for col in columns:
            _validate_column_name(col["name"])
            _validate_column_type(col["type"])
            pg_type = PG_TYPE_MAP[col["type"]]
            sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{col["name"]}" {pg_type}'
            await self.session.execute(text(sql))
        await self.session.commit()

    async def alter_table_drop_columns(self, table_name: str, column_names: list[str]) -> None:
        """Drop columns from a dynamic table."""
        if not TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"Invalid table name: {table_name}")
        for name in column_names:
            _validate_column_name(name)
            sql = f'ALTER TABLE "{table_name}" DROP COLUMN "{name}"'
            await self.session.execute(text(sql))
        await self.session.commit()

    async def insert_row(self, table_name: str, schema_definition: list[dict], data: dict) -> dict:
        """Insert a single row and return it."""
        if not TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"Invalid table name: {table_name}")

        col_names = [col["name"] for col in schema_definition if col["name"] in data]
        if not col_names:
            raise ValueError("No valid columns to insert")

        placeholders = ", ".join(f":{name}" for name in col_names)
        col_list = ", ".join(f'"{name}"' for name in col_names)
        sql = f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders}) RETURNING *'

        params = {name: data[name] for name in col_names}
        result = await self.session.execute(text(sql), params)
        await self.session.commit()
        row = result.mappings().one()
        return dict(row)

    async def get_rows(self, table_name: str, limit: int = 50, offset: int = 0) -> list[dict]:
        """Get paginated rows from a dynamic table."""
        if not TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"Invalid table name: {table_name}")

        sql = f'SELECT * FROM "{table_name}" ORDER BY created_at DESC LIMIT :limit OFFSET :offset'
        result = await self.session.execute(text(sql), {"limit": limit, "offset": offset})
        return [dict(row) for row in result.mappings().all()]

    async def get_row(self, table_name: str, row_id: UUID) -> dict | None:
        """Get a single row by ID."""
        if not TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"Invalid table name: {table_name}")

        sql = f'SELECT * FROM "{table_name}" WHERE id = :id'
        result = await self.session.execute(text(sql), {"id": row_id})
        row = result.mappings().one_or_none()
        return dict(row) if row else None

    async def update_row(self, table_name: str, schema_definition: list[dict], row_id: UUID, data: dict) -> dict | None:
        """Update a single row by ID."""
        if not TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"Invalid table name: {table_name}")

        valid_cols = {col["name"] for col in schema_definition}
        update_cols = [name for name in data if name in valid_cols]
        if not update_cols:
            raise ValueError("No valid columns to update")

        set_clause = ", ".join(f'"{name}" = :{name}' for name in update_cols)
        sql = f'UPDATE "{table_name}" SET {set_clause}, updated_at = now() WHERE id = :id RETURNING *'

        params = {name: data[name] for name in update_cols}
        params["id"] = row_id
        result = await self.session.execute(text(sql), params)
        await self.session.commit()
        row = result.mappings().one_or_none()
        return dict(row) if row else None

    async def delete_row(self, table_name: str, row_id: UUID) -> bool:
        """Delete a single row by ID."""
        if not TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"Invalid table name: {table_name}")

        sql = f'DELETE FROM "{table_name}" WHERE id = :id'
        result = await self.session.execute(text(sql), {"id": row_id})
        await self.session.commit()
        return result.rowcount > 0

    async def count_rows(self, table_name: str) -> int:
        """Count rows in a dynamic table."""
        if not TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"Invalid table name: {table_name}")

        sql = f'SELECT COUNT(*) FROM "{table_name}"'
        result = await self.session.execute(text(sql))
        return result.scalar_one()

    async def bulk_insert(self, table_name: str, schema_definition: list[dict], rows: list[dict]) -> int:
        """Bulk insert rows. Returns count of inserted rows."""
        if not TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"Invalid table name: {table_name}")
        if not rows:
            return 0

        col_names = [col["name"] for col in schema_definition]
        placeholders = ", ".join(f":{name}" for name in col_names)
        col_list = ", ".join(f'"{name}"' for name in col_names)
        sql = f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders})'

        params_list = []
        for row in rows:
            params = {name: row.get(name) for name in col_names}
            params_list.append(params)

        for params in params_list:
            await self.session.execute(text(sql), params)

        await self.session.commit()
        return len(params_list)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/repositories/data_store_repository.py
git commit -m "feat: add DataStoreRepository with metadata CRUD and dynamic table ops"
```

---

## Task 4: Service Layer

**Files:**
- Create: `backend/app/services/data_store_service.py`

- [ ] **Step 1: Create the service**

```python
# backend/app/services/data_store_service.py
import csv
import io
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.repositories.data_store_repository import DataStoreRepository
from app.schemas.data_store import (
    ALLOWED_COLUMN_TYPES,
    DataStoreCreate,
    DataStoreUpdate,
    DataStoreResponse,
    DataStoreRowResponse,
    DataStoreRowsResponse,
    CsvImportResponse,
    ColumnDefinition,
)
from app.services.exceptions import ConflictError, NotFoundError, ValidationError


class DataStoreService:
    def __init__(self, repo: DataStoreRepository):
        self.repo = repo

    async def create_store(self, project_id: UUID, data: DataStoreCreate) -> DataStoreResponse:
        """Create a data store: metadata record + dynamic PostgreSQL table."""
        self._validate_schema(data.schema_definition)

        try:
            store = await self.repo.create(project_id, data)
        except IntegrityError as e:
            error_str = str(e).lower()
            if 'uq_project_data_stores_project_name' in error_str:
                raise ConflictError(f"Data store with name '{data.name}' already exists in this project")
            raise

        try:
            await self.repo.create_table(store.table_name, store.schema_definition)
        except Exception:
            # Rollback: remove metadata if table creation fails
            await self.repo.delete_metadata(store.id, project_id)
            raise

        return DataStoreResponse.model_validate(store)

    async def get_store(self, store_id: UUID, project_id: UUID) -> DataStoreResponse:
        """Get a data store by ID."""
        store = await self.repo.get_by_id(store_id, project_id)
        if not store:
            raise NotFoundError(f"Data store {store_id} not found")
        return DataStoreResponse.model_validate(store)

    async def list_stores(self, project_id: UUID) -> list[DataStoreResponse]:
        """List all data stores for a project."""
        stores = await self.repo.list_by_project(project_id)
        return [DataStoreResponse.model_validate(s) for s in stores]

    async def update_store(self, store_id: UUID, project_id: UUID, data: DataStoreUpdate) -> DataStoreResponse:
        """Update a data store. If schema changed, apply ALTER TABLE."""
        store = await self.repo.get_by_id(store_id, project_id)
        if not store:
            raise NotFoundError(f"Data store {store_id} not found")

        if data.schema_definition is not None:
            self._validate_schema(data.schema_definition)
            await self._apply_schema_changes(
                store.table_name,
                store.schema_definition,
                [col.model_dump() for col in data.schema_definition],
            )

        try:
            updated = await self.repo.update(store_id, project_id, data)
        except IntegrityError as e:
            error_str = str(e).lower()
            if 'uq_project_data_stores_project_name' in error_str:
                raise ConflictError(f"Data store with name '{data.name}' already exists in this project")
            raise

        if not updated:
            raise NotFoundError(f"Data store {store_id} not found")
        return DataStoreResponse.model_validate(updated)

    async def delete_store(self, store_id: UUID, project_id: UUID) -> None:
        """Delete a data store: drop dynamic table + remove metadata."""
        store = await self.repo.get_by_id(store_id, project_id)
        if not store:
            raise NotFoundError(f"Data store {store_id} not found")

        await self.repo.drop_table(store.table_name)
        await self.repo.delete_metadata(store_id, project_id)

    # ── Row operations ─────────────────────────────────────────────

    async def get_rows(self, store_id: UUID, project_id: UUID, limit: int = 50, offset: int = 0) -> DataStoreRowsResponse:
        """Get paginated rows from a data store."""
        store = await self.repo.get_by_id(store_id, project_id)
        if not store:
            raise NotFoundError(f"Data store {store_id} not found")

        rows = await self.repo.get_rows(store.table_name, limit, offset)
        total = await self.repo.count_rows(store.table_name)

        return DataStoreRowsResponse(
            rows=[self._row_to_response(row, store.schema_definition) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def insert_row(self, store_id: UUID, project_id: UUID, data: dict) -> DataStoreRowResponse:
        """Insert a single row."""
        store = await self.repo.get_by_id(store_id, project_id)
        if not store:
            raise NotFoundError(f"Data store {store_id} not found")

        self._validate_row_data(data, store.schema_definition)
        row = await self.repo.insert_row(store.table_name, store.schema_definition, data)
        await self._refresh_row_count(store)
        return self._row_to_response(row, store.schema_definition)

    async def get_row(self, store_id: UUID, project_id: UUID, row_id: UUID) -> DataStoreRowResponse:
        """Get a single row by ID."""
        store = await self.repo.get_by_id(store_id, project_id)
        if not store:
            raise NotFoundError(f"Data store {store_id} not found")

        row = await self.repo.get_row(store.table_name, row_id)
        if not row:
            raise NotFoundError(f"Row {row_id} not found")
        return self._row_to_response(row, store.schema_definition)

    async def update_row(self, store_id: UUID, project_id: UUID, row_id: UUID, data: dict) -> DataStoreRowResponse:
        """Update a single row."""
        store = await self.repo.get_by_id(store_id, project_id)
        if not store:
            raise NotFoundError(f"Data store {store_id} not found")

        self._validate_row_data(data, store.schema_definition, partial=True)
        row = await self.repo.update_row(store.table_name, store.schema_definition, row_id, data)
        if not row:
            raise NotFoundError(f"Row {row_id} not found")
        return self._row_to_response(row, store.schema_definition)

    async def delete_row(self, store_id: UUID, project_id: UUID, row_id: UUID) -> None:
        """Delete a single row."""
        store = await self.repo.get_by_id(store_id, project_id)
        if not store:
            raise NotFoundError(f"Data store {store_id} not found")

        deleted = await self.repo.delete_row(store.table_name, row_id)
        if not deleted:
            raise NotFoundError(f"Row {row_id} not found")
        await self._refresh_row_count(store)

    async def import_csv(self, store_id: UUID, project_id: UUID, csv_content: str, column_mapping: dict[str, str]) -> CsvImportResponse:
        """Import rows from CSV content.

        column_mapping: maps CSV header names → data store column names.
        """
        store = await self.repo.get_by_id(store_id, project_id)
        if not store:
            raise NotFoundError(f"Data store {store_id} not found")

        reader = csv.DictReader(io.StringIO(csv_content))
        rows = []
        for line_num, csv_row in enumerate(reader, start=2):
            mapped_row = {}
            for csv_col, store_col in column_mapping.items():
                if csv_col in csv_row:
                    mapped_row[store_col] = self._coerce_value(
                        csv_row[csv_col], store_col, store.schema_definition, line_num
                    )
            rows.append(mapped_row)

        if not rows:
            raise ValidationError("CSV file contains no data rows")

        for i, row in enumerate(rows, start=2):
            self._validate_row_data(row, store.schema_definition, line_num=i)

        count = await self.repo.bulk_insert(store.table_name, store.schema_definition, rows)
        await self._refresh_row_count(store)
        return CsvImportResponse(rows_imported=count)

    # ── Helpers ────────────────────────────────────────────────────

    def _validate_schema(self, columns: list[ColumnDefinition]) -> None:
        """Validate all columns in a schema definition."""
        names = set()
        reserved = {"id", "created_at", "updated_at"}
        for col in columns:
            if col.name in reserved:
                raise ValidationError(f"Column name '{col.name}' is reserved")
            if col.name in names:
                raise ValidationError(f"Duplicate column name: '{col.name}'")
            if col.type not in ALLOWED_COLUMN_TYPES:
                raise ValidationError(f"Invalid column type '{col.type}'. Allowed: {ALLOWED_COLUMN_TYPES}")
            names.add(col.name)

    def _validate_row_data(self, data: dict, schema_definition: list[dict], partial: bool = False, line_num: int | None = None) -> None:
        """Validate row data against the schema definition."""
        col_map = {col["name"]: col for col in schema_definition}
        prefix = f"Row {line_num}: " if line_num else ""

        for key in data:
            if key not in col_map:
                raise ValidationError(f"{prefix}Unknown column '{key}'")

        if not partial:
            for col in schema_definition:
                if not col.get("nullable", True) and col["name"] not in data:
                    raise ValidationError(f"{prefix}Required column '{col['name']}' is missing")

    def _coerce_value(self, raw: str, col_name: str, schema_definition: list[dict], line_num: int) -> object:
        """Coerce a CSV string value to the appropriate Python type."""
        col = next((c for c in schema_definition if c["name"] == col_name), None)
        if not col:
            return raw

        raw = raw.strip()
        if raw == "" and col.get("nullable", True):
            return None

        col_type = col["type"]
        try:
            if col_type == "text":
                return raw
            elif col_type == "integer":
                return int(raw)
            elif col_type == "numeric":
                return float(raw)
            elif col_type == "boolean":
                if raw.lower() in ("true", "1", "yes"):
                    return True
                elif raw.lower() in ("false", "0", "no"):
                    return False
                raise ValueError()
            elif col_type == "timestamptz":
                return raw  # Let PostgreSQL parse the timestamp
        except (ValueError, TypeError):
            raise ValidationError(
                f"Row {line_num}: Cannot convert '{raw}' to {col_type} for column '{col_name}'"
            )
        return raw

    async def _apply_schema_changes(self, table_name: str, old_schema: list[dict], new_schema: list[dict]) -> None:
        """Diff old vs new schema and apply ALTER TABLE changes."""
        old_names = {col["name"] for col in old_schema}
        new_names = {col["name"] for col in new_schema}

        to_add = [col for col in new_schema if col["name"] not in old_names]
        to_drop = [name for name in old_names if name not in new_names]

        if to_add:
            await self.repo.alter_table_add_columns(table_name, to_add)
        if to_drop:
            await self.repo.alter_table_drop_columns(table_name, to_drop)

    async def _refresh_row_count(self, store) -> None:
        """Refresh the cached row count."""
        count = await self.repo.count_rows(store.table_name)
        await self.repo.update_row_count(store.id, count)

    def _row_to_response(self, row: dict, schema_definition: list[dict]) -> DataStoreRowResponse:
        """Convert a raw row dict to a DataStoreRowResponse."""
        col_names = {col["name"] for col in schema_definition}
        data = {k: v for k, v in row.items() if k in col_names}
        return DataStoreRowResponse(
            id=row["id"],
            data=data,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/data_store_service.py
git commit -m "feat: add DataStoreService with CRUD, schema changes, and CSV import"
```

---

## Task 5: Router

**Files:**
- Create: `backend/app/routers/data_stores.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create the router**

```python
# backend/app/routers/data_stores.py
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.data_store_repository import DataStoreRepository
from app.schemas.data_store import (
    DataStoreCreate,
    DataStoreUpdate,
    DataStoreResponse,
    DataStoreRowResponse,
    DataStoreRowsResponse,
    CsvImportResponse,
)
from app.services.data_store_service import DataStoreService
from app.services.exceptions import ConflictError, NotFoundError, ValidationError

router = APIRouter(
    prefix="/projects/{project_id}/data-stores",
    tags=["data-stores"],
)


def get_data_store_service(db: AsyncSession = Depends(get_db)) -> DataStoreService:
    repo = DataStoreRepository(db)
    return DataStoreService(repo)


# ── Store CRUD ─────────────────────────────────────────────────────

@router.post("", response_model=DataStoreResponse, status_code=status.HTTP_201_CREATED)
async def create_data_store(
    project_id: UUID,
    data: DataStoreCreate,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Create a new data store for the project."""
    try:
        return await service.create_store(project_id, data)
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=list[DataStoreResponse])
async def list_data_stores(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """List all data stores for the project."""
    return await service.list_stores(project_id)


@router.get("/{store_id}", response_model=DataStoreResponse)
async def get_data_store(
    project_id: UUID,
    store_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Get a data store by ID."""
    try:
        return await service.get_store(store_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{store_id}", response_model=DataStoreResponse)
async def update_data_store(
    project_id: UUID,
    store_id: UUID,
    data: DataStoreUpdate,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Update a data store."""
    try:
        return await service.update_store(store_id, project_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_data_store(
    project_id: UUID,
    store_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Delete a data store and its underlying table."""
    try:
        await service.delete_store(store_id, project_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ── Row CRUD ───────────────────────────────────────────────────────

@router.get("/{store_id}/rows", response_model=DataStoreRowsResponse)
async def list_rows(
    project_id: UUID,
    store_id: UUID,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """List paginated rows from a data store."""
    try:
        return await service.get_rows(store_id, project_id, limit, offset)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{store_id}/rows", response_model=DataStoreRowResponse, status_code=status.HTTP_201_CREATED)
async def insert_row(
    project_id: UUID,
    store_id: UUID,
    data: dict,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Insert a single row into a data store."""
    try:
        return await service.insert_row(store_id, project_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{store_id}/rows/{row_id}", response_model=DataStoreRowResponse)
async def get_row(
    project_id: UUID,
    store_id: UUID,
    row_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Get a single row by ID."""
    try:
        return await service.get_row(store_id, project_id, row_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{store_id}/rows/{row_id}", response_model=DataStoreRowResponse)
async def update_row(
    project_id: UUID,
    store_id: UUID,
    row_id: UUID,
    data: dict,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Update a single row."""
    try:
        return await service.update_row(store_id, project_id, row_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{store_id}/rows/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_row(
    project_id: UUID,
    store_id: UUID,
    row_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Delete a single row."""
    try:
        await service.delete_row(store_id, project_id, row_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ── CSV Import ─────────────────────────────────────────────────────

@router.post("/{store_id}/import", response_model=CsvImportResponse)
async def import_csv(
    project_id: UUID,
    store_id: UUID,
    file: UploadFile = File(...),
    column_mapping: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    service: DataStoreService = Depends(get_data_store_service),
):
    """Import rows from a CSV file.

    column_mapping is a JSON string: {"csv_header": "store_column", ...}
    """
    import json

    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )

    try:
        mapping = json.loads(column_mapping)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="column_mapping must be valid JSON"
        )

    content = await file.read()
    csv_text = content.decode("utf-8")

    try:
        return await service.import_csv(store_id, project_id, csv_text, mapping)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
```

- [ ] **Step 2: Register router in main.py**

Add to the imports in `backend/app/main.py`:

```python
from app.routers import auth, oauth, otel_proxy, projects, users, documents, indexes, provider_keys, golden_sets, eval_runs, experiments, parse_results, extraction, extraction_ground_truth, extraction_eval, agent, data_stores
```

Add before the last `include_router` call:

```python
app.include_router(data_stores.router, prefix="/api/v1")
```

- [ ] **Step 3: Run the backend to verify startup**

Run:
```bash
cd backend && python -c "from app.main import app; print('OK')"
```

Expected: `OK` — no import errors.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/data_stores.py backend/app/main.py
git commit -m "feat: add data stores REST API router"
```

---

## Task 6: Backend Tests — Service Layer

**Files:**
- Create: `backend/tests/services/test_data_store_service.py`

- [ ] **Step 1: Write service tests**

```python
# backend/tests/services/test_data_store_service.py
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthProvider, User
from app.repositories.data_store_repository import DataStoreRepository
from app.repositories.user_repository import UserRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.data_store import DataStoreCreate, DataStoreUpdate, ColumnDefinition
from app.schemas.project import ProjectCreate
from app.services.data_store_service import DataStoreService
from app.services.project_service import ProjectService
from app.services.exceptions import ConflictError, NotFoundError, ValidationError


@pytest.fixture
async def test_user(test_db: AsyncSession) -> User:
    user_repo = UserRepository(test_db)
    user = User(
        email="datastore-test@example.com",
        password_hash="hash",
        auth_provider=AuthProvider.email,
        full_name="Test User",
    )
    return await user_repo.create(user)


@pytest.fixture
async def test_project(test_db: AsyncSession, test_user: User):
    project_repo = ProjectRepository(test_db)
    project_service = ProjectService(project_repo)
    return await project_service.create_project(
        test_user.id, ProjectCreate(name="Test Project")
    )


@pytest.fixture
def data_store_service(test_db: AsyncSession) -> DataStoreService:
    repo = DataStoreRepository(test_db)
    return DataStoreService(repo)


def _make_schema(columns: list[tuple[str, str, bool]] | None = None) -> list[ColumnDefinition]:
    """Helper to create column definitions. Each tuple: (name, type, nullable)."""
    if columns is None:
        columns = [("item_name", "text", False), ("price", "numeric", True)]
    return [ColumnDefinition(name=n, type=t, nullable=nl) for n, t, nl in columns]


@pytest.mark.asyncio
async def test_create_store_success(data_store_service, test_project):
    data = DataStoreCreate(
        name="Budget Items",
        description="Lookup table for budget categories",
        schema_definition=_make_schema(),
    )
    store = await data_store_service.create_store(test_project.id, data)

    assert store.name == "Budget Items"
    assert store.description == "Lookup table for budget categories"
    assert store.table_name.startswith("pd_")
    assert len(store.schema_definition) == 2
    assert store.row_count == 0


@pytest.mark.asyncio
async def test_create_store_duplicate_name(data_store_service, test_project):
    data = DataStoreCreate(name="Dupes", schema_definition=_make_schema())
    await data_store_service.create_store(test_project.id, data)

    with pytest.raises(ConflictError, match="already exists"):
        await data_store_service.create_store(test_project.id, data)


@pytest.mark.asyncio
async def test_create_store_reserved_column_name(data_store_service, test_project):
    data = DataStoreCreate(
        name="Bad Schema",
        schema_definition=_make_schema([("id", "text", False)]),
    )
    with pytest.raises(ValidationError, match="reserved"):
        await data_store_service.create_store(test_project.id, data)


@pytest.mark.asyncio
async def test_create_store_invalid_column_type(data_store_service, test_project):
    data = DataStoreCreate(
        name="Bad Type",
        schema_definition=_make_schema([("name", "varchar", False)]),
    )
    with pytest.raises(ValidationError, match="Invalid column type"):
        await data_store_service.create_store(test_project.id, data)


@pytest.mark.asyncio
async def test_list_stores(data_store_service, test_project):
    await data_store_service.create_store(
        test_project.id,
        DataStoreCreate(name="Store A", schema_definition=_make_schema()),
    )
    await data_store_service.create_store(
        test_project.id,
        DataStoreCreate(name="Store B", schema_definition=_make_schema()),
    )

    stores = await data_store_service.list_stores(test_project.id)
    assert len(stores) == 2


@pytest.mark.asyncio
async def test_delete_store(data_store_service, test_project):
    store = await data_store_service.create_store(
        test_project.id,
        DataStoreCreate(name="To Delete", schema_definition=_make_schema()),
    )
    await data_store_service.delete_store(store.id, test_project.id)

    with pytest.raises(NotFoundError):
        await data_store_service.get_store(store.id, test_project.id)


@pytest.mark.asyncio
async def test_insert_and_get_row(data_store_service, test_project):
    store = await data_store_service.create_store(
        test_project.id,
        DataStoreCreate(name="Row Test", schema_definition=_make_schema()),
    )
    row = await data_store_service.insert_row(
        store.id, test_project.id, {"item_name": "Bread", "price": 2.50}
    )

    assert row.data["item_name"] == "Bread"
    assert row.data["price"] == 2.50

    fetched = await data_store_service.get_row(store.id, test_project.id, row.id)
    assert fetched.data["item_name"] == "Bread"


@pytest.mark.asyncio
async def test_update_row(data_store_service, test_project):
    store = await data_store_service.create_store(
        test_project.id,
        DataStoreCreate(name="Update Test", schema_definition=_make_schema()),
    )
    row = await data_store_service.insert_row(
        store.id, test_project.id, {"item_name": "Bread", "price": 2.50}
    )

    updated = await data_store_service.update_row(
        store.id, test_project.id, row.id, {"price": 3.00}
    )
    assert updated.data["price"] == 3.00
    assert updated.data["item_name"] == "Bread"


@pytest.mark.asyncio
async def test_delete_row(data_store_service, test_project):
    store = await data_store_service.create_store(
        test_project.id,
        DataStoreCreate(name="Delete Row Test", schema_definition=_make_schema()),
    )
    row = await data_store_service.insert_row(
        store.id, test_project.id, {"item_name": "Bread", "price": 2.50}
    )

    await data_store_service.delete_row(store.id, test_project.id, row.id)

    with pytest.raises(NotFoundError):
        await data_store_service.get_row(store.id, test_project.id, row.id)


@pytest.mark.asyncio
async def test_get_rows_paginated(data_store_service, test_project):
    store = await data_store_service.create_store(
        test_project.id,
        DataStoreCreate(name="Pagination Test", schema_definition=_make_schema()),
    )
    for i in range(5):
        await data_store_service.insert_row(
            store.id, test_project.id, {"item_name": f"Item {i}", "price": float(i)}
        )

    page = await data_store_service.get_rows(store.id, test_project.id, limit=2, offset=0)
    assert len(page.rows) == 2
    assert page.total == 5


@pytest.mark.asyncio
async def test_import_csv(data_store_service, test_project):
    store = await data_store_service.create_store(
        test_project.id,
        DataStoreCreate(name="CSV Test", schema_definition=_make_schema()),
    )
    csv_content = "name,amount\nBread,2.50\nMilk,1.20\nEggs,3.00"
    mapping = {"name": "item_name", "amount": "price"}

    result = await data_store_service.import_csv(
        store.id, test_project.id, csv_content, mapping
    )
    assert result.rows_imported == 3

    page = await data_store_service.get_rows(store.id, test_project.id)
    assert page.total == 3


@pytest.mark.asyncio
async def test_import_csv_type_error(data_store_service, test_project):
    store = await data_store_service.create_store(
        test_project.id,
        DataStoreCreate(
            name="CSV Error Test",
            schema_definition=_make_schema([("count", "integer", False)]),
        ),
    )
    csv_content = "count\n5\nnot_a_number\n3"
    mapping = {"count": "count"}

    with pytest.raises(ValidationError, match="Cannot convert"):
        await data_store_service.import_csv(
            store.id, test_project.id, csv_content, mapping
        )


@pytest.mark.asyncio
async def test_insert_row_missing_required(data_store_service, test_project):
    store = await data_store_service.create_store(
        test_project.id,
        DataStoreCreate(name="Required Test", schema_definition=_make_schema()),
    )
    with pytest.raises(ValidationError, match="Required column"):
        await data_store_service.insert_row(
            store.id, test_project.id, {"price": 2.50}
        )
```

- [ ] **Step 2: Run the tests**

Run:
```bash
cd backend && uv run python -m pytest tests/services/test_data_store_service.py -v -o "addopts="
```

Expected: All tests pass. Note: dynamic table DDL tests may need adjustment for SQLite (the test database). If `CREATE TABLE` via raw SQL fails with SQLite, the tests for row CRUD will need to use a real PostgreSQL test database or mock the DDL operations. Investigate and fix any failures.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/services/test_data_store_service.py
git commit -m "test: add DataStoreService unit tests"
```

---

## Task 7: Export Tool Enhancement

**Files:**
- Modify: `backend/app/services/agent/tools/export.py`
- Modify: `backend/app/services/agent/nodes.py`

- [ ] **Step 1: Update the export tool definition with config_schema**

Replace the contents of `backend/app/services/agent/tools/export.py`:

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
    output_keys=["exported"],
    config_schema={
        "type": "object",
        "properties": {
            "data_store_id": {
                "type": "string",
                "format": "uuid",
                "description": "Target data store to export rows into",
            },
        },
        "required": ["data_store_id"],
    },
    node_fn=export_node,
))
```

- [ ] **Step 2: Enhance the export_node to write to data store**

Replace the `export_node` function in `backend/app/services/agent/nodes.py`:

```python
async def export_node(state: dict) -> dict:
    """Export data to a project data store.

    Reads data_store_id from node config, maps state fields to table columns
    by name, and inserts a row.
    """
    from app.database import AsyncSessionLocal
    from app.repositories.data_store_repository import DataStoreRepository
    from app.services.data_store_service import DataStoreService

    logger.info("export_node: exporting data")

    config = state.get("node_config", {})
    data_store_id = config.get("data_store_id")

    if not data_store_id:
        logger.warning("export_node: no data_store_id configured, marking as exported only")
        return {
            **state,
            "exported": True,
            "current_step": "done",
        }

    # Use reviewed_data if available (post-review), otherwise extracted_data
    data = state.get("reviewed_data") or state.get("extracted_data") or {}

    async with AsyncSessionLocal() as session:
        repo = DataStoreRepository(session)
        service = DataStoreService(repo)

        store = await repo.get_by_id(data_store_id, state.get("project_id"))
        if not store:
            return {
                **state,
                "error": f"Data store {data_store_id} not found",
                "exported": False,
                "current_step": "failed",
            }

        # Map state fields to table columns by name
        col_names = {col["name"] for col in store.schema_definition}
        row_data = {k: v for k, v in data.items() if k in col_names}

        # Check required columns
        for col in store.schema_definition:
            if not col.get("nullable", True) and col["name"] not in row_data:
                return {
                    **state,
                    "error": f"Required column '{col['name']}' not found in pipeline data",
                    "exported": False,
                    "current_step": "failed",
                }

        await repo.insert_row(store.table_name, store.schema_definition, row_data)
        count = await repo.count_rows(store.table_name)
        await repo.update_row_count(store.id, count)

    return {
        **state,
        "exported": True,
        "current_step": "done",
    }
```

- [ ] **Step 3: Run existing tests to verify no regressions**

Run:
```bash
cd backend && uv run python -m pytest -v -o "addopts="
```

Expected: All existing tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/agent/tools/export.py backend/app/services/agent/nodes.py
git commit -m "feat: enhance export tool to write to project data stores"
```

---

## Task 8: Frontend Types + API Layer

**Files:**
- Create: `frontend/src/types/dataStore.ts`
- Create: `frontend/src/api/dataStores.ts`

- [ ] **Step 1: Create TypeScript types**

```typescript
// frontend/src/types/dataStore.ts

export interface ColumnDefinition {
  name: string
  type: 'text' | 'integer' | 'numeric' | 'boolean' | 'timestamptz'
  nullable: boolean
  description: string
}

export interface DataStore {
  id: string
  projectId: string
  name: string
  description: string | null
  tableName: string
  schemaDefinition: ColumnDefinition[]
  rowCount: number
  createdAt: string
  updatedAt: string
}

export interface DataStoreCreate {
  name: string
  description?: string
  schema_definition: ColumnDefinition[]
}

export interface DataStoreUpdate {
  name?: string
  description?: string
  schema_definition?: ColumnDefinition[]
}

export interface DataStoreRow {
  id: string
  data: Record<string, unknown>
  createdAt: string
  updatedAt: string
}

export interface DataStoreRowsResponse {
  rows: DataStoreRow[]
  total: number
  limit: number
  offset: number
}

export interface CsvImportResponse {
  rowsImported: number
}
```

- [ ] **Step 2: Create API wrappers**

```typescript
// frontend/src/api/dataStores.ts
import apiClient from './client'
import type {
  DataStore,
  DataStoreCreate,
  DataStoreUpdate,
  DataStoreRow,
  DataStoreRowsResponse,
  CsvImportResponse,
} from '@/types/dataStore'

// ── Store CRUD ────────────────────────────────────────────────────

export async function listDataStores(projectId: string): Promise<DataStore[]> {
  const response = await apiClient.get<DataStore[]>(
    `/projects/${projectId}/data-stores`
  )
  return response.data
}

export async function getDataStore(projectId: string, storeId: string): Promise<DataStore> {
  const response = await apiClient.get<DataStore>(
    `/projects/${projectId}/data-stores/${storeId}`
  )
  return response.data
}

export async function createDataStore(projectId: string, data: DataStoreCreate): Promise<DataStore> {
  const response = await apiClient.post<DataStore>(
    `/projects/${projectId}/data-stores`,
    data
  )
  return response.data
}

export async function updateDataStore(
  projectId: string,
  storeId: string,
  data: DataStoreUpdate
): Promise<DataStore> {
  const response = await apiClient.patch<DataStore>(
    `/projects/${projectId}/data-stores/${storeId}`,
    data
  )
  return response.data
}

export async function deleteDataStore(projectId: string, storeId: string): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/data-stores/${storeId}`)
}

// ── Row CRUD ──────────────────────────────────────────────────────

export async function listRows(
  projectId: string,
  storeId: string,
  limit = 50,
  offset = 0
): Promise<DataStoreRowsResponse> {
  const response = await apiClient.get<DataStoreRowsResponse>(
    `/projects/${projectId}/data-stores/${storeId}/rows`,
    { params: { limit, offset } }
  )
  return response.data
}

export async function getRow(
  projectId: string,
  storeId: string,
  rowId: string
): Promise<DataStoreRow> {
  const response = await apiClient.get<DataStoreRow>(
    `/projects/${projectId}/data-stores/${storeId}/rows/${rowId}`
  )
  return response.data
}

export async function insertRow(
  projectId: string,
  storeId: string,
  data: Record<string, unknown>
): Promise<DataStoreRow> {
  const response = await apiClient.post<DataStoreRow>(
    `/projects/${projectId}/data-stores/${storeId}/rows`,
    data
  )
  return response.data
}

export async function updateRow(
  projectId: string,
  storeId: string,
  rowId: string,
  data: Record<string, unknown>
): Promise<DataStoreRow> {
  const response = await apiClient.patch<DataStoreRow>(
    `/projects/${projectId}/data-stores/${storeId}/rows/${rowId}`,
    data
  )
  return response.data
}

export async function deleteRow(
  projectId: string,
  storeId: string,
  rowId: string
): Promise<void> {
  await apiClient.delete(
    `/projects/${projectId}/data-stores/${storeId}/rows/${rowId}`
  )
}

// ── CSV Import ────────────────────────────────────────────────────

export async function importCsv(
  projectId: string,
  storeId: string,
  file: File,
  columnMapping: Record<string, string>
): Promise<CsvImportResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('column_mapping', JSON.stringify(columnMapping))

  const response = await apiClient.post<CsvImportResponse>(
    `/projects/${projectId}/data-stores/${storeId}/import`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return response.data
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/dataStore.ts frontend/src/api/dataStores.ts
git commit -m "feat: add data store TypeScript types and API layer"
```

---

## Task 9: Frontend Hooks

**Files:**
- Create: `frontend/src/hooks/useDataStores.ts`
- Create: `frontend/src/hooks/useDataStoreRows.ts`

- [ ] **Step 1: Create the store-level hook**

```typescript
// frontend/src/hooks/useDataStores.ts
import { useState, useEffect, useCallback } from 'react'
import * as dataStoresApi from '@/api/dataStores'
import type { DataStore, DataStoreCreate, DataStoreUpdate } from '@/types/dataStore'

export interface UseDataStoresReturn {
  dataStores: DataStore[]
  isLoading: boolean
  error: string | null
  fetchDataStores: () => Promise<void>
  createDataStore: (data: DataStoreCreate) => Promise<DataStore>
  updateDataStore: (storeId: string, data: DataStoreUpdate) => Promise<DataStore>
  deleteDataStore: (storeId: string) => Promise<void>
}

export function useDataStores(projectId: string | null): UseDataStoresReturn {
  const [dataStores, setDataStores] = useState<DataStore[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchDataStores = useCallback(async () => {
    if (!projectId) {
      setDataStores([])
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const data = await dataStoresApi.listDataStores(projectId)
      setDataStores(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data stores')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  const createDataStore = useCallback(
    async (data: DataStoreCreate): Promise<DataStore> => {
      if (!projectId) throw new Error('No project selected')
      try {
        const store = await dataStoresApi.createDataStore(projectId, data)
        setDataStores((prev) => [store, ...prev])
        return store
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to create data store'
        setError(msg)
        throw err
      }
    },
    [projectId]
  )

  const updateDataStore = useCallback(
    async (storeId: string, data: DataStoreUpdate): Promise<DataStore> => {
      if (!projectId) throw new Error('No project selected')
      try {
        const updated = await dataStoresApi.updateDataStore(projectId, storeId, data)
        setDataStores((prev) =>
          prev.map((s) => (s.id === storeId ? updated : s))
        )
        return updated
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to update data store'
        setError(msg)
        throw err
      }
    },
    [projectId]
  )

  const deleteDataStore = useCallback(
    async (storeId: string): Promise<void> => {
      if (!projectId) throw new Error('No project selected')
      try {
        await dataStoresApi.deleteDataStore(projectId, storeId)
        setDataStores((prev) => prev.filter((s) => s.id !== storeId))
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to delete data store'
        setError(msg)
        throw err
      }
    },
    [projectId]
  )

  useEffect(() => {
    if (projectId) {
      fetchDataStores()
    }
  }, [projectId, fetchDataStores])

  return {
    dataStores,
    isLoading,
    error,
    fetchDataStores,
    createDataStore,
    updateDataStore,
    deleteDataStore,
  }
}
```

- [ ] **Step 2: Create the row-level hook**

```typescript
// frontend/src/hooks/useDataStoreRows.ts
import { useState, useEffect, useCallback } from 'react'
import * as dataStoresApi from '@/api/dataStores'
import type { DataStoreRow, DataStoreRowsResponse, CsvImportResponse } from '@/types/dataStore'

export interface UseDataStoreRowsReturn {
  rows: DataStoreRow[]
  total: number
  isLoading: boolean
  error: string | null
  page: number
  setPage: (page: number) => void
  pageSize: number
  fetchRows: () => Promise<void>
  insertRow: (data: Record<string, unknown>) => Promise<DataStoreRow>
  updateRow: (rowId: string, data: Record<string, unknown>) => Promise<DataStoreRow>
  deleteRow: (rowId: string) => Promise<void>
  importCsv: (file: File, columnMapping: Record<string, string>) => Promise<CsvImportResponse>
}

export function useDataStoreRows(
  projectId: string | null,
  storeId: string | null,
  pageSize = 50
): UseDataStoreRowsReturn {
  const [rows, setRows] = useState<DataStoreRow[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchRows = useCallback(async () => {
    if (!projectId || !storeId) {
      setRows([])
      setTotal(0)
      return
    }
    setIsLoading(true)
    setError(null)
    try {
      const data = await dataStoresApi.listRows(projectId, storeId, pageSize, page * pageSize)
      setRows(data.rows)
      setTotal(data.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch rows')
    } finally {
      setIsLoading(false)
    }
  }, [projectId, storeId, page, pageSize])

  const insertRow = useCallback(
    async (data: Record<string, unknown>): Promise<DataStoreRow> => {
      if (!projectId || !storeId) throw new Error('No store selected')
      try {
        const row = await dataStoresApi.insertRow(projectId, storeId, data)
        await fetchRows()
        return row
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to insert row'
        setError(msg)
        throw err
      }
    },
    [projectId, storeId, fetchRows]
  )

  const updateRow = useCallback(
    async (rowId: string, data: Record<string, unknown>): Promise<DataStoreRow> => {
      if (!projectId || !storeId) throw new Error('No store selected')
      try {
        const updated = await dataStoresApi.updateRow(projectId, storeId, rowId, data)
        setRows((prev) => prev.map((r) => (r.id === rowId ? updated : r)))
        return updated
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to update row'
        setError(msg)
        throw err
      }
    },
    [projectId, storeId]
  )

  const deleteRow = useCallback(
    async (rowId: string): Promise<void> => {
      if (!projectId || !storeId) throw new Error('No store selected')
      try {
        await dataStoresApi.deleteRow(projectId, storeId, rowId)
        await fetchRows()
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to delete row'
        setError(msg)
        throw err
      }
    },
    [projectId, storeId, fetchRows]
  )

  const importCsv = useCallback(
    async (file: File, columnMapping: Record<string, string>): Promise<CsvImportResponse> => {
      if (!projectId || !storeId) throw new Error('No store selected')
      try {
        const result = await dataStoresApi.importCsv(projectId, storeId, file, columnMapping)
        await fetchRows()
        return result
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to import CSV'
        setError(msg)
        throw err
      }
    },
    [projectId, storeId, fetchRows]
  )

  useEffect(() => {
    if (projectId && storeId) {
      fetchRows()
    }
  }, [projectId, storeId, fetchRows])

  return {
    rows,
    total,
    isLoading,
    error,
    page,
    setPage,
    pageSize,
    fetchRows,
    insertRow,
    updateRow,
    deleteRow,
    importCsv,
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useDataStores.ts frontend/src/hooks/useDataStoreRows.ts
git commit -m "feat: add useDataStores and useDataStoreRows hooks"
```

---

## Task 10: Frontend — Schema Editor Component

**Files:**
- Create: `frontend/src/components/data-stores/DataStoreSchemaEditor.tsx`

- [ ] **Step 1: Create the schema editor**

```typescript
// frontend/src/components/data-stores/DataStoreSchemaEditor.tsx
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { Trash2, Plus } from 'lucide-react'
import type { ColumnDefinition } from '@/types/dataStore'

const COLUMN_TYPES = [
  { value: 'text', label: 'Text' },
  { value: 'integer', label: 'Integer' },
  { value: 'numeric', label: 'Numeric' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'timestamptz', label: 'Timestamp' },
] as const

interface DataStoreSchemaEditorProps {
  columns: ColumnDefinition[]
  onChange: (columns: ColumnDefinition[]) => void
  disabled?: boolean
}

function normalizeColumnName(name: string): string {
  return name
    .toLowerCase()
    .replace(/\s+/g, '_')
    .replace(/[^a-z0-9_]/g, '')
    .replace(/^[^a-z]/, '')
}

export function DataStoreSchemaEditor({ columns, onChange, disabled }: DataStoreSchemaEditorProps) {
  const addColumn = () => {
    onChange([
      ...columns,
      { name: '', type: 'text', nullable: true, description: '' },
    ])
  }

  const removeColumn = (index: number) => {
    onChange(columns.filter((_, i) => i !== index))
  }

  const updateColumn = (index: number, field: keyof ColumnDefinition, value: unknown) => {
    const updated = columns.map((col, i) => {
      if (i !== index) return col
      if (field === 'name') {
        return { ...col, name: normalizeColumnName(value as string) }
      }
      return { ...col, [field]: value }
    })
    onChange(updated)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label>Columns</Label>
        <Button type="button" variant="outline" size="sm" onClick={addColumn} disabled={disabled}>
          <Plus className="h-4 w-4 mr-1" />
          Add Column
        </Button>
      </div>

      {columns.length === 0 && (
        <p className="text-sm text-muted-foreground py-4 text-center">
          No columns defined. Add at least one column.
        </p>
      )}

      {columns.map((col, index) => (
        <div key={index} className="flex items-center gap-2 p-3 border rounded-md bg-muted/30">
          <div className="flex-1">
            <Input
              placeholder="column_name"
              value={col.name}
              onChange={(e) => updateColumn(index, 'name', e.target.value)}
              disabled={disabled}
              className="font-mono text-sm"
            />
          </div>
          <div className="w-36">
            <Select
              value={col.type}
              onValueChange={(v) => updateColumn(index, 'type', v)}
              disabled={disabled}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {COLUMN_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-1">
            <Checkbox
              checked={col.nullable}
              onCheckedChange={(v) => updateColumn(index, 'nullable', !!v)}
              disabled={disabled}
            />
            <span className="text-xs text-muted-foreground">Nullable</span>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => removeColumn(index)}
            disabled={disabled}
            className="text-red-600 hover:text-red-700"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/data-stores/DataStoreSchemaEditor.tsx
git commit -m "feat: add DataStoreSchemaEditor component"
```

---

## Task 11: Frontend — Create + Edit Dialogs

**Files:**
- Create: `frontend/src/components/data-stores/DataStoreCreateDialog.tsx`
- Create: `frontend/src/components/data-stores/DataStoreEditDialog.tsx`

- [ ] **Step 1: Create the create dialog**

```typescript
// frontend/src/components/data-stores/DataStoreCreateDialog.tsx
import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { DataStoreSchemaEditor } from './DataStoreSchemaEditor'
import type { DataStoreCreate, ColumnDefinition } from '@/types/dataStore'

interface DataStoreCreateDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreate: (data: DataStoreCreate) => Promise<void>
  extractionSchemas?: Array<{ id: string; name: string; schemaDefinition: Record<string, unknown> }>
}

export function DataStoreCreateDialog({ open, onOpenChange, onCreate, extractionSchemas }: DataStoreCreateDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [columns, setColumns] = useState<ColumnDefinition[]>([
    { name: '', type: 'text', nullable: false, description: '' },
  ])
  const [isCreating, setIsCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSeedFromSchema = (schema: { schemaDefinition: Record<string, unknown> }) => {
    // Convert extraction schema properties to column definitions
    const props = (schema.schemaDefinition as { properties?: Record<string, { type?: string; description?: string }> }).properties || {}
    const required = (schema.schemaDefinition as { required?: string[] }).required || []
    const seeded: ColumnDefinition[] = Object.entries(props).map(([key, val]) => {
      const colName = key.toLowerCase().replace(/\s+/g, '_').replace(/[^a-z0-9_]/g, '')
      let colType: ColumnDefinition['type'] = 'text'
      if (val.type === 'integer' || val.type === 'number') colType = val.type === 'integer' ? 'integer' : 'numeric'
      else if (val.type === 'boolean') colType = 'boolean'
      return {
        name: colName,
        type: colType,
        nullable: !required.includes(key),
        description: val.description || '',
      }
    })
    setColumns(seeded)
  }

  const handleCreate = async () => {
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    const validColumns = columns.filter((c) => c.name.trim() !== '')
    if (validColumns.length === 0) {
      setError('At least one column is required')
      return
    }

    setIsCreating(true)
    setError(null)
    try {
      await onCreate({
        name: name.trim(),
        description: description.trim() || undefined,
        schema_definition: validColumns,
      })
      onOpenChange(false)
      setName('')
      setDescription('')
      setColumns([{ name: '', type: 'text', nullable: false, description: '' }])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create data store')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create Data Store</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="store-name">Name *</Label>
            <Input
              id="store-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Budget Items"
              disabled={isCreating}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="store-desc">Description</Label>
            <Textarea
              id="store-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              disabled={isCreating}
              rows={2}
            />
          </div>

          {extractionSchemas && extractionSchemas.length > 0 && (
            <div className="space-y-2">
              <Label>Seed from Extraction Schema</Label>
              <Select onValueChange={(id) => {
                const schema = extractionSchemas.find((s) => s.id === id)
                if (schema) handleSeedFromSchema(schema)
              }}>
                <SelectTrigger>
                  <SelectValue placeholder="Optional — pre-fill columns from a schema" />
                </SelectTrigger>
                <SelectContent>
                  {extractionSchemas.map((s) => (
                    <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <DataStoreSchemaEditor
            columns={columns}
            onChange={setColumns}
            disabled={isCreating}
          />

          {error && <div className="text-sm text-red-600">{error}</div>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isCreating}>
            Cancel
          </Button>
          <Button onClick={handleCreate} disabled={isCreating}>
            {isCreating ? 'Creating...' : 'Create Data Store'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Create the edit dialog**

```typescript
// frontend/src/components/data-stores/DataStoreEditDialog.tsx
import { useState, useEffect } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { DataStoreSchemaEditor } from './DataStoreSchemaEditor'
import type { DataStore, DataStoreUpdate, ColumnDefinition } from '@/types/dataStore'

interface DataStoreEditDialogProps {
  store: DataStore | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSave: (storeId: string, data: DataStoreUpdate) => Promise<void>
}

export function DataStoreEditDialog({ store, open, onOpenChange, onSave }: DataStoreEditDialogProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [columns, setColumns] = useState<ColumnDefinition[]>([])
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (store) {
      setName(store.name)
      setDescription(store.description || '')
      setColumns([...store.schemaDefinition])
      setError(null)
    }
  }, [store])

  const handleSave = async () => {
    if (!store || !name.trim()) {
      setError('Name is required')
      return
    }
    const validColumns = columns.filter((c) => c.name.trim() !== '')
    if (validColumns.length === 0) {
      setError('At least one column is required')
      return
    }

    setIsSaving(true)
    setError(null)
    try {
      await onSave(store.id, {
        name: name.trim(),
        description: description.trim() || undefined,
        schema_definition: validColumns,
      })
      onOpenChange(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update data store')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit Data Store</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>Name *</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} disabled={isSaving} />
          </div>

          <div className="space-y-2">
            <Label>Description</Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={isSaving}
              rows={2}
            />
          </div>

          <DataStoreSchemaEditor columns={columns} onChange={setColumns} disabled={isSaving} />

          {error && <div className="text-sm text-red-600">{error}</div>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Saving...' : 'Save Changes'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/data-stores/DataStoreCreateDialog.tsx frontend/src/components/data-stores/DataStoreEditDialog.tsx
git commit -m "feat: add DataStoreCreateDialog and DataStoreEditDialog"
```

---

## Task 12: Frontend — Data Grid + Row Dialogs

**Files:**
- Create: `frontend/src/components/data-stores/DataGrid.tsx`
- Create: `frontend/src/components/data-stores/AddRowDialog.tsx`

- [ ] **Step 1: Create the data grid component**

```typescript
// frontend/src/components/data-stores/DataGrid.tsx
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { MoreHorizontal, Check, X } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import type { ColumnDefinition, DataStoreRow } from '@/types/dataStore'

interface DataGridProps {
  columns: ColumnDefinition[]
  rows: DataStoreRow[]
  total: number
  page: number
  pageSize: number
  onPageChange: (page: number) => void
  onUpdateRow: (rowId: string, data: Record<string, unknown>) => Promise<void>
  onDeleteRow: (rowId: string) => Promise<void>
}

export function DataGrid({
  columns,
  rows,
  total,
  page,
  pageSize,
  onPageChange,
  onUpdateRow,
  onDeleteRow,
}: DataGridProps) {
  const [editingRowId, setEditingRowId] = useState<string | null>(null)
  const [editData, setEditData] = useState<Record<string, unknown>>({})

  const startEdit = (row: DataStoreRow) => {
    setEditingRowId(row.id)
    setEditData({ ...row.data })
  }

  const cancelEdit = () => {
    setEditingRowId(null)
    setEditData({})
  }

  const saveEdit = async () => {
    if (!editingRowId) return
    await onUpdateRow(editingRowId, editData)
    setEditingRowId(null)
    setEditData({})
  }

  const totalPages = Math.ceil(total / pageSize)

  const renderCellInput = (col: ColumnDefinition, value: unknown) => {
    if (col.type === 'boolean') {
      return (
        <Checkbox
          checked={!!value}
          onCheckedChange={(v) =>
            setEditData((prev) => ({ ...prev, [col.name]: !!v }))
          }
        />
      )
    }
    return (
      <Input
        value={value != null ? String(value) : ''}
        onChange={(e) =>
          setEditData((prev) => ({ ...prev, [col.name]: e.target.value }))
        }
        type={col.type === 'integer' || col.type === 'numeric' ? 'number' : 'text'}
        className="h-8 text-sm"
      />
    )
  }

  const renderCellValue = (col: ColumnDefinition, value: unknown) => {
    if (value == null) return <span className="text-muted-foreground">—</span>
    if (col.type === 'boolean') return value ? 'Yes' : 'No'
    return String(value)
  }

  if (rows.length === 0 && total === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center border rounded-lg">
        <p className="text-muted-foreground">No data yet. Add rows manually or import a CSV.</p>
      </div>
    )
  }

  return (
    <div>
      <div className="border rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr>
                {columns.map((col) => (
                  <th key={col.name} className="text-left py-3 px-4 font-medium text-sm">
                    {col.name}
                    <span className="text-xs text-muted-foreground ml-1">({col.type})</span>
                  </th>
                ))}
                <th className="text-left py-3 px-4 font-medium text-sm">Created</th>
                <th className="text-right py-3 px-4 font-medium text-sm w-20">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((row) => (
                <tr key={row.id} className="hover:bg-primary/5 transition-colors">
                  {columns.map((col) => (
                    <td key={col.name} className="py-2 px-4 text-sm">
                      {editingRowId === row.id
                        ? renderCellInput(col, editData[col.name])
                        : renderCellValue(col, row.data[col.name])}
                    </td>
                  ))}
                  <td className="py-2 px-4 text-sm text-muted-foreground">
                    {formatDistanceToNow(new Date(row.createdAt), { addSuffix: true })}
                  </td>
                  <td className="py-2 px-4 text-right">
                    {editingRowId === row.id ? (
                      <div className="flex justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={saveEdit}>
                          <Check className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={cancelEdit}>
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    ) : (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => startEdit(row)}>Edit</DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => onDeleteRow(row.id)}
                            className="text-red-600"
                          >
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-muted-foreground">
            Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, total)} of {total}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(page - 1)}
              disabled={page === 0}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages - 1}
            >
              Next
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create the add row dialog**

```typescript
// frontend/src/components/data-stores/AddRowDialog.tsx
import { useState } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import type { ColumnDefinition } from '@/types/dataStore'

interface AddRowDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  columns: ColumnDefinition[]
  onAdd: (data: Record<string, unknown>) => Promise<void>
}

export function AddRowDialog({ open, onOpenChange, columns, onAdd }: AddRowDialogProps) {
  const [data, setData] = useState<Record<string, string>>({})
  const [isAdding, setIsAdding] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleAdd = async () => {
    setIsAdding(true)
    setError(null)
    try {
      const coerced: Record<string, unknown> = {}
      for (const col of columns) {
        const raw = data[col.name]
        if (raw === undefined || raw === '') {
          if (!col.nullable) {
            setError(`${col.name} is required`)
            setIsAdding(false)
            return
          }
          continue
        }
        if (col.type === 'integer') coerced[col.name] = parseInt(raw, 10)
        else if (col.type === 'numeric') coerced[col.name] = parseFloat(raw)
        else if (col.type === 'boolean') coerced[col.name] = raw === 'true'
        else coerced[col.name] = raw
      }

      await onAdd(coerced)
      onOpenChange(false)
      setData({})
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add row')
    } finally {
      setIsAdding(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Row</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {columns.map((col) => (
            <div key={col.name} className="space-y-2">
              <Label>
                {col.name}
                {!col.nullable && <span className="text-red-500 ml-1">*</span>}
                <span className="text-xs text-muted-foreground ml-2">({col.type})</span>
              </Label>
              {col.type === 'boolean' ? (
                <div className="flex items-center gap-2">
                  <Checkbox
                    checked={data[col.name] === 'true'}
                    onCheckedChange={(v) =>
                      setData((prev) => ({ ...prev, [col.name]: v ? 'true' : 'false' }))
                    }
                    disabled={isAdding}
                  />
                  <span className="text-sm">{data[col.name] === 'true' ? 'Yes' : 'No'}</span>
                </div>
              ) : (
                <Input
                  value={data[col.name] || ''}
                  onChange={(e) =>
                    setData((prev) => ({ ...prev, [col.name]: e.target.value }))
                  }
                  type={col.type === 'integer' || col.type === 'numeric' ? 'number' : 'text'}
                  placeholder={col.nullable ? 'Optional' : 'Required'}
                  disabled={isAdding}
                />
              )}
            </div>
          ))}

          {error && <div className="text-sm text-red-600">{error}</div>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isAdding}>
            Cancel
          </Button>
          <Button onClick={handleAdd} disabled={isAdding}>
            {isAdding ? 'Adding...' : 'Add Row'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/data-stores/DataGrid.tsx frontend/src/components/data-stores/AddRowDialog.tsx
git commit -m "feat: add DataGrid and AddRowDialog components"
```

---

## Task 13: Frontend — CSV Import Dialog

**Files:**
- Create: `frontend/src/components/data-stores/CsvImportDialog.tsx`

- [ ] **Step 1: Create the CSV import dialog**

```typescript
// frontend/src/components/data-stores/CsvImportDialog.tsx
import { useState, useCallback } from 'react'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Upload } from 'lucide-react'
import type { ColumnDefinition, CsvImportResponse } from '@/types/dataStore'

interface CsvImportDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  columns: ColumnDefinition[]
  onImport: (file: File, columnMapping: Record<string, string>) => Promise<CsvImportResponse>
}

export function CsvImportDialog({ open, onOpenChange, columns, onImport }: CsvImportDialogProps) {
  const [file, setFile] = useState<File | null>(null)
  const [csvHeaders, setCsvHeaders] = useState<string[]>([])
  const [previewRows, setPreviewRows] = useState<string[][]>([])
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [isImporting, setIsImporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<CsvImportResponse | null>(null)

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = e.target.files?.[0]
      if (!selected) return

      setFile(selected)
      setError(null)
      setResult(null)

      const reader = new FileReader()
      reader.onload = (event) => {
        const text = event.target?.result as string
        const lines = text.split('\n').filter((l) => l.trim())
        if (lines.length === 0) {
          setError('CSV file is empty')
          return
        }

        const headers = lines[0].split(',').map((h) => h.trim().replace(/^"|"$/g, ''))
        setCsvHeaders(headers)

        const preview = lines.slice(1, 6).map((line) =>
          line.split(',').map((v) => v.trim().replace(/^"|"$/g, ''))
        )
        setPreviewRows(preview)

        // Auto-map by name match
        const autoMapping: Record<string, string> = {}
        const storeColNames = columns.map((c) => c.name)
        for (const header of headers) {
          const normalized = header.toLowerCase().replace(/\s+/g, '_')
          if (storeColNames.includes(normalized)) {
            autoMapping[header] = normalized
          }
        }
        setMapping(autoMapping)
      }
      reader.readAsText(selected)
    },
    [columns]
  )

  const handleImport = async () => {
    if (!file) return

    const activeMappings = Object.entries(mapping).filter(([, v]) => v !== '')
    if (activeMappings.length === 0) {
      setError('Map at least one column')
      return
    }

    // Check required columns
    const mappedStoreCols = new Set(activeMappings.map(([, v]) => v))
    for (const col of columns) {
      if (!col.nullable && !mappedStoreCols.has(col.name)) {
        setError(`Required column "${col.name}" is not mapped`)
        return
      }
    }

    setIsImporting(true)
    setError(null)
    try {
      const mappingObj = Object.fromEntries(activeMappings)
      const res = await onImport(file, mappingObj)
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setIsImporting(false)
    }
  }

  const handleClose = () => {
    onOpenChange(false)
    setFile(null)
    setCsvHeaders([])
    setPreviewRows([])
    setMapping({})
    setError(null)
    setResult(null)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Import CSV</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* File selector */}
          <div className="space-y-2">
            <Label>CSV File</Label>
            <div className="flex items-center gap-2">
              <label className="flex items-center gap-2 px-4 py-2 border rounded-md cursor-pointer hover:bg-muted/50 transition-colors">
                <Upload className="h-4 w-4" />
                <span className="text-sm">{file ? file.name : 'Choose file...'}</span>
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileSelect}
                  className="hidden"
                />
              </label>
            </div>
          </div>

          {/* Column mapping */}
          {csvHeaders.length > 0 && (
            <div className="space-y-3">
              <Label>Column Mapping</Label>
              <div className="border rounded-md">
                <table className="w-full">
                  <thead className="bg-muted/50">
                    <tr>
                      <th className="text-left py-2 px-3 text-sm font-medium">CSV Column</th>
                      <th className="text-left py-2 px-3 text-sm font-medium">→</th>
                      <th className="text-left py-2 px-3 text-sm font-medium">Store Column</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {csvHeaders.map((header) => (
                      <tr key={header}>
                        <td className="py-2 px-3 text-sm font-mono">{header}</td>
                        <td className="py-2 px-3 text-sm text-muted-foreground">→</td>
                        <td className="py-2 px-3">
                          <Select
                            value={mapping[header] || '_skip'}
                            onValueChange={(v) =>
                              setMapping((prev) => ({
                                ...prev,
                                [header]: v === '_skip' ? '' : v,
                              }))
                            }
                          >
                            <SelectTrigger className="h-8">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="_skip">— Skip —</SelectItem>
                              {columns.map((col) => (
                                <SelectItem key={col.name} value={col.name}>
                                  {col.name} ({col.type})
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Preview */}
          {previewRows.length > 0 && (
            <div className="space-y-2">
              <Label>Preview (first {previewRows.length} rows)</Label>
              <div className="border rounded-md overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="bg-muted/50">
                    <tr>
                      {csvHeaders.map((h) => (
                        <th key={h} className="py-1 px-2 text-left font-medium">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {previewRows.map((row, i) => (
                      <tr key={i}>
                        {row.map((cell, j) => (
                          <td key={j} className="py-1 px-2">{cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {result && (
            <div className="text-sm text-green-600">
              Successfully imported {result.rowsImported} rows.
            </div>
          )}
          {error && <div className="text-sm text-red-600">{error}</div>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            {result ? 'Close' : 'Cancel'}
          </Button>
          {!result && (
            <Button onClick={handleImport} disabled={!file || isImporting}>
              {isImporting ? 'Importing...' : 'Import'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/data-stores/CsvImportDialog.tsx
git commit -m "feat: add CsvImportDialog component"
```

---

## Task 14: Frontend — Pages + Routing

**Files:**
- Create: `frontend/src/pages/DataStoresPage.tsx`
- Create: `frontend/src/pages/DataStoreDetailPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/config/navigation.ts`

- [ ] **Step 1: Create the list page**

```typescript
// frontend/src/pages/DataStoresPage.tsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { MoreHorizontal, Plus, Database } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { toast } from 'sonner'
import { useDataStores } from '@/hooks/useDataStores'
import { useProject } from '@/contexts/ProjectContext'
import { DataStoreCreateDialog } from '@/components/data-stores/DataStoreCreateDialog'
import * as extractionApi from '@/api/extraction'
import type { DataStore } from '@/types/dataStore'
import type { ExtractionSchema } from '@/types/extraction'

export default function DataStoresPage() {
  const { selectedProject } = useProject()
  const projectId = selectedProject?.id || null
  const navigate = useNavigate()

  const { dataStores, isLoading, error, createDataStore, deleteDataStore } = useDataStores(projectId)
  const [extractionSchemas, setExtractionSchemas] = useState<ExtractionSchema[]>([])

  const [createOpen, setCreateOpen] = useState(false)

  // Fetch extraction schemas when create dialog opens (for seed feature)
  useEffect(() => {
    if (createOpen && projectId) {
      extractionApi.listExtractionSchemas(projectId).then(setExtractionSchemas).catch(() => {})
    }
  }, [createOpen, projectId])

  const handleCreate = async (data: Parameters<typeof createDataStore>[0]) => {
    const store = await createDataStore(data)
    toast.success(`Data store "${store.name}" created`)
  }

  const handleDelete = async (store: DataStore) => {
    try {
      await deleteDataStore(store.id)
      toast.success(`Data store "${store.name}" deleted`)
    } catch {
      toast.error('Failed to delete data store')
    }
  }

  if (!projectId) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-muted-foreground">Select a project to manage data stores.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Data Stores</h1>
          <p className="text-muted-foreground">Manage project data tables</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Create Data Store
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : dataStores.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center border rounded-lg">
          <Database className="h-12 w-12 text-muted-foreground mb-4" />
          <h3 className="font-medium mb-1">No data stores yet</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Create a data store to manage project data.
          </p>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Create Data Store
          </Button>
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left py-3 px-4 font-medium text-sm">Name</th>
                <th className="text-left py-3 px-4 font-medium text-sm">Columns</th>
                <th className="text-left py-3 px-4 font-medium text-sm">Rows</th>
                <th className="text-left py-3 px-4 font-medium text-sm">Created</th>
                <th className="text-right py-3 px-4 font-medium text-sm w-20">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {dataStores.map((store) => (
                <tr key={store.id} className="hover:bg-primary/5 transition-colors">
                  <td className="py-3 px-4">
                    <button
                      onClick={() => navigate(`/projects/${projectId}/data-stores/${store.id}`)}
                      className="font-medium hover:text-primary"
                    >
                      {store.name}
                    </button>
                    {store.description && (
                      <p className="text-sm text-muted-foreground mt-0.5 line-clamp-1">
                        {store.description}
                      </p>
                    )}
                  </td>
                  <td className="py-3 px-4 text-sm">{store.schemaDefinition.length}</td>
                  <td className="py-3 px-4 text-sm">{store.rowCount}</td>
                  <td className="py-3 px-4 text-sm text-muted-foreground">
                    {formatDistanceToNow(new Date(store.createdAt), { addSuffix: true })}
                  </td>
                  <td className="py-3 px-4 text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          onClick={() => navigate(`/projects/${projectId}/data-stores/${store.id}`)}
                        >
                          View
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => handleDelete(store)}
                          className="text-red-600"
                        >
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <DataStoreCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreate={handleCreate}
        extractionSchemas={extractionSchemas}
      />
    </div>
  )
}
```

- [ ] **Step 2: Create the detail page**

```typescript
// frontend/src/pages/DataStoreDetailPage.tsx
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, Plus, Upload, Pencil, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { useProject } from '@/contexts/ProjectContext'
import { useDataStoreRows } from '@/hooks/useDataStoreRows'
import { DataGrid } from '@/components/data-stores/DataGrid'
import { AddRowDialog } from '@/components/data-stores/AddRowDialog'
import { CsvImportDialog } from '@/components/data-stores/CsvImportDialog'
import { DataStoreEditDialog } from '@/components/data-stores/DataStoreEditDialog'
import * as dataStoresApi from '@/api/dataStores'
import type { DataStore, DataStoreUpdate } from '@/types/dataStore'

export default function DataStoreDetailPage() {
  const { storeId } = useParams<{ storeId: string }>()
  const { selectedProject } = useProject()
  const projectId = selectedProject?.id || null
  const navigate = useNavigate()

  const [store, setStore] = useState<DataStore | null>(null)
  const [storeLoading, setStoreLoading] = useState(true)
  const [storeError, setStoreError] = useState<string | null>(null)

  const [addRowOpen, setAddRowOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)

  const {
    rows,
    total,
    isLoading: rowsLoading,
    error: rowsError,
    page,
    setPage,
    pageSize,
    fetchRows,
    insertRow,
    updateRow,
    deleteRow,
    importCsv,
  } = useDataStoreRows(projectId, storeId || null)

  useEffect(() => {
    if (!projectId || !storeId) return
    setStoreLoading(true)
    dataStoresApi
      .getDataStore(projectId, storeId)
      .then(setStore)
      .catch((err) => setStoreError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setStoreLoading(false))
  }, [projectId, storeId])

  const handleAddRow = async (data: Record<string, unknown>) => {
    await insertRow(data)
    toast.success('Row added')
  }

  const handleUpdateRow = async (rowId: string, data: Record<string, unknown>) => {
    await updateRow(rowId, data)
    toast.success('Row updated')
  }

  const handleDeleteRow = async (rowId: string) => {
    await deleteRow(rowId)
    toast.success('Row deleted')
  }

  const handleImport = async (file: File, mapping: Record<string, string>) => {
    const result = await importCsv(file, mapping)
    toast.success(`Imported ${result.rowsImported} rows`)
    return result
  }

  const handleEditStore = async (id: string, data: DataStoreUpdate) => {
    if (!projectId) return
    const updated = await dataStoresApi.updateDataStore(projectId, id, data)
    setStore(updated)
    toast.success('Data store updated')
    await fetchRows()
  }

  const handleDeleteStore = async () => {
    if (!projectId || !storeId) return
    await dataStoresApi.deleteDataStore(projectId, storeId)
    toast.success('Data store deleted')
    navigate(`/projects/${projectId}/data-stores`)
  }

  if (storeLoading) {
    return <Skeleton className="h-96 w-full" />
  }

  if (storeError || !store) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{storeError || 'Data store not found'}</AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/projects/${projectId}/data-stores`)}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{store.name}</h1>
            {store.description && (
              <p className="text-muted-foreground">{store.description}</p>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4 mr-1" /> Edit
          </Button>
          <Button variant="outline" size="sm" onClick={handleDeleteStore} className="text-red-600">
            <Trash2 className="h-4 w-4 mr-1" /> Delete
          </Button>
        </div>
      </div>

      {/* Schema summary */}
      <div className="flex flex-wrap gap-2">
        {store.schemaDefinition.map((col) => (
          <Badge key={col.name} variant="secondary" className="font-mono text-xs">
            {col.name}: {col.type}
            {!col.nullable && ' *'}
          </Badge>
        ))}
      </div>

      {/* Data actions */}
      <div className="flex gap-2">
        <Button size="sm" onClick={() => setAddRowOpen(true)}>
          <Plus className="h-4 w-4 mr-1" /> Add Row
        </Button>
        <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}>
          <Upload className="h-4 w-4 mr-1" /> Import CSV
        </Button>
      </div>

      {rowsError && (
        <Alert variant="destructive">
          <AlertDescription>{rowsError}</AlertDescription>
        </Alert>
      )}

      {/* Data grid */}
      {rowsLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <DataGrid
          columns={store.schemaDefinition}
          rows={rows}
          total={total}
          page={page}
          pageSize={pageSize}
          onPageChange={setPage}
          onUpdateRow={handleUpdateRow}
          onDeleteRow={handleDeleteRow}
        />
      )}

      {/* Dialogs */}
      <AddRowDialog
        open={addRowOpen}
        onOpenChange={setAddRowOpen}
        columns={store.schemaDefinition}
        onAdd={handleAddRow}
      />
      <CsvImportDialog
        open={importOpen}
        onOpenChange={setImportOpen}
        columns={store.schemaDefinition}
        onImport={handleImport}
      />
      <DataStoreEditDialog
        store={store}
        open={editOpen}
        onOpenChange={setEditOpen}
        onSave={handleEditStore}
      />
    </div>
  )
}
```

- [ ] **Step 3: Add routes to App.tsx**

Add the import at the top of `frontend/src/App.tsx`:

```typescript
import DataStoresPage from './pages/DataStoresPage'
import DataStoreDetailPage from './pages/DataStoreDetailPage'
```

Add these route entries inside the `children` array of the private route, after the `projects/:projectId/documents` route:

```typescript
{
  path: 'projects/:projectId/data-stores',
  element: <DataStoresPage />,
  handle: { breadcrumb: 'Data Stores' },
},
{
  path: 'projects/:projectId/data-stores/:storeId',
  element: <DataStoreDetailPage />,
  handle: { breadcrumb: 'Data Store Detail' },
},
```

- [ ] **Step 4: Add navigation item**

In `frontend/src/config/navigation.ts`, add a new entry. Import `HardDrive` from lucide-react (to avoid conflict with the existing `Database` icon used for Index):

```typescript
import { LayoutDashboard, FolderKanban, FileText, Database, BarChart3, Settings, FileSearch, Bot, HardDrive } from 'lucide-react'
```

Add the entry after the Extraction item:

```typescript
{ label: 'Data Stores', href: '/data-stores', icon: HardDrive, activeColor: 'border-l-cyan-500' },
```

Note: This nav item uses `/data-stores` as the href for sidebar highlighting. The actual pages are project-scoped at `/projects/:projectId/data-stores`. The sidebar click behavior should navigate to the data stores page for the currently selected project. This may need adjustment based on how the sidebar currently handles project-scoped routes — check how the existing "Documents" nav item works and follow the same pattern.

- [ ] **Step 5: Run lint and build**

Run:
```bash
cd frontend && npm run lint && npm run build
```

Expected: No lint errors, build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/DataStoresPage.tsx frontend/src/pages/DataStoreDetailPage.tsx frontend/src/App.tsx frontend/src/config/navigation.ts
git commit -m "feat: add Data Stores pages with routing and navigation"
```

---

## Task 15: End-to-End Verification

- [ ] **Step 1: Start the backend**

Run:
```bash
cd backend && uvicorn app.main:app --reload
```

Expected: Server starts without errors.

- [ ] **Step 2: Start the frontend**

Run:
```bash
cd frontend && npm run dev
```

Expected: Dev server starts without errors.

- [ ] **Step 3: Manual verification checklist**

Test in browser:

1. Navigate to Data Stores page — should show empty state
2. Create a data store with columns (e.g., "Budget Items" with item_name:text, amount:numeric, category:text)
3. Verify it appears in the list with 0 rows
4. Click into the detail page
5. Add a row manually via Add Row dialog
6. Verify the row appears in the data grid
7. Edit the row inline — change a value, click save
8. Delete the row
9. Import a CSV file:
   - Create a test CSV: `name,amount,cat\nBread,2.50,Food\nMilk,1.20,Dairy`
   - Map columns: name→item_name, amount→amount, cat→category
   - Verify 2 rows imported
10. Edit the data store (add a new column)
11. Delete the data store
12. Verify it's gone from the list

- [ ] **Step 4: Run all backend tests**

Run:
```bash
cd backend && uv run python -m pytest -v -o "addopts="
```

Expected: All tests pass.

- [ ] **Step 5: Run frontend build**

Run:
```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 6: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: address issues found during end-to-end verification"
```
