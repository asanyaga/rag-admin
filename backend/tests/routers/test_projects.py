import pytest
from httpx import AsyncClient


async def create_user_and_login(client: AsyncClient) -> str:
    """Helper to create a user and return access token."""
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "testuser@example.com",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "Test User"
        }
    )

    response = await client.post(
        "/api/v1/auth/signin",
        json={
            "email": "testuser@example.com",
            "password": "ValidPass123!",
        }
    )

    return response.json()["access_token"]


async def create_another_user_and_login(client: AsyncClient) -> str:
    """Helper to create another user and return access token."""
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "anotheruser@example.com",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "Another User"
        }
    )

    response = await client.post(
        "/api/v1/auth/signin",
        json={
            "email": "anotheruser@example.com",
            "password": "ValidPass123!",
        }
    )

    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_create_project_success(client: AsyncClient):
    token = await create_user_and_login(client)

    response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Test Project",
            "description": "A test project",
            "tags": ["tag1", "tag2"]
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Project"
    assert data["description"] == "A test project"
    assert data["tags"] == ["tag1", "tag2"]
    assert data["isArchived"] is False
    assert "id" in data
    assert "userId" in data
    assert "createdAt" in data
    assert "updatedAt" in data


@pytest.mark.asyncio
async def test_create_project_minimal(client: AsyncClient):
    """Test creating a project with only required fields."""
    token = await create_user_and_login(client)

    response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Minimal Project"}
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Minimal Project"
    assert data["description"] is None
    assert data["tags"] == []


@pytest.mark.asyncio
async def test_create_project_unauthenticated(client: AsyncClient):
    """Test that creating a project requires authentication."""
    response = await client.post(
        "/api/v1/projects",
        json={"name": "Test Project"}
    )

    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_project_duplicate_name(client: AsyncClient):
    """Test that duplicate project names for the same user fail."""
    token = await create_user_and_login(client)

    # Create first project
    await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Duplicate"}
    )

    # Try to create second project with same name
    response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Duplicate"}
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_project_invalid_data(client: AsyncClient):
    """Test validation errors."""
    token = await create_user_and_login(client)

    # Missing required field
    response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={}
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_projects_empty(client: AsyncClient):
    """Test listing projects when none exist."""
    token = await create_user_and_login(client)

    response = await client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient):
    """Test listing user's projects."""
    token = await create_user_and_login(client)

    # Create projects
    await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Project 1"}
    )
    await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Project 2"}
    )

    response = await client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert {p["name"] for p in data} == {"Project 1", "Project 2"}


@pytest.mark.asyncio
async def test_list_projects_exclude_archived(client: AsyncClient):
    """Test that archived projects are excluded by default."""
    token = await create_user_and_login(client)

    # Create active project
    await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Active"}
    )

    # Create and archive project
    create_response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Archived"}
    )
    project_id = create_response.json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/archive",
        headers={"Authorization": f"Bearer {token}"}
    )

    # List without archived
    response = await client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Active"


@pytest.mark.asyncio
async def test_list_projects_include_archived(client: AsyncClient):
    """Test listing projects including archived."""
    token = await create_user_and_login(client)

    # Create active project
    await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Active"}
    )

    # Create and archive project
    create_response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Archived"}
    )
    project_id = create_response.json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/archive",
        headers={"Authorization": f"Bearer {token}"}
    )

    # List with archived
    response = await client.get(
        "/api/v1/projects?include_archived=true",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_projects_user_scoping(client: AsyncClient):
    """Test that users only see their own projects."""
    token1 = await create_user_and_login(client)
    token2 = await create_another_user_and_login(client)

    # User 1 creates a project
    await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token1}"},
        json={"name": "User 1 Project"}
    )

    # User 2 creates a project
    await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token2}"},
        json={"name": "User 2 Project"}
    )

    # User 1 should only see their project
    response1 = await client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token1}"}
    )
    data1 = response1.json()
    assert len(data1) == 1
    assert data1[0]["name"] == "User 1 Project"

    # User 2 should only see their project
    response2 = await client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token2}"}
    )
    data2 = response2.json()
    assert len(data2) == 1
    assert data2[0]["name"] == "User 2 Project"


