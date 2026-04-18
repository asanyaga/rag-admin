"""Tests for FolderService."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.schemas.folder import FolderCreate, FolderUpdate
from app.services.folder_service import FolderService
from app.services.exceptions import NotFoundError


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
    folder.document_count = doc_count
    # camelCase aliases for Pydantic
    folder.projectId = folder.project_id
    folder.createdBy = folder.created_by
    folder.createdAt = _now
    folder.updatedAt = _now
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
    assert results[0].document_count == 5


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
