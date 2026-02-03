import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthProvider, Project, User
from app.repositories.project_repository import ProjectRepository
from app.repositories.user_repository import UserRepository
from app.schemas.project import ProjectCreate, ProjectUpdate


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
def project_repo(test_db: AsyncSession) -> ProjectRepository:
    return ProjectRepository(test_db)


@pytest.mark.asyncio
async def test_create_project(project_repo: ProjectRepository, test_user: User):
    data = ProjectCreate(
        name="Test Project",
        description="A test project",
        tags=["tag1", "tag2"]
    )

    project = await project_repo.create(test_user.id, data)

    assert project.id is not None
    assert project.user_id == test_user.id
    assert project.name == "Test Project"
    assert project.description == "A test project"
    assert project.tags == ["tag1", "tag2"]
    assert project.is_archived is False
    assert project.created_at is not None
    assert project.updated_at is not None


@pytest.mark.asyncio
async def test_create_project_without_optional_fields(
    project_repo: ProjectRepository,
    test_user: User
):
    data = ProjectCreate(name="Minimal Project")

    project = await project_repo.create(test_user.id, data)

    assert project.name == "Minimal Project"
    assert project.description is None
    assert project.tags == []
    assert project.is_archived is False


@pytest.mark.asyncio
async def test_get_by_id_found(project_repo: ProjectRepository, test_user: User):
    data = ProjectCreate(name="Find Me")
    created = await project_repo.create(test_user.id, data)

    found = await project_repo.get_by_id(created.id, test_user.id)

    assert found is not None
    assert found.id == created.id
    assert found.name == "Find Me"


@pytest.mark.asyncio
async def test_get_by_id_not_found(project_repo: ProjectRepository, test_user: User):
    from uuid import uuid4

    found = await project_repo.get_by_id(uuid4(), test_user.id)

    assert found is None


@pytest.mark.asyncio
async def test_get_by_id_wrong_user(
    project_repo: ProjectRepository,
    test_user: User,
    another_user: User
):
    """Test that users cannot access other users' projects."""
    data = ProjectCreate(name="Private Project")
    created = await project_repo.create(test_user.id, data)

    # Try to get project with another user's ID
    found = await project_repo.get_by_id(created.id, another_user.id)

    assert found is None


@pytest.mark.asyncio
async def test_get_by_name_found(project_repo: ProjectRepository, test_user: User):
    data = ProjectCreate(name="Unique Name")
    await project_repo.create(test_user.id, data)

    found = await project_repo.get_by_name(test_user.id, "Unique Name")

    assert found is not None
    assert found.name == "Unique Name"


@pytest.mark.asyncio
async def test_get_by_name_not_found(project_repo: ProjectRepository, test_user: User):
    found = await project_repo.get_by_name(test_user.id, "Nonexistent")

    assert found is None


@pytest.mark.asyncio
async def test_list_all_active_only(project_repo: ProjectRepository, test_user: User):
    # Create active projects
    await project_repo.create(test_user.id, ProjectCreate(name="Active 1"))
    await project_repo.create(test_user.id, ProjectCreate(name="Active 2"))

    # Create and archive a project
    archived = await project_repo.create(test_user.id, ProjectCreate(name="Archived"))
    await project_repo.archive(archived.id, test_user.id)

    # List only active projects
    projects = await project_repo.list_all(test_user.id, include_archived=False)

    assert len(projects) == 2
    assert all(not p.is_archived for p in projects)
    assert {p.name for p in projects} == {"Active 1", "Active 2"}


@pytest.mark.asyncio
async def test_list_all_include_archived(
    project_repo: ProjectRepository,
    test_user: User
):
    # Create active and archived projects
    await project_repo.create(test_user.id, ProjectCreate(name="Active"))
    archived = await project_repo.create(test_user.id, ProjectCreate(name="Archived"))
    await project_repo.archive(archived.id, test_user.id)

    # List all projects including archived
    projects = await project_repo.list_all(test_user.id, include_archived=True)

    assert len(projects) == 2
    assert {p.name for p in projects} == {"Active", "Archived"}


@pytest.mark.asyncio
async def test_list_all_sorted_by_created_at(
    project_repo: ProjectRepository,
    test_user: User
):
    """Test that projects are sorted by created_at DESC (newest first)."""
    await project_repo.create(test_user.id, ProjectCreate(name="First"))
    await project_repo.create(test_user.id, ProjectCreate(name="Second"))
    await project_repo.create(test_user.id, ProjectCreate(name="Third"))

    projects = await project_repo.list_all(test_user.id)

    # Should be in reverse order (newest first)
    assert [p.name for p in projects] == ["Third", "Second", "First"]


