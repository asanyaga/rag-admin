import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthProvider, User
from app.repositories.project_repository import ProjectRepository
from app.repositories.user_repository import UserRepository
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.project_service import ProjectService
from app.services.exceptions import ConflictError, NotFoundError, ValidationError


@pytest.fixture
async def test_user(test_db: AsyncSession) -> User:
    """Create a test user for project tests."""
    user_repo = UserRepository(test_db)
    user = User(
        email="testuser@example.com",
        password_hash="hash",
        auth_provider=AuthProvider.email,
        full_name="Test User"
    )
    return await user_repo.create(user)


@pytest.fixture
async def another_user(test_db: AsyncSession) -> User:
    """Create another test user for security tests."""
    user_repo = UserRepository(test_db)
    user = User(
        email="anotheruser@example.com",
        password_hash="hash",
        auth_provider=AuthProvider.email,
        full_name="Another User"
    )
    return await user_repo.create(user)


@pytest.fixture
def project_service(test_db: AsyncSession) -> ProjectService:
    project_repo = ProjectRepository(test_db)
    return ProjectService(project_repo)


@pytest.mark.asyncio
async def test_create_project_success(
    project_service: ProjectService,
    test_user: User
):
    data = ProjectCreate(
        name="Test Project",
        description="A test project",
        tags=["tag1", "tag2"]
    )

    project = await project_service.create_project(test_user.id, data)

    assert project.id is not None
    assert project.user_id == test_user.id
    assert project.name == "Test Project"
    assert project.description == "A test project"
    assert project.tags == ["tag1", "tag2"]
    assert project.is_archived is False


@pytest.mark.asyncio
async def test_create_project_duplicate_name(
    project_service: ProjectService,
    test_user: User
):
    """Test that creating a project with duplicate name raises ConflictError."""
    data = ProjectCreate(name="Duplicate")
    await project_service.create_project(test_user.id, data)

    with pytest.raises(ConflictError, match="already exists"):
        await project_service.create_project(test_user.id, data)


@pytest.mark.asyncio
async def test_create_project_same_name_different_users(
    project_service: ProjectService,
    test_user: User,
    another_user: User
):
    """Test that different users can create projects with the same name."""
    data = ProjectCreate(name="Same Name")

    project1 = await project_service.create_project(test_user.id, data)
    project2 = await project_service.create_project(another_user.id, data)

    assert project1.name == "Same Name"
    assert project2.name == "Same Name"
    assert project1.user_id != project2.user_id


@pytest.mark.asyncio
async def test_get_project_success(
    project_service: ProjectService,
    test_user: User
):
    created = await project_service.create_project(
        test_user.id,
        ProjectCreate(name="Get Me")
    )

    found = await project_service.get_project(created.id, test_user.id)

    assert found.id == created.id
    assert found.name == "Get Me"


@pytest.mark.asyncio
async def test_get_project_not_found(
    project_service: ProjectService,
    test_user: User
):
    from uuid import uuid4

    with pytest.raises(NotFoundError, match="not found"):
        await project_service.get_project(uuid4(), test_user.id)


@pytest.mark.asyncio
async def test_get_project_wrong_user(
    project_service: ProjectService,
    test_user: User,
    another_user: User
):
    """Test that users cannot access other users' projects."""
    created = await project_service.create_project(
        test_user.id,
        ProjectCreate(name="Private")
    )

    with pytest.raises(NotFoundError):
        await project_service.get_project(created.id, another_user.id)


@pytest.mark.asyncio
async def test_list_projects(project_service: ProjectService, test_user: User):
    await project_service.create_project(test_user.id, ProjectCreate(name="Project 1"))
    await project_service.create_project(test_user.id, ProjectCreate(name="Project 2"))

    projects = await project_service.list_projects(test_user.id)

    assert len(projects) == 2
    assert {p.name for p in projects} == {"Project 1", "Project 2"}


@pytest.mark.asyncio
async def test_list_projects_exclude_archived(
    project_service: ProjectService,
    test_user: User
):
    await project_service.create_project(test_user.id, ProjectCreate(name="Active"))
    archived = await project_service.create_project(
        test_user.id,
        ProjectCreate(name="Archived")
    )
    await project_service.archive_project(archived.id, test_user.id)

    projects = await project_service.list_projects(test_user.id, include_archived=False)

    assert len(projects) == 1
    assert projects[0].name == "Active"


@pytest.mark.asyncio
async def test_list_projects_include_archived(
    project_service: ProjectService,
    test_user: User
):
    await project_service.create_project(test_user.id, ProjectCreate(name="Active"))
    archived = await project_service.create_project(
        test_user.id,
        ProjectCreate(name="Archived")
    )
    await project_service.archive_project(archived.id, test_user.id)

    projects = await project_service.list_projects(test_user.id, include_archived=True)

    assert len(projects) == 2


