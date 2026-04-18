# Document Folders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add project-scoped document folders with a sidebar navigation UI, inline CRUD, and multi-select bulk move.

**Architecture:** New `Folder` model with a nullable `folder_id` FK on `Document`. Backend follows the standard router→service→repository pattern. Frontend adds a `FolderSidebar` to `ProjectDocumentsPage` alongside a `BulkActionBar` for multi-select moves.

**Tech Stack:** Python/FastAPI/SQLAlchemy (backend), React/TypeScript/shadcn/ui/Tailwind (frontend), PostgreSQL `TEXT[]` for tags (SQLite-compatible via existing `StringList` type).

**Spec:** `docs/superpowers/specs/2026-04-18-document-folders-design.md`

---

## File Map

### Backend — New files
| File | Purpose |
|------|---------|
| `backend/app/models/types.py` | Shared `StringList` SQLAlchemy type (moved from project.py) |
| `backend/app/models/folder.py` | `Folder` SQLAlchemy model |
| `backend/app/schemas/folder.py` | Pydantic schemas: `FolderCreate`, `FolderUpdate`, `FolderResponse` |
| `backend/app/repositories/folder_repository.py` | Folder CRUD with document count |
| `backend/app/services/folder_service.py` | Folder business logic |
| `backend/app/routers/folders.py` | REST endpoints under `/projects/{project_id}/folders` |
| `backend/alembic/versions/XXXX_add_folders.py` | Migration: folders table + documents.folder_id |
| `backend/tests/services/test_folder_service.py` | Folder service unit tests |
| `backend/tests/routers/test_folders_router.py` | Folder router integration tests |

### Backend — Modified files
| File | Change |
|------|--------|
| `backend/app/models/project.py` | Import `StringList` from `models/types.py` instead of defining it |
| `backend/app/models/document.py` | Add `folder_id` nullable FK column + relationship |
| `backend/app/models/__init__.py` | Export `Folder` |
| `backend/app/schemas/document.py` | Add `folder_id` to `DocumentUpdate`, `DocumentResponse`, `DocumentListResponse` |
| `backend/app/repositories/document_repository.py` | Add `folder_id` filter to `list_by_project`; add `bulk_move` method |
| `backend/app/services/document_service.py` | Add `bulk_move` method |
| `backend/app/routers/documents.py` | Add `folder_id` form field to upload; `folder_id` query param to list; `bulk-move` endpoint |
| `backend/app/main.py` | Register folders router |

### Frontend — New files
| File | Purpose |
|------|---------|
| `frontend/src/types/folder.ts` | `Folder`, `FolderCreate`, `FolderUpdate` TypeScript types |
| `frontend/src/api/folders.ts` | API client functions for folder CRUD |
| `frontend/src/hooks/useFolders.ts` | Folder state: fetch, create, update, delete with optimistic updates |
| `frontend/src/components/documents/FolderSidebar.tsx` | Left sidebar: folder list, inline create, `...` menu |
| `frontend/src/components/documents/FolderEditPopover.tsx` | Popover form: name, description, tags |
| `frontend/src/components/documents/BulkActionBar.tsx` | Slides in when rows selected; move-to-folder dropdown |

### Frontend — Modified files
| File | Change |
|------|--------|
| `frontend/src/types/document.ts` | Add `folderId` to `DocumentListItem`, `Document`, `DocumentUpdate`, `DocumentUpload` |
| `frontend/src/api/documents.ts` | Add `folder_id` to upload; `folderId` filter to list; add `bulkMoveDocuments` |
| `frontend/src/hooks/useDocuments.ts` | Accept `folderId` filter; expose `bulkMoveDocuments` |
| `frontend/src/components/documents/DocumentsTable.tsx` | Checkbox column; Folder column; `selectedIds` / `onSelectionChange` props |
| `frontend/src/components/documents/DocumentEditDialog.tsx` | Add Folder `Select` field |
| `frontend/src/components/documents/DocumentUploadDialog.tsx` | Add optional Folder `Select` field |
| `frontend/src/pages/ProjectDocumentsPage.tsx` | Two-column layout; wire sidebar + bulk action bar |

---

## Task 1: Extract `StringList` to shared module

The `StringList` SQLAlchemy type is currently defined in `project.py`. The `Folder` model also needs it. Move it to a shared location.

**Files:**
- Create: `backend/app/models/types.py`
- Modify: `backend/app/models/project.py`

- [ ] **Step 1: Create `backend/app/models/types.py`**

```python
import json
from sqlalchemy import Text, TypeDecorator
from sqlalchemy.dialects.postgresql import ARRAY, TEXT


class StringList(TypeDecorator):
    """Store list of strings. Uses PostgreSQL ARRAY in prod, JSON in SQLite for tests."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(ARRAY(TEXT))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if dialect.name == 'postgresql':
            return value
        if value is not None:
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if dialect.name == 'postgresql':
            return value if value is not None else []
        if value is not None:
            return json.loads(value) if value else []
        return []
```

- [ ] **Step 2: Update `backend/app/models/project.py` to import from types.py**

Remove the `StringList` class definition from `project.py` and replace with:

```python
from app.models.types import StringList
```

Remove these imports that are no longer needed in project.py (if they were only for StringList):
```python
# Remove: import json
# Remove: from sqlalchemy.dialects.postgresql import ARRAY, TEXT
```

Keep all other imports and code unchanged.

- [ ] **Step 3: Run backend tests to confirm nothing broke**

```bash
cd backend && uv run python -m pytest tests/services/test_project_service.py tests/repositories/test_project_repository.py -v -o "addopts="
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/types.py backend/app/models/project.py
git commit -m "refactor: extract StringList to shared models/types.py"
```

---

## Task 2: Folder model

**Files:**
- Create: `backend/app/models/folder.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create `backend/app/models/folder.py`**

```python
from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.types import StringList


class Folder(Base):
    __tablename__ = "folders"

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
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        StringList,
        nullable=False,
        default=list
    )
    created_by: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )
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

    project: Mapped["Project"] = relationship(back_populates="folders")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="folder",
        passive_deletes=True
    )

    __table_args__ = (
        sa.UniqueConstraint('project_id', 'name', name='uq_folders_project_name'),
        sa.Index('ix_folders_project_id', 'project_id'),
    )
```

- [ ] **Step 2: Register `Folder` in `backend/app/models/__init__.py`**

Add after the `Project` import line:
```python
from app.models.folder import Folder
```

Add `"Folder"` to the `__all__` list.

- [ ] **Step 3: Add `folders` relationship to `Project` model in `backend/app/models/project.py`**

Add this relationship to the `Project` class after the existing `documents` relationship:
```python
folders: Mapped[list["Folder"]] = relationship(back_populates="project", cascade="all, delete-orphan")
```

- [ ] **Step 4: Verify model imports work**

```bash
cd backend && uv run python -c "from app.models import Folder; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/folder.py backend/app/models/__init__.py backend/app/models/project.py
git commit -m "feat: add Folder model"
```

---

## Task 3: Folder Pydantic schemas

**Files:**
- Create: `backend/app/schemas/folder.py`

- [ ] **Step 1: Create `backend/app/schemas/folder.py`**

```python
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class FolderUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] | None = None


class FolderResponse(BaseModel):
    id: UUID
    project_id: UUID = Field(..., alias="projectId")
    name: str
    description: str | None
    tags: list[str]
    document_count: int = Field(0, alias="documentCount")
    created_by: UUID = Field(..., alias="createdBy")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
