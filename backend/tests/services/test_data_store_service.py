# backend/tests/services/test_data_store_service.py
"""Service-layer tests for DataStoreService.

Dynamic table operations (CREATE TABLE, INSERT ... RETURNING *, etc.) use
PostgreSQL-specific SQL, so they're mocked here.  Metadata CRUD runs against
the real SQLite in-memory test database to exercise the ORM layer.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4, UUID
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


# ── Fixtures ───────────────────────────────────────────────────────────────────

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


def _make_row(data: dict, row_id: UUID | None = None) -> dict:
    """Build a fake row dict as the repository would return."""
    now = datetime.now(tz=timezone.utc)
    return {
        "id": row_id or uuid4(),
        "created_at": now,
        "updated_at": now,
        **data,
    }


# ── Create store ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_store_success(data_store_service, test_project):
    with patch.object(
        data_store_service.repo, "create_table", new_callable=AsyncMock
    ) as mock_create_table:
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
    mock_create_table.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_store_duplicate_name(data_store_service, test_project):
    data = DataStoreCreate(name="Dupes", schema_definition=_make_schema())

    with patch.object(
        data_store_service.repo, "create_table", new_callable=AsyncMock
    ):
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


# ── List stores ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_stores(data_store_service, test_project):
    with patch.object(
        data_store_service.repo, "create_table", new_callable=AsyncMock
    ):
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


# ── Delete store ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_store(data_store_service, test_project):
    with patch.object(
        data_store_service.repo, "create_table", new_callable=AsyncMock
    ), patch.object(
        data_store_service.repo, "drop_table", new_callable=AsyncMock
    ):
        store = await data_store_service.create_store(
            test_project.id,
            DataStoreCreate(name="To Delete", schema_definition=_make_schema()),
        )
        await data_store_service.delete_store(store.id, test_project.id)

    with pytest.raises(NotFoundError):
        await data_store_service.get_store(store.id, test_project.id)


# ── Insert and get row ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_insert_and_get_row(data_store_service, test_project):
    row_id = uuid4()
    fake_row = _make_row({"item_name": "Bread", "price": 2.50}, row_id)

    with patch.object(
        data_store_service.repo, "create_table", new_callable=AsyncMock
    ), patch.object(
        data_store_service.repo, "insert_row", new_callable=AsyncMock, return_value=fake_row
    ), patch.object(
        data_store_service.repo, "count_rows", new_callable=AsyncMock, return_value=1
    ), patch.object(
        data_store_service.repo, "update_row_count", new_callable=AsyncMock
    ), patch.object(
        data_store_service.repo, "get_row", new_callable=AsyncMock, return_value=fake_row
    ):
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


# ── Update row ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_row(data_store_service, test_project):
    row_id = uuid4()
    inserted_row = _make_row({"item_name": "Bread", "price": 2.50}, row_id)
    updated_row = _make_row({"item_name": "Bread", "price": 3.00}, row_id)

    with patch.object(
        data_store_service.repo, "create_table", new_callable=AsyncMock
    ), patch.object(
        data_store_service.repo, "insert_row", new_callable=AsyncMock, return_value=inserted_row
    ), patch.object(
        data_store_service.repo, "count_rows", new_callable=AsyncMock, return_value=1
    ), patch.object(
        data_store_service.repo, "update_row_count", new_callable=AsyncMock
    ), patch.object(
        data_store_service.repo, "update_row", new_callable=AsyncMock, return_value=updated_row
    ):
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


# ── Delete row ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_row(data_store_service, test_project):
    row_id = uuid4()
    fake_row = _make_row({"item_name": "Bread", "price": 2.50}, row_id)

    with patch.object(
        data_store_service.repo, "create_table", new_callable=AsyncMock
    ), patch.object(
        data_store_service.repo, "insert_row", new_callable=AsyncMock, return_value=fake_row
    ), patch.object(
        data_store_service.repo, "count_rows", new_callable=AsyncMock, return_value=0
    ), patch.object(
        data_store_service.repo, "update_row_count", new_callable=AsyncMock
    ), patch.object(
        data_store_service.repo, "delete_row", new_callable=AsyncMock, return_value=True
    ), patch.object(
        data_store_service.repo, "get_row", new_callable=AsyncMock, return_value=None
    ):
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


# ── Paginated rows ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_rows_paginated(data_store_service, test_project):
    fake_rows = [
        _make_row({"item_name": f"Item {i}", "price": float(i)}) for i in range(5)
    ]

    with patch.object(
        data_store_service.repo, "create_table", new_callable=AsyncMock
    ), patch.object(
        data_store_service.repo, "get_rows", new_callable=AsyncMock, return_value=fake_rows[:2]
    ), patch.object(
        data_store_service.repo, "count_rows", new_callable=AsyncMock, return_value=5
    ):
        store = await data_store_service.create_store(
            test_project.id,
            DataStoreCreate(name="Pagination Test", schema_definition=_make_schema()),
        )
        page = await data_store_service.get_rows(store.id, test_project.id, limit=2, offset=0)

    assert len(page.rows) == 2
    assert page.total == 5


# ── CSV import ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_import_csv(data_store_service, test_project):
    csv_content = "name,amount\nBread,2.50\nMilk,1.20\nEggs,3.00"
    mapping = {"name": "item_name", "amount": "price"}

    with patch.object(
        data_store_service.repo, "create_table", new_callable=AsyncMock
    ), patch.object(
        data_store_service.repo, "bulk_insert", new_callable=AsyncMock, return_value=3
    ), patch.object(
        data_store_service.repo, "count_rows", new_callable=AsyncMock, return_value=3
    ), patch.object(
        data_store_service.repo, "update_row_count", new_callable=AsyncMock
    ), patch.object(
        data_store_service.repo, "get_rows", new_callable=AsyncMock, return_value=[
            _make_row({"item_name": "Bread", "price": 2.50}),
            _make_row({"item_name": "Milk", "price": 1.20}),
            _make_row({"item_name": "Eggs", "price": 3.00}),
        ]
    ):
        store = await data_store_service.create_store(
            test_project.id,
            DataStoreCreate(name="CSV Test", schema_definition=_make_schema()),
        )
        result = await data_store_service.import_csv(
            store.id, test_project.id, csv_content, mapping
        )
        assert result.rows_imported == 3

        page = await data_store_service.get_rows(store.id, test_project.id)
        assert page.total == 3


@pytest.mark.asyncio
async def test_import_csv_type_error(data_store_service, test_project):
    csv_content = "count\n5\nnot_a_number\n3"
    mapping = {"count": "count"}

    with patch.object(
        data_store_service.repo, "create_table", new_callable=AsyncMock
    ):
        store = await data_store_service.create_store(
            test_project.id,
            DataStoreCreate(
                name="CSV Error Test",
                schema_definition=_make_schema([("count", "integer", False)]),
            ),
        )
        with pytest.raises(ValidationError, match="Cannot convert"):
            await data_store_service.import_csv(
                store.id, test_project.id, csv_content, mapping
            )


# ── Insert row missing required column ────────────────────────────────────────

@pytest.mark.asyncio
async def test_insert_row_missing_required(data_store_service, test_project):
    with patch.object(
        data_store_service.repo, "create_table", new_callable=AsyncMock
    ):
        store = await data_store_service.create_store(
            test_project.id,
            DataStoreCreate(name="Required Test", schema_definition=_make_schema()),
        )
        # item_name is NOT NULL; omitting it should raise ValidationError
        with pytest.raises(ValidationError, match="Required column"):
            await data_store_service.insert_row(
                store.id, test_project.id, {"price": 2.50}
            )
