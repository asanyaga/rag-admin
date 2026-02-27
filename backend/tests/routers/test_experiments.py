"""API tests for the experiments router."""
import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def create_user_and_login(client: AsyncClient) -> str:
    """Create a user and return access token."""
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "expuser@example.com",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "Experiment User",
        },
    )
    response = await client.post(
        "/api/v1/auth/signin",
        json={"email": "expuser@example.com", "password": "ValidPass123!"},
    )
    return response.json()["access_token"]


async def create_project(client: AsyncClient, token: str) -> str:
    """Create a project and return its ID."""
    resp = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Experiment Test Project"},
    )
    return resp.json()["id"]


async def create_experiment(
    client: AsyncClient, token: str, project_id: str, name: str = "Test Experiment",
    description: str | None = None,
) -> dict:
    """Create an experiment and return its JSON response."""
    resp = await client.post(
        f"/api/v1/projects/{project_id}/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name, "description": description},
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_experiment(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    resp = await client.post(
        f"/api/v1/projects/{project_id}/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Hypothesis A", "description": "Does X improve Y?"},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Hypothesis A"
    assert data["description"] == "Does X improve Y?"
    assert data["status"] == "active"
    assert data["runCount"] == 0
    assert data["baselineRunId"] is None
    assert data["baselineRun"] is None
    assert "id" in data
    assert "createdBy" in data
    assert "createdAt" in data


@pytest.mark.asyncio
async def test_create_experiment_minimal(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    resp = await client.post(
        f"/api/v1/projects/{project_id}/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Minimal"},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Minimal"
    assert data["description"] is None


@pytest.mark.asyncio
async def test_create_experiment_missing_name(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    resp = await client.post(
        f"/api/v1/projects/{project_id}/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_experiment_unauthenticated(client: AsyncClient):
    resp = await client.post(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/experiments",
        json={"name": "Nope"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_experiment_wrong_project(client: AsyncClient):
    token = await create_user_and_login(client)

    resp = await client.post(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Wrong"},
    )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_experiments_empty(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    resp = await client.get(
        f"/api/v1/projects/{project_id}/experiments",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_experiments(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    await create_experiment(client, token, project_id, name="Exp A")
    await create_experiment(client, token, project_id, name="Exp B")

    resp = await client.get(
        f"/api/v1/projects/{project_id}/experiments",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    names = {e["name"] for e in data}
    assert names == {"Exp A", "Exp B"}


@pytest.mark.asyncio
async def test_list_experiments_scoped_to_project(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    # Create another project
    resp2 = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Other Project"},
    )
    other_project_id = resp2.json()["id"]

    await create_experiment(client, token, project_id, name="In Project")
    await create_experiment(client, token, other_project_id, name="Other Project Exp")

    resp = await client.get(
        f"/api/v1/projects/{project_id}/experiments",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "In Project"


# ---------------------------------------------------------------------------
# Get detail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_experiment_detail(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)
    exp = await create_experiment(client, token, project_id, name="Detail")

    resp = await client.get(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Detail"
    assert "runs" in data
    assert isinstance(data["runs"], list)
    assert "variableDiff" in data
    assert "varying" in data["variableDiff"]
    assert "constant" in data["variableDiff"]


@pytest.mark.asyncio
async def test_get_experiment_not_found(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    resp = await client.get(
        f"/api/v1/projects/{project_id}/experiments/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_experiment_name(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)
    exp = await create_experiment(client, token, project_id, name="Original")

    resp = await client.patch(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Updated"},
    )

    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated"


@pytest.mark.asyncio
async def test_update_experiment_status(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)
    exp = await create_experiment(client, token, project_id)

    resp = await client.patch(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "concluded"},
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "concluded"


@pytest.mark.asyncio
async def test_update_experiment_notes(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)
    exp = await create_experiment(client, token, project_id)

    resp = await client.patch(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"notes": "Hybrid search is better"},
    )

    assert resp.status_code == 200
    assert resp.json()["notes"] == "Hybrid search is better"


@pytest.mark.asyncio
async def test_update_experiment_not_found(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    resp = await client.patch(
        f"/api/v1/projects/{project_id}/experiments/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Nope"},
    )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_experiment(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)
    exp = await create_experiment(client, token, project_id)

    resp = await client.delete(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # Verify it's gone
    get_resp = await client.get(
        f"/api/v1/projects/{project_id}/experiments/{exp['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_experiment_not_found(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    resp = await client.delete(
        f"/api/v1/projects/{project_id}/experiments/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 404
