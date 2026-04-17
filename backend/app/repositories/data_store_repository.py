# backend/app/repositories/data_store_repository.py
import json
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
        columns.append("source_metadata JSONB NULL")

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

    async def insert_row(self, table_name: str, schema_definition: list[dict], data: dict, source_metadata: dict | None = None) -> dict:
        """Insert a single row and return it."""
        if not TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"Invalid table name: {table_name}")

        col_names = [col["name"] for col in schema_definition if col["name"] in data]
        if not col_names:
            raise ValueError("No valid columns to insert")

        # Add source_metadata if provided (serialize dict → JSON string for asyncpg)
        if source_metadata is not None:
            col_names.append("source_metadata")
            data = {**data, "source_metadata": json.dumps(source_metadata)}

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
                params["source_metadata"] = json.dumps(source_metadata)
            params_list.append(params)

        for params in params_list:
            await self.session.execute(text(sql), params)

        await self.session.commit()
        return len(params_list)