```

- [ ] **Step 2: Verify schemas import cleanly**

```bash
cd backend && uv run python -c "from app.schemas.folder import FolderCreate, FolderUpdate, FolderResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/folder.py
git commit -m "feat: add Folder Pydantic schemas"
```

---

## Task 4: Folder repository (TDD)

**Files:**
- Create: `backend/app/repositories/folder_repository.py`
- Test: `backend/tests/repositories/test_folder_repository.py` (skip — service-level mocks cover this; router tests use full DB)

- [ ] **Step 1: Create `backend/app/repositories/folder_repository.py`**

```python
from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folder import Folder
from app.models.document import Document
from app.models.project import Project
from app.schemas.folder import FolderCreate, FolderUpdate


class FolderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, project_id: UUID, user_id: UUID, data: FolderCreate) -> Folder:
        folder = Folder(
            project_id=project_id,
            created_by=user_id,
            name=data.name,
            description=data.description,
            tags=data.tags,
        )
        self.session.add(folder)
        await self.session.commit()
        await self.session.refresh(folder)
        return folder

    async def get_by_id(self, folder_id: UUID, user_id: UUID) -> Folder | None:
        result = await self.session.execute(
            select(Folder)
            .join(Folder.project)
            .where(
                and_(
                    Folder.id == folder_id,
                    Project.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: UUID, user_id: UUID) -> list[tuple[Folder, int]]:
        """Return folders with document counts as (Folder, count) tuples."""
        result = await self.session.execute(
            select(Folder, func.count(Document.id).label("document_count"))
            .join(Folder.project)
            .outerjoin(Document, Document.folder_id == Folder.id)
            .where(
                and_(
                    Folder.project_id == project_id,
                    Project.user_id == user_id,
                )
            )
            .group_by(Folder.id)
            .order_by(Folder.name)
        )
        return list(result.all())

    async def update(self, folder_id: UUID, user_id: UUID, data: FolderUpdate) -> Folder | None:
        folder = await self.get_by_id(folder_id, user_id)
        if not folder:
            return None
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(folder, key, value)
        await self.session.commit()
        await self.session.refresh(folder)
        return folder

    async def delete(self, folder_id: UUID, user_id: UUID) -> bool:
        folder = await self.get_by_id(folder_id, user_id)
        if not folder:
            return False
        await self.session.delete(folder)
        await self.session.commit()
        return True
```

- [ ] **Step 2: Verify it imports**

```bash
cd backend && uv run python -c "from app.repositories.folder_repository import FolderRepository; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/repositories/folder_repository.py
git commit -m "feat: add FolderRepository"
```

---

## Task 5: Folder service (TDD)

**Files:**
- Create: `backend/app/services/folder_service.py`
- Test: `backend/tests/services/test_folder_service.py`

- [ ] **Step 1: Write failing tests in `backend/tests/services/test_folder_service.py`**

```python
"""Tests for FolderService."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.schemas.folder import FolderCreate, FolderUpdate
from app.services.folder_service import FolderService
from app.services.exceptions import ConflictError, NotFoundError


def make_mock_folder(name: str = "Bank Statements", project_id=None, user_id=None, doc_count: int = 0):
    folder = MagicMock()
    _now = datetime.now(timezone.utc)
    folder.id = uuid4()
    folder.project_id = project_id or uuid4()
    folder.name = name
    folder.description = None
    folder.tags = []
    folder.created_by = user_id or uuid4()
    folder.created_at = _now
    folder.updated_at = _now
    # camelCase aliases for Pydantic
    folder.projectId = folder.project_id
    folder.createdBy = folder.created_by
    folder.createdAt = _now
    folder.updatedAt = _now
    folder.document_count = doc_count
    return folder, doc_count


@pytest.fixture
def project_id():
    return uuid4()


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def mock_repos(project_id, user_id):
    folder_repo = AsyncMock()
    project_repo = AsyncMock()
    project_repo.get_by_id.return_value = MagicMock(id=project_id, user_id=user_id)
    return folder_repo, project_repo


@pytest.fixture
def service(mock_repos):
    folder_repo, project_repo = mock_repos
    return FolderService(folder_repo=folder_repo, project_repo=project_repo)


@pytest.mark.asyncio
async def test_create_folder_success(service, mock_repos, project_id, user_id):
    folder_repo, project_repo = mock_repos
    mock_folder, _ = make_mock_folder(project_id=project_id, user_id=user_id)
    folder_repo.create.return_value = mock_folder

    data = FolderCreate(name="Bank Statements", tags=["finance"])
    result = await service.create_folder(user_id=user_id, project_id=project_id, data=data)

    folder_repo.create.assert_called_once_with(project_id, user_id, data)
    assert result.name == "Bank Statements"


@pytest.mark.asyncio
async def test_create_folder_project_not_found(service, mock_repos, project_id, user_id):
    _, project_repo = mock_repos
    project_repo.get_by_id.return_value = None

    with pytest.raises(NotFoundError):
        await service.create_folder(
            user_id=user_id,
            project_id=project_id,
            data=FolderCreate(name="X"),
        )


@pytest.mark.asyncio
async def test_list_folders_returns_response_with_counts(service, mock_repos, project_id, user_id):
    folder_repo, _ = mock_repos
    mock_folder, count = make_mock_folder(project_id=project_id, doc_count=5)
    folder_repo.list_by_project.return_value = [(mock_folder, count)]

    results = await service.list_folders(user_id=user_id, project_id=project_id)

    assert len(results) == 1
    assert results[0].documentCount == 5


@pytest.mark.asyncio
async def test_update_folder_not_found(service, mock_repos, user_id):
    folder_repo, _ = mock_repos
    folder_repo.update.return_value = None

    with pytest.raises(NotFoundError):
        await service.update_folder(
            folder_id=uuid4(),
            user_id=user_id,
            data=FolderUpdate(name="New Name"),
        )


@pytest.mark.asyncio
async def test_delete_folder_not_found(service, mock_repos, user_id):
    folder_repo, _ = mock_repos
    folder_repo.delete.return_value = False

    with pytest.raises(NotFoundError):
        await service.delete_folder(folder_id=uuid4(), user_id=user_id)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend && uv run python -m pytest tests/services/test_folder_service.py -v -o "addopts="
```

Expected: `ModuleNotFoundError` or `ImportError` — `folder_service` doesn't exist yet.

- [ ] **Step 3: Create `backend/app/services/folder_service.py`**

```python
from uuid import UUID

from app.repositories.folder_repository import FolderRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.folder import FolderCreate, FolderUpdate, FolderResponse
from app.services.exceptions import ConflictError, NotFoundError


class FolderService:
    def __init__(self, folder_repo: FolderRepository, project_repo: ProjectRepository):
        self.folder_repo = folder_repo
        self.project_repo = project_repo

    async def create_folder(
        self, user_id: UUID, project_id: UUID, data: FolderCreate
    ) -> FolderResponse:
        project = await self.project_repo.get_by_id(project_id, user_id)
        if not project:
            raise NotFoundError(f"Project {project_id} not found")
        folder = await self.folder_repo.create(project_id, user_id, data)
        return FolderResponse.model_validate({**folder.__dict__, "document_count": 0})

    async def list_folders(self, user_id: UUID, project_id: UUID) -> list[FolderResponse]:
        rows = await self.folder_repo.list_by_project(project_id, user_id)
        results = []
        for folder, count in rows:
            data = {**folder.__dict__, "document_count": count}
            results.append(FolderResponse.model_validate(data))
        return results

    async def update_folder(
        self, folder_id: UUID, user_id: UUID, data: FolderUpdate
    ) -> FolderResponse:
        folder = await self.folder_repo.update(folder_id, user_id, data)
        if not folder:
            raise NotFoundError(f"Folder {folder_id} not found")
        return FolderResponse.model_validate({**folder.__dict__, "document_count": 0})

    async def delete_folder(self, folder_id: UUID, user_id: UUID) -> None:
        deleted = await self.folder_repo.delete(folder_id, user_id)
        if not deleted:
            raise NotFoundError(f"Folder {folder_id} not found")
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend && uv run python -m pytest tests/services/test_folder_service.py -v -o "addopts="
```

Expected: all 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/folder_service.py backend/tests/services/test_folder_service.py
git commit -m "feat: add FolderService with tests"
```

---

## Task 6: Folder router + register in main.py (TDD)

**Files:**
- Create: `backend/app/routers/folders.py`
- Test: `backend/tests/routers/test_folders_router.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests in `backend/tests/routers/test_folders_router.py`**

```python
"""Integration tests for /api/v1/projects/{project_id}/folders endpoints."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4

from app.schemas.folder import FolderResponse
from datetime import datetime, timezone


def make_folder_response(**kwargs) -> FolderResponse:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid4(),
        projectId=uuid4(),
        name="Bank Statements",
        description=None,
        tags=[],
        documentCount=0,
        createdBy=uuid4(),
        createdAt=now,
        updatedAt=now,
    )
    defaults.update(kwargs)
    return FolderResponse.model_validate(defaults)


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-token"}


@pytest.mark.asyncio
async def test_list_folders(client, auth_headers):
    project_id = uuid4()
    folders = [make_folder_response(projectId=project_id, documentCount=3)]

    with patch("app.routers.folders.get_folder_service") as mock_dep:
        mock_svc = AsyncMock()
        mock_svc.list_folders.return_value = folders
        mock_dep.return_value = mock_svc

        with patch("app.dependencies.auth.get_current_active_user") as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4())
            resp = await client.get(
                f"/api/v1/projects/{project_id}/folders",
                headers=auth_headers,
            )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["documentCount"] == 3


