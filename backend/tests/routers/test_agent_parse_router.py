"""Tests for POST /agent/parse/projects/{project_id}/runs."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.dependencies.auth import get_current_active_user
from app.main import app
from app.models.agent_run import AgentRunStatus
from app.schemas.agent import AgentRunResponse


def _mock_user():
    """Return a lightweight fake user for auth bypass."""
    user = MagicMock()
    user.id = uuid4()
    user.email = "test@example.com"
    user.is_active = True
    return user


def _fake_agent_run_response() -> AgentRunResponse:
    now = datetime.now(timezone.utc)
    return AgentRunResponse(
        id=uuid4(),
        projectId=uuid4(),
        agentDefinitionId=uuid4(),
        status=AgentRunStatus.running,
        statusMessage=None,
        initialState={},
        currentState=None,
        currentNode=None,
        threadId=None,
        createdBy=uuid4(),
        createdAt=now,
        updatedAt=now,
    )


@pytest.mark.asyncio
async def test_start_parse_run_returns_202(client: AsyncClient):
    from app.routers.agent import get_parse_run_service

    stub_service = MagicMock()
    stub_service.start_parse_run = AsyncMock(return_value=_fake_agent_run_response())

    app.dependency_overrides[get_current_active_user] = _mock_user
    app.dependency_overrides[get_parse_run_service] = lambda: stub_service

    try:
        resp = await client.post(
            "/api/v1/agent/parse/projects/33333333-3333-3333-3333-333333333333/runs",
            json={
                "agentDefinitionId": "44444444-4444-4444-4444-444444444444",
                "sourceDocumentId": "55555555-5555-5555-5555-555555555555",
                "parser": "simple",
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
        app.dependency_overrides.pop(get_parse_run_service, None)

    assert resp.status_code == 202, resp.text
    assert stub_service.start_parse_run.await_count == 1


@pytest.mark.asyncio
async def test_start_parse_run_missing_key_returns_400(client: AsyncClient):
    from app.routers.agent import get_parse_run_service

    stub_service = MagicMock()
    stub_service.start_parse_run = AsyncMock(
        side_effect=ValueError("No API key configured for parser 'llamaparse'.")
    )

    app.dependency_overrides[get_current_active_user] = _mock_user
    app.dependency_overrides[get_parse_run_service] = lambda: stub_service

    try:
        resp = await client.post(
            "/api/v1/agent/parse/projects/33333333-3333-3333-3333-333333333333/runs",
            json={
                "agentDefinitionId": "44444444-4444-4444-4444-444444444444",
                "sourceDocumentId": "55555555-5555-5555-5555-555555555555",
                "parser": "llamaparse",
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
        app.dependency_overrides.pop(get_parse_run_service, None)

    assert resp.status_code == 400, resp.text