@pytest.mark.asyncio
async def test_list_all_user_scoping(
    project_repo: ProjectRepository,
    test_user: User,
    another_user: User
):
    """Test that users only see their own projects."""
    await project_repo.create(test_user.id, ProjectCreate(name="User 1 Project"))
    await project_repo.create(another_user.id, ProjectCreate(name="User 2 Project"))

    user1_projects = await project_repo.list_all(test_user.id)
    user2_projects = await project_repo.list_all(another_user.id)

    assert len(user1_projects) == 1
    assert user1_projects[0].name == "User 1 Project"
    assert len(user2_projects) == 1
    assert user2_projects[0].name == "User 2 Project"


@pytest.mark.asyncio
async def test_update_project(project_repo: ProjectRepository, test_user: User):
    created = await project_repo.create(
        test_user.id,
        ProjectCreate(name="Original", description="Old description", tags=["old"])
    )

    update_data = ProjectUpdate(
        name="Updated",
        description="New description",
        tags=["new", "tags"]
    )
    updated = await project_repo.update(created.id, test_user.id, update_data)

    assert updated is not None
    assert updated.id == created.id
    assert updated.name == "Updated"
    assert updated.description == "New description"
    assert updated.tags == ["new", "tags"]


@pytest.mark.asyncio
async def test_update_project_partial(project_repo: ProjectRepository, test_user: User):
    """Test partial update (only some fields)."""
    created = await project_repo.create(
        test_user.id,
        ProjectCreate(name="Original", description="Description", tags=["tag"])
    )

    # Update only the name
    update_data = ProjectUpdate(name="Updated Name")
    updated = await project_repo.update(created.id, test_user.id, update_data)

    assert updated is not None
    assert updated.name == "Updated Name"
    assert updated.description == "Description"  # Unchanged
    assert updated.tags == ["tag"]  # Unchanged


@pytest.mark.asyncio
async def test_update_project_not_found(
    project_repo: ProjectRepository,
    test_user: User
):
    from uuid import uuid4

    update_data = ProjectUpdate(name="Updated")
    updated = await project_repo.update(uuid4(), test_user.id, update_data)

    assert updated is None


@pytest.mark.asyncio
async def test_archive_project(project_repo: ProjectRepository, test_user: User):
    created = await project_repo.create(test_user.id, ProjectCreate(name="To Archive"))

    archived = await project_repo.archive(created.id, test_user.id)

    assert archived is not None
    assert archived.id == created.id
    assert archived.is_archived is True


@pytest.mark.asyncio
async def test_unarchive_project(project_repo: ProjectRepository, test_user: User):
    created = await project_repo.create(test_user.id, ProjectCreate(name="To Unarchive"))
    await project_repo.archive(created.id, test_user.id)

    unarchived = await project_repo.unarchive(created.id, test_user.id)

    assert unarchived is not None
    assert unarchived.is_archived is False


@pytest.mark.asyncio
async def test_delete_project(project_repo: ProjectRepository, test_user: User):
    created = await project_repo.create(test_user.id, ProjectCreate(name="To Delete"))

    result = await project_repo.delete(created.id, test_user.id)

    assert result is True

    # Verify it's deleted
    found = await project_repo.get_by_id(created.id, test_user.id)
    assert found is None


@pytest.mark.asyncio
async def test_delete_project_not_found(
    project_repo: ProjectRepository,
    test_user: User
):
    from uuid import uuid4

    result = await project_repo.delete(uuid4(), test_user.id)

    assert result is False


@pytest.mark.asyncio
async def test_unique_name_per_user_constraint(
    project_repo: ProjectRepository,
    test_user: User
):
    """Test that project names must be unique per user."""
    await project_repo.create(test_user.id, ProjectCreate(name="Duplicate"))

    with pytest.raises(IntegrityError):
        await project_repo.create(test_user.id, ProjectCreate(name="Duplicate"))


@pytest.mark.asyncio
async def test_same_name_different_users_allowed(
    project_repo: ProjectRepository,
    test_user: User,
    another_user: User
):
    """Test that different users can have projects with the same name."""
    await project_repo.create(test_user.id, ProjectCreate(name="Same Name"))
    project2 = await project_repo.create(another_user.id, ProjectCreate(name="Same Name"))

    assert project2 is not None
    assert project2.name == "Same Name"