@pytest.mark.asyncio
async def test_create_folder(client, auth_headers):
    project_id = uuid4()
    folder = make_folder_response(projectId=project_id, name="Receipts")

    with patch("app.routers.folders.get_folder_service") as mock_dep:
        mock_svc = AsyncMock()
        mock_svc.create_folder.return_value = folder
        mock_dep.return_value = mock_svc

        with patch("app.dependencies.auth.get_current_active_user") as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4())
            resp = await client.post(
                f"/api/v1/projects/{project_id}/folders",
                json={"name": "Receipts", "tags": []},
                headers=auth_headers,
            )

    assert resp.status_code == 201
    assert resp.json()["name"] == "Receipts"


@pytest.mark.asyncio
async def test_delete_folder(client, auth_headers):
    project_id = uuid4()
    folder_id = uuid4()

    with patch("app.routers.folders.get_folder_service") as mock_dep:
        mock_svc = AsyncMock()
        mock_svc.delete_folder.return_value = None
        mock_dep.return_value = mock_svc

        with patch("app.dependencies.auth.get_current_active_user") as mock_auth:
            mock_auth.return_value = MagicMock(id=uuid4())
            resp = await client.delete(
                f"/api/v1/projects/{project_id}/folders/{folder_id}",
                headers=auth_headers,
            )

    assert resp.status_code == 204
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && uv run python -m pytest tests/routers/test_folders_router.py -v -o "addopts="
```

Expected: import error or 404s — router doesn't exist yet.

- [ ] **Step 3: Create `backend/app/routers/folders.py`**

```python
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models import User
from app.repositories.folder_repository import FolderRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.folder import FolderCreate, FolderUpdate, FolderResponse
from app.services.folder_service import FolderService
from app.services.exceptions import ConflictError, NotFoundError

router = APIRouter(prefix="/projects/{project_id}/folders", tags=["folders"])


def get_folder_service(db: AsyncSession = Depends(get_db)) -> FolderService:
    folder_repo = FolderRepository(db)
    project_repo = ProjectRepository(db)
    return FolderService(folder_repo=folder_repo, project_repo=project_repo)


@router.get("", response_model=list[FolderResponse])
async def list_folders(
    project_id: UUID,
    current_user: User = Depends(get_current_active_user),
    folder_service: FolderService = Depends(get_folder_service),
):
    return await folder_service.list_folders(user_id=current_user.id, project_id=project_id)


