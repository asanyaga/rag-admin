"""API tests for eval runs router — experiment-related additions."""
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
            "email": "evalrunuser@example.com",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "Eval Run User",
        },
    )
    response = await client.post(
        "/api/v1/auth/signin",
        json={"email": "evalrunuser@example.com", "password": "ValidPass123!"},
    )
    return response.json()["access_token"]


async def create_project(client: AsyncClient, token: str) -> str:
    """Create a project and return its ID."""
    resp = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Eval Run Test Project"},
    )
    return resp.json()["id"]


async def create_golden_set(client: AsyncClient, token: str, project_id: str) -> str:
    """Create a golden set with a query and return its ID."""
    resp = await client.post(
        f"/api/v1/projects/{project_id}/golden-sets",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Test Golden Set"},
    )
    gs_id = resp.json()["id"]
    # Add a query
    await client.post(
        f"/api/v1/projects/{project_id}/golden-sets/{gs_id}/queries",
        headers={"Authorization": f"Bearer {token}"},
        json={"queryText": "What is RAG?"},
    )
    return gs_id


async def create_index(client: AsyncClient, token: str, project_id: str) -> str:
    """Create an index and return its ID."""
    resp = await client.post(
        f"/api/v1/projects/{project_id}/indexes",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Test Index",
            "config": {
                "parser": "llamaparse",
                "parseConfigHash": "h" * 64,
                "chunkingStrategy": "recursive_character",
                "chunkSize": 512,
            },
        },
    )
    return resp.json()["id"]


async def create_experiment(client: AsyncClient, token: str, project_id: str) -> str:
    """Create an experiment and return its ID."""
    resp = await client.post(
        f"/api/v1/projects/{project_id}/experiments",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Test Experiment"},
    )
    return resp.json()["id"]


async def create_eval_run(
    client: AsyncClient,
    token: str,
    project_id: str,
    golden_set_id: str,
    index_id: str,
    experiment_id: str | None = None,
    variant_label: str | None = None,
    name: str = "Test Run",
) -> dict:
    """Create an eval run and return its JSON response."""
    payload = {
        "goldenSetId": golden_set_id,
        "indexId": index_id,
        "name": name,
        "config": {"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
    }
    if experiment_id:
        payload["experimentId"] = experiment_id
    if variant_label:
        payload["variantLabel"] = variant_label

    resp = await client.post(
        f"/api/v1/projects/{project_id}/eval-runs",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
    return resp.json()


# ---------------------------------------------------------------------------
# Create with experiment fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_run_with_experiment_id(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)
    gs_id = await create_golden_set(client, token, project_id)
    index_id = await create_index(client, token, project_id)
    exp_id = await create_experiment(client, token, project_id)

    data = await create_eval_run(
        client, token, project_id, gs_id, index_id,
        experiment_id=exp_id, variant_label="topK=10",
    )

    assert data["experimentId"] == exp_id
    assert data["experimentName"] == "Test Experiment"
    assert data["variantLabel"] == "topK=10"


@pytest.mark.asyncio
async def test_create_run_without_experiment_id(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)
    gs_id = await create_golden_set(client, token, project_id)
    index_id = await create_index(client, token, project_id)

    data = await create_eval_run(client, token, project_id, gs_id, index_id)

    assert data["experimentId"] is None
    assert data["experimentName"] is None
    assert data["variantLabel"] is None


# ---------------------------------------------------------------------------
# List with experiment fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_run_experiment_id_in_list(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)
    gs_id = await create_golden_set(client, token, project_id)
    index_id = await create_index(client, token, project_id)
    exp_id = await create_experiment(client, token, project_id)

    await create_eval_run(
        client, token, project_id, gs_id, index_id,
        experiment_id=exp_id, variant_label="v1",
    )

    resp = await client.get(
        f"/api/v1/projects/{project_id}/eval-runs",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["experimentId"] == exp_id
    assert data[0]["experimentName"] == "Test Experiment"
    assert data[0]["variantLabel"] == "v1"


# ---------------------------------------------------------------------------
# Get run config (clone feature)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_run_config(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)
    gs_id = await create_golden_set(client, token, project_id)
    index_id = await create_index(client, token, project_id)
    exp_id = await create_experiment(client, token, project_id)

    run = await create_eval_run(
        client, token, project_id, gs_id, index_id,
        experiment_id=exp_id, variant_label="baseline",
    )

    resp = await client.get(
        f"/api/v1/projects/{project_id}/eval-runs/{run['id']}/config",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    config = resp.json()
    assert config["goldenSetId"] == gs_id
    assert config["indexId"] == index_id
    assert config["name"] == "Test Run"
    assert config["config"]["searchType"] == "semantic"
    assert config["config"]["topK"] == 5
    assert config["mode"] == "retrieval_only"
    assert config["generationConfig"] is None
    assert config["judgeConfig"] is None
    assert config["experimentId"] == exp_id
    assert config["variantLabel"] == "baseline"


@pytest.mark.asyncio
async def test_get_run_config_not_found(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    resp = await client.get(
        f"/api/v1/projects/{project_id}/eval-runs/00000000-0000-0000-0000-000000000000/config",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Answer mode with PromptConfig fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_run_answer_mode_with_prompt_configs(client: AsyncClient):
    """Creating a retrieval_and_answer run with generationConfig + judgeConfig succeeds."""
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)
    gs_id = await create_golden_set(client, token, project_id)
    index_id = await create_index(client, token, project_id)

    resp = await client.post(
        f"/api/v1/projects/{project_id}/eval-runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "goldenSetId": gs_id,
            "indexId": index_id,
            "name": "Answer Run",
            "config": {"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
            "mode": "retrieval_and_answer",
            "generationConfig": {
                "provider": "ollama_local",
                "model": "llama3.2",
                "temperature": 0.0,
                "maxTokens": 1024,
            },
            "judgeConfig": {
                "provider": "ollama_local",
                "model": "llama3.2",
            },
        },
    )

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["mode"] == "retrieval_and_answer"
    assert data["generationConfig"]["provider"] == "ollama_local"
    assert data["generationConfig"]["model"] == "llama3.2"
    assert data["judgeConfig"]["provider"] == "ollama_local"
    assert data["judgeConfig"]["model"] == "llama3.2"


@pytest.mark.asyncio
async def test_create_run_answer_mode_missing_generation_config_rejected(client: AsyncClient):
    """Creating a retrieval_and_answer run without generationConfig is rejected."""
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)
    gs_id = await create_golden_set(client, token, project_id)
    index_id = await create_index(client, token, project_id)

    resp = await client.post(
        f"/api/v1/projects/{project_id}/eval-runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "goldenSetId": gs_id,
            "indexId": index_id,
            "config": {"searchType": "semantic", "topK": 5, "similarityThreshold": 0},
            "mode": "retrieval_and_answer",
        },
    )

    assert resp.status_code == 422