@pytest.mark.asyncio
async def test_get_project_success(client: AsyncClient):
    """Test getting a specific project."""
    token = await create_user_and_login(client)

    create_response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Get Me"}
    )
    project_id = create_response.json()["id"]

    response = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == project_id
    assert data["name"] == "Get Me"


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient):
    """Test getting a non-existent project."""
    token = await create_user_and_login(client)

    response = await client.get(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_project_wrong_user(client: AsyncClient):
    """Test that users cannot access other users' projects."""
    token1 = await create_user_and_login(client)
    token2 = await create_another_user_and_login(client)

    # User 1 creates a project
    create_response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token1}"},
        json={"name": "Private Project"}
    )
    project_id = create_response.json()["id"]

    # User 2 tries to access it
    response = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token2}"}
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_project_success(client: AsyncClient):
    """Test updating a project."""
    token = await create_user_and_login(client)

    # Create project
    create_response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Original", "description": "Old", "tags": ["old"]}
    )
    project_id = create_response.json()["id"]

    # Update project
    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Updated", "description": "New", "tags": ["new"]}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated"
    assert data["description"] == "New"
    assert data["tags"] == ["new"]


@pytest.mark.asyncio
async def test_update_project_partial(client: AsyncClient):
    """Test partial update of a project."""
    token = await create_user_and_login(client)

    # Create project
    create_response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Original", "description": "Description", "tags": ["tag"]}
    )
    project_id = create_response.json()["id"]

    # Update only name
    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Updated Name"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "Description"
    assert data["tags"] == ["tag"]


@pytest.mark.asyncio
async def test_update_project_not_found(client: AsyncClient):
    """Test updating a non-existent project."""
    token = await create_user_and_login(client)

    response = await client.patch(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Updated"}
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_project_duplicate_name(client: AsyncClient):
    """Test that updating to a duplicate name fails."""
    token = await create_user_and_login(client)

    # Create two projects
    await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Existing"}
    )
    create_response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "ToUpdate"}
    )
    project_id = create_response.json()["id"]

    # Try to update to existing name
    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Existing"}
    )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_archive_project_success(client: AsyncClient):
    """Test archiving a project."""
    token = await create_user_and_login(client)

    # Create project
    create_response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "To Archive"}
    )
    project_id = create_response.json()["id"]

    # Archive project
    response = await client.post(
        f"/api/v1/projects/{project_id}/archive",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["isArchived"] is True


@pytest.mark.asyncio
async def test_archive_project_not_found(client: AsyncClient):
    """Test archiving a non-existent project."""
    token = await create_user_and_login(client)

    response = await client.post(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/archive",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unarchive_project_success(client: AsyncClient):
    """Test unarchiving a project."""
    token = await create_user_and_login(client)

    # Create and archive project
    create_response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "To Unarchive"}
    )
    project_id = create_response.json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/archive",
        headers={"Authorization": f"Bearer {token}"}
    )

    # Unarchive project
    response = await client.post(
        f"/api/v1/projects/{project_id}/unarchive",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["isArchived"] is False


@pytest.mark.asyncio
async def test_unarchive_project_not_found(client: AsyncClient):
    """Test unarchiving a non-existent project."""
    token = await create_user_and_login(client)

    response = await client.post(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/unarchive",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_archived_project_success(client: AsyncClient):
    """Test that archived projects can be deleted."""
    token = await create_user_and_login(client)

    # Create and archive project
    create_response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "To Delete"}
    )
    project_id = create_response.json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/archive",
        headers={"Authorization": f"Bearer {token}"}
    )

    # Delete project
    response = await client.delete(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204

    # Verify it's deleted
    get_response = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_active_project_fails(client: AsyncClient):
    """Test that active (non-archived) projects cannot be deleted."""
    token = await create_user_and_login(client)

    # Create project (not archived)
    create_response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Active Project"}
    )
    project_id = create_response.json()["id"]

    # Try to delete without archiving
    response = await client.delete(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400
    assert "must be archived" in response.json()["detail"]

    # Verify project still exists
    get_response = await client.get(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert get_response.status_code == 200


@pytest.mark.asyncio
async def test_delete_project_not_found(client: AsyncClient):
    """Test deleting a non-existent project."""
    token = await create_user_and_login(client)

    response = await client.delete(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_wrong_user(client: AsyncClient):
    """Test that users cannot delete other users' projects."""
    token1 = await create_user_and_login(client)
    token2 = await create_another_user_and_login(client)

    # User 1 creates and archives a project
    create_response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token1}"},
        json={"name": "Private Project"}
    )
    project_id = create_response.json()["id"]
    await client.post(
        f"/api/v1/projects/{project_id}/archive",
        headers={"Authorization": f"Bearer {token1}"}
    )

    # User 2 tries to delete it
    response = await client.delete(
        f"/api/v1/projects/{project_id}",
        headers={"Authorization": f"Bearer {token2}"}
    )

    assert response.status_code == 404