@pytest.mark.asyncio
async def test_update_project_success(
    project_service: ProjectService,
    test_user: User
):
    created = await project_service.create_project(
        test_user.id,
        ProjectCreate(name="Original", description="Old", tags=["old"])
    )

    updated = await project_service.update_project(
        created.id,
        test_user.id,
        ProjectUpdate(name="Updated", description="New", tags=["new"])
    )

    assert updated.name == "Updated"
    assert updated.description == "New"
    assert updated.tags == ["new"]


@pytest.mark.asyncio
async def test_update_project_not_found(
    project_service: ProjectService,
    test_user: User
):
    from uuid import uuid4

    with pytest.raises(NotFoundError):
        await project_service.update_project(
            uuid4(),
            test_user.id,
            ProjectUpdate(name="Updated")
        )


@pytest.mark.asyncio
async def test_update_project_duplicate_name(
    project_service: ProjectService,
    test_user: User
):
    """Test that updating to a duplicate name raises ConflictError."""
    await project_service.create_project(test_user.id, ProjectCreate(name="Existing"))
    project2 = await project_service.create_project(
        test_user.id,
        ProjectCreate(name="ToUpdate")
    )

    with pytest.raises(ConflictError, match="already exists"):
        await project_service.update_project(
            project2.id,
            test_user.id,
            ProjectUpdate(name="Existing")
        )


@pytest.mark.asyncio
async def test_update_project_same_name_allowed(
    project_service: ProjectService,
    test_user: User
):
    """Test that updating a project with its own name is allowed."""
    created = await project_service.create_project(
        test_user.id,
        ProjectCreate(name="Same Name")
    )

    # Update with same name (should not raise error)
    updated = await project_service.update_project(
        created.id,
        test_user.id,
        ProjectUpdate(name="Same Name", description="Updated description")
    )

    assert updated.name == "Same Name"
    assert updated.description == "Updated description"


@pytest.mark.asyncio
async def test_archive_project_success(
    project_service: ProjectService,
    test_user: User
):
    created = await project_service.create_project(
        test_user.id,
        ProjectCreate(name="To Archive")
    )

    archived = await project_service.archive_project(created.id, test_user.id)

    assert archived.is_archived is True


@pytest.mark.asyncio
async def test_archive_project_not_found(
    project_service: ProjectService,
    test_user: User
):
    from uuid import uuid4

    with pytest.raises(NotFoundError):
        await project_service.archive_project(uuid4(), test_user.id)


@pytest.mark.asyncio
async def test_unarchive_project_success(
    project_service: ProjectService,
    test_user: User
):
    created = await project_service.create_project(
        test_user.id,
        ProjectCreate(name="To Unarchive")
    )
    await project_service.archive_project(created.id, test_user.id)

    unarchived = await project_service.unarchive_project(created.id, test_user.id)

    assert unarchived.is_archived is False


@pytest.mark.asyncio
async def test_unarchive_project_not_found(
    project_service: ProjectService,
    test_user: User
):
    from uuid import uuid4

    with pytest.raises(NotFoundError):
        await project_service.unarchive_project(uuid4(), test_user.id)


@pytest.mark.asyncio
async def test_delete_archived_project_success(
    project_service: ProjectService,
    test_user: User
):
    """Test that archived projects can be deleted."""
    created = await project_service.create_project(
        test_user.id,
        ProjectCreate(name="To Delete")
    )
    await project_service.archive_project(created.id, test_user.id)

    # Should not raise error
    await project_service.delete_project(created.id, test_user.id)

    # Verify it's deleted
    with pytest.raises(NotFoundError):
        await project_service.get_project(created.id, test_user.id)


@pytest.mark.asyncio
async def test_delete_active_project_fails(
    project_service: ProjectService,
    test_user: User
):
    """Test that active (non-archived) projects cannot be deleted."""
    created = await project_service.create_project(
        test_user.id,
        ProjectCreate(name="Active Project")
    )

    with pytest.raises(ValidationError, match="must be archived"):
        await project_service.delete_project(created.id, test_user.id)

    # Verify project still exists
    found = await project_service.get_project(created.id, test_user.id)
    assert found is not None


@pytest.mark.asyncio
async def test_delete_project_not_found(
    project_service: ProjectService,
    test_user: User
):
    from uuid import uuid4

    with pytest.raises(NotFoundError):
        await project_service.delete_project(uuid4(), test_user.id)


@pytest.mark.asyncio
async def test_delete_project_wrong_user(
    project_service: ProjectService,
    test_user: User,
    another_user: User
):
    """Test that users cannot delete other users' projects."""
    created = await project_service.create_project(
        test_user.id,
        ProjectCreate(name="Private")
    )
    await project_service.archive_project(created.id, test_user.id)

    with pytest.raises(NotFoundError):
        await project_service.delete_project(created.id, another_user.id)
