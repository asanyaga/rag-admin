# backend/app/services/data_store_service.py
import csv
import io
from datetime import datetime, timezone
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
            if 'uq_project_data_stores_project_name' in error_str or \
               ('project_data_stores.project_id' in error_str and 'project_data_stores.name' in error_str):
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
            if 'uq_project_data_stores_project_name' in error_str or \
               ('project_data_stores.project_id' in error_str and 'project_data_stores.name' in error_str):
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
        source_metadata = {"source": "manual", "created_at": datetime.now(tz=timezone.utc).isoformat()}
        row = await self.repo.insert_row(store.table_name, store.schema_definition, data, source_metadata=source_metadata)
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

    async def import_csv(self, store_id: UUID, project_id: UUID, csv_content: str, column_mapping: dict[str, str], filename: str | None = None) -> CsvImportResponse:
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

        source_metadata = {
            "source": "csv_import",
            "filename": filename or "unknown",
            "imported_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        count = await self.repo.bulk_insert(store.table_name, store.schema_definition, rows, source_metadata=source_metadata)
        await self._refresh_row_count(store)
        return CsvImportResponse(rows_imported=count)

    # ── Export operations ────────────────────────────────────────────

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

    # ── Helpers ────────────────────────────────────────────────────

    def _validate_schema(self, columns: list[ColumnDefinition]) -> None:
        """Validate all columns in a schema definition."""
        names = set()
        reserved = {"id", "created_at", "updated_at", "source_metadata"}
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
            source_metadata=row.get("source_metadata"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