@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    project_id: UUID,
    data: FolderCreate,
    current_user: User = Depends(get_current_active_user),
    folder_service: FolderService = Depends(get_folder_service),
):
    try:
        return await folder_service.create_folder(
            user_id=current_user.id, project_id=project_id, data=data
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.patch("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    project_id: UUID,
    folder_id: UUID,
    data: FolderUpdate,
    current_user: User = Depends(get_current_active_user),
    folder_service: FolderService = Depends(get_folder_service),
):
    try:
        return await folder_service.update_folder(
            folder_id=folder_id, user_id=current_user.id, data=data
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    project_id: UUID,
    folder_id: UUID,
    current_user: User = Depends(get_current_active_user),
    folder_service: FolderService = Depends(get_folder_service),
):
    try:
        await folder_service.delete_folder(folder_id=folder_id, user_id=current_user.id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 4: Register in `backend/app/main.py`**

Add `folders` to the router imports line:
```python
from app.routers import auth, oauth, otel_proxy, projects, users, documents, indexes, provider_keys, golden_sets, eval_runs, experiments, parse_results, extraction, extraction_ground_truth, extraction_eval, agent, data_stores, export_mappings, folders
```

Add after the `documents` router registration:
```python
app.include_router(folders.router, prefix="/api/v1")
```

- [ ] **Step 5: Run router tests**

```bash
cd backend && uv run python -m pytest tests/routers/test_folders_router.py -v -o "addopts="
```

Expected: all 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/folders.py backend/tests/routers/test_folders_router.py backend/app/main.py
git commit -m "feat: add folders router with tests"
```

---

## Task 7: Update Document model + repository for folder support (TDD)

**Files:**
- Modify: `backend/app/models/document.py`
- Modify: `backend/app/repositories/document_repository.py`

- [ ] **Step 1: Add `folder_id` FK to `backend/app/models/document.py`**

Add this import at the top of the file (after existing imports):
```python
# already has ForeignKey, UUID imports — no new imports needed
```

Add this column inside the `Document` class, after `project_id`:
```python
folder_id: Mapped[UUID | None] = mapped_column(
    PGUUID(as_uuid=True),
    ForeignKey("folders.id", ondelete="SET NULL"),
    nullable=True
)
```

Add relationship after the `project` relationship:
```python
folder: Mapped["Folder | None"] = relationship(back_populates="documents")
```

Add index to `__table_args__`:
```python
sa.Index('ix_documents_folder_id', 'folder_id'),
```

- [ ] **Step 2: Add `folder_id` filter to `list_by_project` in `backend/app/repositories/document_repository.py`**

Change the signature and add filter logic:

```python
async def list_by_project(
    self,
    project_id: UUID,
    user_id: UUID,
    status: DocumentStatus | None = None,
    folder_id: UUID | None | str = None,  # UUID = specific folder; "none" = unfiled; None = all
    limit: int = 100,
    offset: int = 0
) -> list[Document]:
    query = (
        select(Document)
        .join(Document.project)
        .where(
            and_(
                Document.project_id == project_id,
                Project.user_id == user_id
            )
        )
    )

    if status:
        query = query.where(Document.status == status)

    if folder_id == "none":
        query = query.where(Document.folder_id.is_(None))
    elif folder_id is not None:
        query = query.where(Document.folder_id == folder_id)

    query = query.order_by(Document.created_at.desc()).limit(limit).offset(offset)

    result = await self.session.execute(query)
    return list(result.scalars().all())
```

- [ ] **Step 3: Add `bulk_move` method to `DocumentRepository`**

Add this method to `DocumentRepository`:

```python
async def bulk_move(
    self,
    document_ids: list[UUID],
    user_id: UUID,
    folder_id: UUID | None,
) -> int:
    """Move documents to a folder (or unfile if folder_id is None). Returns count updated."""
    from sqlalchemy import update as sa_update
    # First fetch IDs the user actually owns (security: silently ignore others)
    accessible = await self.session.execute(
        select(Document.id)
        .join(Document.project)
        .where(
            and_(
                Document.id.in_(document_ids),
                Project.user_id == user_id,
            )
        )
    )
    accessible_ids = [row[0] for row in accessible.all()]
    if not accessible_ids:
        return 0
    await self.session.execute(
        sa_update(Document)
        .where(Document.id.in_(accessible_ids))
        .values(folder_id=folder_id)
    )
    await self.session.commit()
    return len(accessible_ids)
```

- [ ] **Step 4: Verify imports and syntax**

```bash
cd backend && uv run python -c "from app.models.document import Document; from app.repositories.document_repository import DocumentRepository; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/document.py backend/app/repositories/document_repository.py
git commit -m "feat: add folder_id to Document model and repository"
```

---

## Task 8: Update Document schemas

**Files:**
- Modify: `backend/app/schemas/document.py`

- [ ] **Step 1: Add `folder_id` to `DocumentUpdate`, `DocumentResponse`, `DocumentListResponse`**

In `DocumentUpdate`, add:
```python
folder_id: UUID | None = None
```
(Add `from uuid import UUID` if not already at top — it already is.)

In `DocumentResponse`, add after `project_id`:
```python
folder_id: UUID | None = Field(None, alias="folderId")
```

In `DocumentListResponse`, add after `project_id`:
```python
folder_id: UUID | None = Field(None, alias="folderId")
```

- [ ] **Step 2: Verify**

```bash
cd backend && uv run python -c "from app.schemas.document import DocumentUpdate, DocumentResponse, DocumentListResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Run existing document tests to check for regressions**

```bash
cd backend && uv run python -m pytest tests/services/test_document_service.py tests/routers/test_documents_router.py -v -o "addopts="
```

Expected: all existing tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/document.py
git commit -m "feat: add folder_id to document schemas"
```

---

## Task 9: Update Document service (bulk_move) (TDD)

**Files:**
- Modify: `backend/app/services/document_service.py`
- Test: add to `backend/tests/services/test_document_service.py`

- [ ] **Step 1: Add bulk_move test to `backend/tests/services/test_document_service.py`**

Add these imports at the top of the existing test file:
```python
from app.services.document_service import DocumentService
```
(Already present — no change needed.)

Add this test at the end of the file:
```python
@pytest.mark.asyncio
async def test_bulk_move_success(mock_service, project_id, user_id):
    """bulk_move delegates to document_repo.bulk_move and returns count."""
    service, doc_repo, _, _ = mock_service
    doc_repo.bulk_move = AsyncMock(return_value=3)

    ids = [uuid4(), uuid4(), uuid4()]
    folder_id = uuid4()
    count = await service.bulk_move(
        user_id=user_id,
        document_ids=ids,
        folder_id=folder_id,
    )

    doc_repo.bulk_move.assert_called_once_with(ids, user_id, folder_id)
    assert count == 3
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd backend && uv run python -m pytest tests/services/test_document_service.py::test_bulk_move_success -v -o "addopts="
```

Expected: `AttributeError` — `bulk_move` not on service yet.

- [ ] **Step 3: Add `bulk_move` to `DocumentService` in `backend/app/services/document_service.py`**

Add this method to the `DocumentService` class:

```python
async def bulk_move(
    self,
    user_id: UUID,
    document_ids: list[UUID],
    folder_id: UUID | None,
) -> int:
    """Move documents to a folder (or unfile). Returns count of moved documents."""
    return await self.document_repo.bulk_move(document_ids, user_id, folder_id)
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
cd backend && uv run python -m pytest tests/services/test_document_service.py -v -o "addopts="
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/document_service.py backend/tests/services/test_document_service.py
git commit -m "feat: add bulk_move to DocumentService"
```

---

## Task 10: Update Document router (folder_id param + bulk-move endpoint)

**Files:**
- Modify: `backend/app/routers/documents.py`

- [ ] **Step 1: Add `folder_id` form field to `upload_document` endpoint**

In the `upload_document` function signature, add after `description`:
```python
folder_id: UUID | None = Form(None, description="Optional folder ID to place document in"),
```

Pass it to `document_service.initiate_upload`:
```python
document = await document_service.initiate_upload(
    user_id=current_user.id,
    project_id=project_id,
    file_content=file_content,
    filename=filename,
    title=title,
    description=description,
    folder_id=folder_id,
)
```

- [ ] **Step 2: Update `DocumentService.initiate_upload` to accept `folder_id`**

In `backend/app/services/document_service.py`, update `initiate_upload` signature to add:
```python
folder_id: UUID | None = None,
```

Pass `folder_id` to `self.document_repo.create(...)`. First update `DocumentRepository.create` to accept and store it:

In `backend/app/repositories/document_repository.py`, add `folder_id: UUID | None = None` to `create` method signature and set it on the `Document` instance:
```python
document = Document(
    project_id=project_id,
    created_by=user_id,
    source_type=source_type,
    source_identifier=source_identifier,
    title=title,
    description=description,
    source_metadata=source_metadata,
    status=DocumentStatus.processing,
    folder_id=folder_id,
)
```

Then in `document_service.py` `initiate_upload`, update the `create` call to pass `folder_id`:
```python
document = await self.document_repo.create(
    project_id=project_id,
    user_id=user_id,
    source_type="upload",
    source_identifier=checksum,
    title=title,
    description=description,
    source_metadata=source_metadata,
    folder_id=folder_id,
)
```

- [ ] **Step 3: Add `folder_id` query param to the `GET ""` list endpoint in `documents.py`**

Find the `@router.get("")` endpoint handler (it accepts `project_id`, `status`, `limit`, `offset` as query params). Add:
```python
folder_id: str | None = Query(None, description="Filter: UUID for a specific folder, 'none' for unfiled, omit for all"),
```

The list endpoint calls `document_repo.list_by_project(...)` either directly or via a service method. Locate that call and add `folder_id=folder_id` to it:
```python
# If called directly on the repo:
documents = await document_repo.list_by_project(
    project_id=project_id,
    user_id=current_user.id,
    status=status,
    folder_id=folder_id,
    limit=limit,
    offset=offset,
)
# If called via document_service, add folder_id to that method's signature first,
# then pass it through to the repo call inside the service.
```

- [ ] **Step 4: Add `bulk-move` endpoint to `backend/app/routers/documents.py`**

Add these schemas at the top of the file (in the imports section), or add a `BulkMoveRequest` inline:

Add import:
```python
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentUpdate,
    BulkUploadItemResponse,
    BulkUploadResponse,
    BulkMoveRequest,
    BulkMoveResponse,
)
```

Add schemas to `backend/app/schemas/document.py`:
```python
class BulkMoveRequest(BaseModel):
    document_ids: list[UUID]
    folder_id: UUID | None = None


class BulkMoveResponse(BaseModel):
    moved_count: int = Field(..., alias="movedCount")

    model_config = ConfigDict(populate_by_name=True)
```

Add endpoint to `backend/app/routers/documents.py`:
```python
@router.post(
    "/bulk-move",
    response_model=BulkMoveResponse,
    summary="Move documents to a folder",
    description="Move one or more documents to a folder. Pass folder_id=null to unfile documents.",
)
async def bulk_move_documents(
    data: BulkMoveRequest,
    current_user: User = Depends(get_current_active_user),
    document_service: DocumentService = Depends(get_document_service),
):
    try:
        count = await document_service.bulk_move(
            user_id=current_user.id,
            document_ids=data.document_ids,
            folder_id=data.folder_id,
        )
        return BulkMoveResponse(movedCount=count)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
```

- [ ] **Step 5: Run all document tests**

```bash
cd backend && uv run python -m pytest tests/services/test_document_service.py tests/routers/test_documents_router.py -v -o "addopts="
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/documents.py backend/app/schemas/document.py backend/app/services/document_service.py backend/app/repositories/document_repository.py
git commit -m "feat: add folder_id to document upload/list and bulk-move endpoint"
```

---

## Task 11: Database migration

**Files:**
- Create: `backend/alembic/versions/XXXX_add_folders.py`

- [ ] **Step 1: Generate migration**

```bash
cd backend && alembic revision --autogenerate -m "add_folders"
```

This creates a new file in `backend/alembic/versions/`. Open it and verify the `upgrade()` function creates:
1. `folders` table with all columns
2. `documents.folder_id` nullable column with FK
3. Required indexes

If autogenerate misses anything, add manually. The upgrade function should look like:

```python
def upgrade() -> None:
    op.create_table(
        'folders',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', sa.Text(), nullable=False, server_default='[]'),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'name', name='uq_folders_project_name'),
    )
    op.create_index('ix_folders_project_id', 'folders', ['project_id'])

    op.add_column('documents', sa.Column('folder_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_documents_folder_id', 'documents', 'folders',
        ['folder_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_documents_folder_id', 'documents', ['folder_id'])


def downgrade() -> None:
    op.drop_index('ix_documents_folder_id', 'documents')
    op.drop_constraint('fk_documents_folder_id', 'documents', type_='foreignkey')
    op.drop_column('documents', 'folder_id')
    op.drop_index('ix_folders_project_id', 'folders')
    op.drop_table('folders')
```

- [ ] **Step 2: Run migration**

```bash
cd backend && alembic upgrade head
```

Expected: migration runs without errors.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat: migration - add folders table and documents.folder_id"
```

---

## Task 12: Frontend types

**Files:**
- Create: `frontend/src/types/folder.ts`
- Modify: `frontend/src/types/document.ts`

- [ ] **Step 1: Create `frontend/src/types/folder.ts`**

```typescript
export interface Folder {
  id: string
  projectId: string
  name: string
  description: string | null
  tags: string[]
  documentCount: number
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface FolderCreate {
  name: string
  description?: string
  tags?: string[]
}

export interface FolderUpdate {
  name?: string
  description?: string
  tags?: string[]
}
```

- [ ] **Step 2: Update `frontend/src/types/document.ts`**

Add `folderId?: string | null` to `Document`, `DocumentListItem`, `DocumentUpdate`, and `DocumentUpload`:

```typescript
// In Document interface, add:
folderId: string | null

// In DocumentListItem interface, add:
folderId: string | null

// In DocumentUpdate interface, add:
folderId?: string | null

// In DocumentUpload interface, add:
folderId?: string
```

Also add bulk-move types at the end of the file:
```typescript
export interface BulkMoveDocuments {
  documentIds: string[]
  folderId: string | null
}

export interface BulkMoveResponse {
  movedCount: number
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/folder.ts frontend/src/types/document.ts
git commit -m "feat: add Folder types and folder_id to Document types"
```

---

## Task 13: Frontend API layer

**Files:**
- Create: `frontend/src/api/folders.ts`
- Modify: `frontend/src/api/documents.ts`

- [ ] **Step 1: Create `frontend/src/api/folders.ts`**

```typescript
import apiClient from './client'
import { Folder, FolderCreate, FolderUpdate } from '@/types/folder'

export async function listFolders(projectId: string): Promise<Folder[]> {
  const response = await apiClient.get<Folder[]>(`/projects/${projectId}/folders`)
  return response.data
}

export async function createFolder(projectId: string, data: FolderCreate): Promise<Folder> {
  const response = await apiClient.post<Folder>(`/projects/${projectId}/folders`, data)
  return response.data
}

export async function updateFolder(
  projectId: string,
  folderId: string,
  data: FolderUpdate
): Promise<Folder> {
  const response = await apiClient.patch<Folder>(
    `/projects/${projectId}/folders/${folderId}`,
    data
  )
  return response.data
}

export async function deleteFolder(projectId: string, folderId: string): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/folders/${folderId}`)
}
```

- [ ] **Step 2: Update `frontend/src/api/documents.ts`**

Update `ListDocumentsParams` to add `folderId`:
```typescript
export interface ListDocumentsParams {
  projectId: string
  status?: DocumentStatus
  folderId?: string | 'none'
  limit?: number
  offset?: number
}
```

Update `listDocuments` to pass `folder_id`:
```typescript
const response = await apiClient.get<DocumentListItem[]>('/documents', {
  params: {
    project_id: params.projectId,
    status: params.status,
    folder_id: params.folderId,
    limit: params.limit,
    offset: params.offset,
  },
})
```

Update `uploadDocument` to pass `folder_id`:
```typescript
// In uploadDocument, after the parserType block, add:
if (data.folderId) {
  formData.append('folder_id', data.folderId)
}
```

Add `bulkMoveDocuments` function:
```typescript
import { BulkMoveDocuments, BulkMoveResponse } from '@/types/document'

export async function bulkMoveDocuments(data: BulkMoveDocuments): Promise<BulkMoveResponse> {
  const response = await apiClient.post<BulkMoveResponse>('/documents/bulk-move', {
    document_ids: data.documentIds,
    folder_id: data.folderId,
  })
  return response.data
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/folders.ts frontend/src/api/documents.ts
git commit -m "feat: add folder API client functions"
```

---

## Task 14: `useFolders` hook

**Files:**
- Create: `frontend/src/hooks/useFolders.ts`

- [ ] **Step 1: Create `frontend/src/hooks/useFolders.ts`**

```typescript
import { useState, useCallback, useEffect } from 'react'
import { Folder, FolderCreate, FolderUpdate } from '@/types/folder'
import * as foldersApi from '@/api/folders'

interface UseFoldersReturn {
  folders: Folder[]
  isLoading: boolean
  error: string | null
  createFolder: (data: FolderCreate) => Promise<Folder>
  updateFolder: (folderId: string, data: FolderUpdate) => Promise<Folder>
  deleteFolder: (folderId: string) => Promise<void>
  refetch: () => Promise<void>
}

export function useFolders(projectId: string | null): UseFoldersReturn {
  const [folders, setFolders] = useState<Folder[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchFolders = useCallback(async () => {
    if (!projectId) return
    setIsLoading(true)
    setError(null)
    try {
      const data = await foldersApi.listFolders(projectId)
      setFolders(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load folders')
    } finally {
      setIsLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    fetchFolders()
  }, [fetchFolders])

  const createFolder = useCallback(
    async (data: FolderCreate): Promise<Folder> => {
      if (!projectId) throw new Error('No project selected')
      const folder = await foldersApi.createFolder(projectId, data)
      setFolders((prev) => [...prev, { ...folder, documentCount: 0 }])
      return folder
    },
    [projectId]
  )

  const updateFolder = useCallback(
    async (folderId: string, data: FolderUpdate): Promise<Folder> => {
      if (!projectId) throw new Error('No project selected')
      const updated = await foldersApi.updateFolder(projectId, folderId, data)
      setFolders((prev) =>
        prev.map((f) => (f.id === folderId ? { ...updated, documentCount: f.documentCount } : f))
      )
      return updated
    },
    [projectId]
  )

  const deleteFolder = useCallback(
    async (folderId: string): Promise<void> => {
      if (!projectId) throw new Error('No project selected')
      await foldersApi.deleteFolder(projectId, folderId)
      setFolders((prev) => prev.filter((f) => f.id !== folderId))
    },
    [projectId]
  )

  return {
    folders,
    isLoading,
    error,
    createFolder,
    updateFolder,
    deleteFolder,
    refetch: fetchFolders,
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useFolders.ts
git commit -m "feat: add useFolders hook"
```

---

## Task 15: Update `useDocuments` hook for folder filter + bulk move

**Files:**
- Modify: `frontend/src/hooks/useDocuments.ts`

- [ ] **Step 1: Update `useDocuments` to accept `folderId` and expose `bulkMoveDocuments`**

Update the `UseDocumentsReturn` interface to add:
```typescript
bulkMoveDocuments: (documentIds: string[], folderId: string | null) => Promise<void>
```

Update `useDocuments` signature:
```typescript
export function useDocuments(
  projectId: string | null,
  statusFilter?: DocumentStatus,
  folderFilter?: string | 'none'
): UseDocumentsReturn {
```

Update the `fetchDocuments` call inside the hook to pass `folderId`:
```typescript
const data = await documentsApi.listDocuments({
  projectId,
  status: statusFilter,
  folderId: folderFilter,
})
```

Add `bulkMoveDocuments` implementation:
```typescript
const bulkMoveDocuments = useCallback(
  async (documentIds: string[], folderId: string | null): Promise<void> => {
    await documentsApi.bulkMoveDocuments({ documentIds, folderId })
    await fetchDocuments()
  },
  [fetchDocuments]
)
```

Return `bulkMoveDocuments` from the hook.

- [ ] **Step 2: Run frontend lint**

```bash
cd frontend && npm run lint
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useDocuments.ts
git commit -m "feat: add folder filter and bulkMoveDocuments to useDocuments"
```

---

## Task 16: `FolderEditPopover` component

**Files:**
- Create: `frontend/src/components/documents/FolderEditPopover.tsx`

- [ ] **Step 1: Create `frontend/src/components/documents/FolderEditPopover.tsx`**

```tsx
import { useState, useEffect } from 'react'
import { Folder, FolderCreate, FolderUpdate } from '@/types/folder'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

interface FolderEditPopoverProps {
  trigger: React.ReactNode
  folder?: Folder
  onSave: (data: FolderCreate | FolderUpdate) => Promise<void>
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

export function FolderEditPopover({
  trigger,
  folder,
  onSave,
  open,
  onOpenChange,
}: FolderEditPopoverProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [tagsInput, setTagsInput] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (folder) {
      setName(folder.name)
      setDescription(folder.description ?? '')
      setTagsInput(folder.tags.join(', '))
    } else {
      setName('')
      setDescription('')
      setTagsInput('')
    }
    setError(null)
  }, [folder, open])

  const handleSave = async () => {
    if (!name.trim()) {
      setError('Name is required')
      return
    }
    setIsSaving(true)
    setError(null)
    try {
      const tags = tagsInput
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean)
      await onSave({ name: name.trim(), description: description.trim() || undefined, tags })
      onOpenChange?.(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>{trigger}</PopoverTrigger>
      <PopoverContent className="w-72">
        <div className="space-y-3">
          <h4 className="font-medium text-sm">{folder ? 'Edit folder' : 'New folder'}</h4>
          <div className="space-y-1">
            <Label htmlFor="folder-name" className="text-xs">Name *</Label>
            <Input
              id="folder-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Folder name"
              disabled={isSaving}
              className="h-8 text-sm"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="folder-desc" className="text-xs">Description</Label>
            <Textarea
              id="folder-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description"
              disabled={isSaving}
              rows={2}
              className="text-sm resize-none"
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="folder-tags" className="text-xs">Tags (comma-separated)</Label>
            <Input
              id="folder-tags"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="finance, receipts"
              disabled={isSaving}
              className="h-8 text-sm"
            />
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="flex gap-2 justify-end">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onOpenChange?.(false)}
              disabled={isSaving}
            >
              Cancel
            </Button>
            <Button size="sm" onClick={handleSave} disabled={isSaving || !name.trim()}>
              {isSaving ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/documents/FolderEditPopover.tsx
git commit -m "feat: add FolderEditPopover component"
```

---

## Task 17: `FolderSidebar` component

**Files:**
- Create: `frontend/src/components/documents/FolderSidebar.tsx`

- [ ] **Step 1: Create `frontend/src/components/documents/FolderSidebar.tsx`**

```tsx
import { useState, useRef, useEffect } from 'react'
import { Folder, FolderCreate, FolderUpdate } from '@/types/folder'
import { FolderEditPopover } from './FolderEditPopover'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { FolderIcon, MoreHorizontal, Plus } from 'lucide-react'
import { cn } from '@/lib/utils'

type FolderFilter = string | 'none' | undefined

interface FolderSidebarProps {
  folders: Folder[]
  totalCount: number
  unfiledCount: number
  selectedFilter: FolderFilter
  onFilterChange: (filter: FolderFilter) => void
  onCreateFolder: (data: FolderCreate) => Promise<void>
  onUpdateFolder: (folderId: string, data: FolderUpdate) => Promise<void>
  onDeleteFolder: (folderId: string) => Promise<void>
}

export function FolderSidebar({
  folders,
  totalCount,
  unfiledCount,
  selectedFilter,
  onFilterChange,
  onCreateFolder,
  onUpdateFolder,
  onDeleteFolder,
}: FolderSidebarProps) {
  const [createOpen, setCreateOpen] = useState(false)
  const [editingFolder, setEditingFolder] = useState<Folder | null>(null)
  const [editPopoverOpen, setEditPopoverOpen] = useState(false)
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null)

  const handleCreate = async (data: FolderCreate) => {
    await onCreateFolder(data)
    setCreateOpen(false)
  }

  const handleUpdate = async (data: FolderUpdate) => {
    if (!editingFolder) return
    await onUpdateFolder(editingFolder.id, data)
    setEditingFolder(null)
    setEditPopoverOpen(false)
  }

  const handleDelete = async (folderId: string) => {
    await onDeleteFolder(folderId)
    setDeleteConfirmId(null)
    if (selectedFilter === folderId) {
      onFilterChange(undefined)
    }
  }

  return (
    <div className="w-52 shrink-0 border-r pr-2 space-y-1">
      {/* All Documents */}
      <button
        onClick={() => onFilterChange(undefined)}
        className={cn(
          'w-full flex items-center justify-between px-2 py-1.5 rounded text-sm transition-colors',
          selectedFilter === undefined
            ? 'bg-primary/10 text-primary font-medium'
            : 'hover:bg-muted/60'
        )}
      >
        <span>All Documents</span>
        <span className="text-xs text-muted-foreground">{totalCount}</span>
      </button>

      {/* Folders header */}
      <div className="flex items-center justify-between px-2 pt-2 pb-1">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Folders
        </span>
        <FolderEditPopover
          trigger={
            <Button variant="ghost" size="icon" className="h-5 w-5">
              <Plus className="h-3 w-3" />
            </Button>
          }
          open={createOpen}
          onOpenChange={setCreateOpen}
          onSave={handleCreate}
        />
      </div>

      {/* Folder list */}
      {folders.map((folder) => (
        <div key={folder.id} className="group flex items-center">
          <button
            onClick={() => onFilterChange(folder.id)}
            className={cn(
              'flex-1 flex items-center gap-1.5 px-2 py-1.5 rounded text-sm transition-colors min-w-0',
              selectedFilter === folder.id
                ? 'bg-primary/10 text-primary font-medium'
                : 'hover:bg-muted/60'
            )}
          >
            <FolderIcon className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{folder.name}</span>
            <span className="ml-auto text-xs text-muted-foreground shrink-0">
              {folder.documentCount}
            </span>
          </button>

          {/* Edit/Delete menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 opacity-0 group-hover:opacity-100 shrink-0"
              >
                <MoreHorizontal className="h-3.5 w-3.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                onClick={() => {
                  setEditingFolder(folder)
                  setEditPopoverOpen(true)
                }}
              >
                Edit
              </DropdownMenuItem>
              <DropdownMenuItem
                className="text-red-600"
                onClick={() => setDeleteConfirmId(folder.id)}
              >
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Delete confirm popover */}
          {deleteConfirmId === folder.id && (
            <Popover
              open={deleteConfirmId === folder.id}
              onOpenChange={(o) => !o && setDeleteConfirmId(null)}
            >
              <PopoverTrigger className="sr-only" />
              <PopoverContent className="w-64" align="end">
                <p className="text-sm mb-3">
                  Delete <strong>{folder.name}</strong>?{' '}
                  {folder.documentCount > 0 && (
                    <>{folder.documentCount} document{folder.documentCount !== 1 ? 's' : ''} will become unfiled.</>
                  )}
                </p>
                <div className="flex gap-2 justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setDeleteConfirmId(null)}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDelete(folder.id)}
                  >
                    Delete
                  </Button>
                </div>
              </PopoverContent>
            </Popover>
          )}
        </div>
      ))}

      {/* Edit folder popover (shared, triggered by dropdown) */}
      {editingFolder && (
        <FolderEditPopover
          trigger={<span className="sr-only" />}
          folder={editingFolder}
          open={editPopoverOpen}
          onOpenChange={(o) => {
            setEditPopoverOpen(o)
            if (!o) setEditingFolder(null)
          }}
          onSave={handleUpdate}
        />
      )}

      {/* Divider + Unfiled */}
      <div className="border-t pt-1 mt-1">
        <button
          onClick={() => onFilterChange('none')}
          className={cn(
            'w-full flex items-center justify-between px-2 py-1.5 rounded text-sm transition-colors',
            selectedFilter === 'none'
              ? 'bg-primary/10 text-primary font-medium'
              : 'hover:bg-muted/60'
          )}
        >
          <span>Unfiled</span>
          <span className="text-xs text-muted-foreground">{unfiledCount}</span>
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/documents/FolderSidebar.tsx
git commit -m "feat: add FolderSidebar component"
```

---

## Task 18: `BulkActionBar` component

**Files:**
- Create: `frontend/src/components/documents/BulkActionBar.tsx`

- [ ] **Step 1: Create `frontend/src/components/documents/BulkActionBar.tsx`**

```tsx
import { Folder } from '@/types/folder'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { FolderIcon, X, ChevronDown } from 'lucide-react'

interface BulkActionBarProps {
  selectedCount: number
  folders: Folder[]
  onMoveToFolder: (folderId: string | null) => Promise<void>
  onClearSelection: () => void
}

export function BulkActionBar({
  selectedCount,
  folders,
  onMoveToFolder,
  onClearSelection,
}: BulkActionBarProps) {
  if (selectedCount === 0) return null

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-primary/5 border rounded-lg">
      <button
        onClick={onClearSelection}
        className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <X className="h-3.5 w-3.5" />
        {selectedCount} selected
      </button>

      <div className="h-4 w-px bg-border" />

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" className="gap-1.5">
            <FolderIcon className="h-3.5 w-3.5" />
            Move to folder
            <ChevronDown className="h-3.5 w-3.5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
          {folders.map((folder) => (
            <DropdownMenuItem key={folder.id} onClick={() => onMoveToFolder(folder.id)}>
              <FolderIcon className="mr-2 h-4 w-4" />
              {folder.name}
            </DropdownMenuItem>
          ))}
          {folders.length > 0 && <div className="border-t my-1" />}
          <DropdownMenuItem
            onClick={() => onMoveToFolder(null)}
            className="text-muted-foreground"
          >
            Remove from folder
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/documents/BulkActionBar.tsx
git commit -m "feat: add BulkActionBar component"
```

---

## Task 19: Update `DocumentsTable` — checkbox + folder column

**Files:**
- Modify: `frontend/src/components/documents/DocumentsTable.tsx`

- [ ] **Step 1: Add `selectedIds`, `onSelectionChange` props and checkbox column**

Update the `DocumentsTableProps` interface:
```typescript
interface DocumentsTableProps {
  documents: DocumentListItem[]
  folders: Folder[]                                        // add
  selectedIds: Set<string>                                 // add
  onSelectionChange: (ids: Set<string>) => void           // add
  onView: (id: string) => void
  onEdit: (id: string) => void
  onDelete: (id: string) => void
  onDownload: (id: string, title: string) => void
  onExtract?: (id: string) => void
  onUploadClick?: () => void
}
```

Add the `Folder` import at the top:
```typescript
import { Folder } from '@/types/folder'
import { Checkbox } from '@/components/ui/checkbox'
```

In the table `<thead>`, add checkbox column as first `<th>`:
```tsx
<th className="py-3 px-4 w-10">
  <Checkbox
    checked={documents.length > 0 && selectedIds.size === documents.length}
    onCheckedChange={(checked) => {
      if (checked) {
        onSelectionChange(new Set(documents.map((d) => d.id)))
      } else {
        onSelectionChange(new Set())
      }
    }}
  />
</th>
```

Add Folder column header after Status:
```tsx
<th className="text-left py-3 px-4 font-medium text-sm">Folder</th>
```

In each `<tr>`, add checkbox cell as first `<td>`:
```tsx
<td className="py-3 px-4">
  <Checkbox
    checked={selectedIds.has(document.id)}
    onCheckedChange={(checked) => {
      const next = new Set(selectedIds)
      if (checked) next.add(document.id)
      else next.delete(document.id)
      onSelectionChange(next)
    }}
  />
</td>
```

Add folder cell after status cell:
```tsx
<td className="py-3 px-4 text-sm text-muted-foreground">
  {folders.find((f) => f.id === document.folderId)?.name ?? '—'}
</td>
```

- [ ] **Step 2: Run lint**

```bash
cd frontend && npm run lint
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/documents/DocumentsTable.tsx
git commit -m "feat: add checkbox selection and folder column to DocumentsTable"
```

---

## Task 20: Update `DocumentEditDialog` — folder select

**Files:**
- Modify: `frontend/src/components/documents/DocumentEditDialog.tsx`

- [ ] **Step 1: Update `DocumentEditDialogProps` and form**

Update props interface:
```typescript
interface DocumentEditDialogProps {
  document: DocumentListItem | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onSave: (id: string, title: string, description?: string, folderId?: string | null) => Promise<void>
  folders: Folder[]
}
```

Add import at top:
```typescript
import { Folder } from '@/types/folder'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
```

Add state:
```typescript
const [folderId, setFolderId] = useState<string>('none')
```

Update `useEffect` to set folderId:
```typescript
setFolderId(document.folderId ?? 'none')
```

Add the Select field in the form, after description:
```tsx
<div className="space-y-2">
  <Label htmlFor="edit-folder">Folder</Label>
  <Select value={folderId} onValueChange={setFolderId} disabled={isSaving}>
    <SelectTrigger id="edit-folder">
      <SelectValue placeholder="No folder" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="none">No folder</SelectItem>
      {folders.map((folder) => (
        <SelectItem key={folder.id} value={folder.id}>
          {folder.name}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
</div>
```

Update `handleSave` to pass folderId:
```typescript
await onSave(
  document.id,
  title.trim(),
  description.trim() || undefined,
  folderId === 'none' ? null : folderId,
)
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/documents/DocumentEditDialog.tsx
git commit -m "feat: add folder select to DocumentEditDialog"
```

---

## Task 21: Update `DocumentUploadDialog` — folder select

**Files:**
- Modify: `frontend/src/components/documents/DocumentUploadDialog.tsx`

- [ ] **Step 1: Read the current DocumentUploadDialog to understand its props and form structure**

```bash
# Read the file to understand the current form fields before editing
```

- [ ] **Step 2: Add `folders` prop and folder select field**

Add to props interface:
```typescript
folders: Folder[]
```

Add import:
```typescript
import { Folder } from '@/types/folder'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
```

Add state:
```typescript
const [folderId, setFolderId] = useState<string>('none')
```

Add Select field in the form (after description, before parser options if present):
```tsx
<div className="space-y-2">
  <Label>Folder (optional)</Label>
  <Select value={folderId} onValueChange={setFolderId}>
    <SelectTrigger>
      <SelectValue placeholder="No folder" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="none">No folder</SelectItem>
      {folders.map((folder) => (
        <SelectItem key={folder.id} value={folder.id}>
          {folder.name}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
</div>
```

Pass `folderId` when calling the upload function — locate where `onUpload` is called and add:
```typescript
folderId: folderId === 'none' ? undefined : folderId,
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/documents/DocumentUploadDialog.tsx
git commit -m "feat: add folder select to DocumentUploadDialog"
```

---

## Task 22: Update `ProjectDocumentsPage` — two-column layout + wire everything

**Files:**
- Modify: `frontend/src/pages/ProjectDocumentsPage.tsx`

- [ ] **Step 1: Read the current full page to understand all existing wiring**

```bash
# Read ProjectDocumentsPage.tsx fully before editing
```

- [ ] **Step 2: Add imports and hooks**

Add imports at the top:
```typescript
import { useFolders } from '@/hooks/useFolders'
import { FolderSidebar } from '@/components/documents/FolderSidebar'
import { BulkActionBar } from '@/components/documents/BulkActionBar'
```

Add state and hooks inside the component:
```typescript
const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
const [folderFilter, setFolderFilter] = useState<string | 'none' | undefined>(undefined)

const { folders, createFolder, updateFolder, deleteFolder, refetch: refetchFolders } = useFolders(projectId || null)
```

Update the `useDocuments` call to pass `folderFilter`:
```typescript
const {
  documents,
  isLoading,
  error,
  uploadDocument,
  uploadDocumentsBulk,
  updateDocument,
  deleteDocument,
  downloadDocument,
  bulkMoveDocuments,
} = useDocuments(projectId || null, undefined, folderFilter)
```

- [ ] **Step 3: Update `handleSave` (edit dialog) to pass folderId**

Find the `handleEdit` / `onSave` callback and update its signature to accept `folderId`:
```typescript
const handleEdit = async (id: string, title: string, description?: string, folderId?: string | null) => {
  try {
    await updateDocument(id, { title, description, folderId })
    // ... existing toast/close logic
  }
  // ... existing error handling
}
```

- [ ] **Step 4: Wire bulk move**

Add bulk move handler:
```typescript
const handleBulkMove = async (folderId: string | null) => {
  try {
    await bulkMoveDocuments(Array.from(selectedIds), folderId)
    setSelectedIds(new Set())
    await refetchFolders()
    toast.success('Documents moved')
  } catch (err) {
    toast.error('Move failed', {
      description: err instanceof Error ? err.message : 'An error occurred',
    })
  }
}
```

- [ ] **Step 5: Replace layout with two-column structure**

Wrap the existing content in a flex layout. Find the return statement and update the outer structure to:

```tsx
return (
  <div className="space-y-4">
    {/* ... existing header with buttons ... */}

    <div className="flex gap-4 items-start">
      {/* Left sidebar */}
      <FolderSidebar
        folders={folders}
        totalCount={documents.length}
        unfiledCount={documents.filter((d) => !d.folderId).length}
        selectedFilter={folderFilter}
        onFilterChange={(f) => {
          setFolderFilter(f)
          setSelectedIds(new Set())
        }}
        onCreateFolder={async (data) => { await createFolder(data); await refetchFolders() }}
        onUpdateFolder={async (id, data) => { await updateFolder(id, data); await refetchFolders() }}
        onDeleteFolder={async (id) => { await deleteFolder(id); await refetchFolders() }}
      />

      {/* Right content */}
      <div className="flex-1 min-w-0 space-y-2">
        <BulkActionBar
          selectedCount={selectedIds.size}
          folders={folders}
          onMoveToFolder={handleBulkMove}
          onClearSelection={() => setSelectedIds(new Set())}
        />

        {/* ... existing DocumentsTable, dialogs, etc. ... */}
        <DocumentsTable
          documents={documents}
          folders={folders}
          selectedIds={selectedIds}
          onSelectionChange={setSelectedIds}
          onView={...}
          onEdit={...}
          onDelete={...}
          onDownload={...}
          onExtract={...}
          onUploadClick={...}
        />
      </div>
    </div>

    {/* ... existing dialogs (Sheet, DocumentEditDialog, etc.) ... */}
  </div>
)
```

Pass `folders` to `DocumentEditDialog` and `DocumentUploadDialog`:
```tsx
<DocumentEditDialog
  document={selectedDocument}
  open={editDialogOpen}
  onOpenChange={setEditDialogOpen}
  onSave={handleEdit}
  folders={folders}
/>
<DocumentUploadDialog
  open={bulkUploadOpen}
  onOpenChange={setBulkUploadOpen}
  onUpload={handleBulkUpload}
  folders={folders}
/>
```

- [ ] **Step 6: Build and lint**

```bash
cd frontend && npm run lint && npm run build
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/ProjectDocumentsPage.tsx
git commit -m "feat: add two-column layout with FolderSidebar and BulkActionBar to ProjectDocumentsPage"
```

---

## Task 23: Run full test suites + manual verification

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && uv run python -m pytest -o "addopts=" -v
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend lint and build**

```bash
cd frontend && npm run lint && npm run build
```

Expected: no errors.

- [ ] **Step 3: Run frontend unit tests**

```bash
cd frontend && npx vitest run
```

Expected: all tests pass.

- [ ] **Step 4: Start dev servers and manually verify**

```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload

# Terminal 2
cd frontend && npm run dev
```

Manual verification checklist:
- [ ] Navigate to a project's Documents page — sidebar appears on the left with "All Documents" and "Unfiled" sections
- [ ] Click `+` in sidebar — inline create popover opens
- [ ] Create a folder "Bank Statements" with tag "finance" — folder appears in sidebar
- [ ] Upload a document, select "Bank Statements" folder during upload — document appears in that folder
- [ ] Click "Bank Statements" in sidebar — table filters to show only that folder's documents
- [ ] Click "All Documents" — all documents shown again
- [ ] Check ≥1 document — `BulkActionBar` slides in above table
- [ ] "Move to folder" dropdown shows all folders + "Remove from folder"
- [ ] Move 2 documents to a folder — document counts update in sidebar
- [ ] Hover folder — `...` menu appears; "Edit" opens FolderEditPopover; change name and save
- [ ] "Delete" shows confirm popover with document count; confirm deletes folder; documents become unfiled
- [ ] Open Edit dialog on a document — Folder select shows current folder; change it and save
- [ ] "Unfiled" filter shows only documents with no folder

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: complete document folders implementation"
```
