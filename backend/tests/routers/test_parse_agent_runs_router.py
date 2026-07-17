from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


async def _signup_and_login(client: AsyncClient, email: str = "pa@example.com") -> str:
    await client.post("/api/v1/auth/signup", json={
        "email": email, "password": "ValidPass123!",
        "password_confirm": "ValidPass123!", "full_name": "PA User",
    })
    resp = await client.post("/api/v1/auth/signin",
                             json={"email": email, "password": "ValidPass123!"})
    return resp.json()["access_token"]


async def _create_project(client: AsyncClient, token: str) -> str:
    resp = await client.post("/api/v1/projects", headers={"Authorization": f"Bearer {token}"},
                             json={"name": "PA Project"})
    return resp.json()["id"]


def _fake_parse_result(source_id: str):
    class _Run:
        id = uuid4()
        failed_pages: list[int] = []

    class _Doc:
        page_count = 1
        full_text = "Hello world."
        blocks: list[Any] = []

    return _Run(), _Doc()


@pytest.mark.asyncio
async def test_upload_creates_run_and_trace(client: AsyncClient, test_db: AsyncSession):
    token = await _signup_and_login(client)
    project_id = await _create_project(client, token)

    # Redirect the background task's own session to the SQLite test session.
    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=test_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    async def fake_parse_and_persist(**kwargs):
        return _fake_parse_result(str(kwargs["source"].id))

    with (
        patch("app.database.AsyncSessionLocal", mock_session_factory),
        patch("app.services.parsing.parsing_service.ParsingService.parse_and_persist",
              new=AsyncMock(side_effect=fake_parse_and_persist)),
    ):
        resp = await client.post(
            "/api/v1/parse-agent-runs",
            headers={"Authorization": f"Bearer {token}"},
            data={"project_id": project_id, "parser_type": "simple"},
            files=[("file", ("test.pdf", MINIMAL_PDF, "application/pdf"))],
        )
        assert resp.status_code == 202, resp.text
        run_id = resp.json()["runId"]

        got = await client.get(f"/api/v1/parse-agent-runs/{run_id}",
                               headers={"Authorization": f"Bearer {token}"})

    assert got.status_code == 200, got.text
    body = got.json()
    assert body["run"]["status"] == "completed"
    assert body["graphNodes"] == ["parse", "health_check"]
    assert [s["node"] for s in body["steps"]] == ["parse", "health_check"]


@pytest.mark.asyncio
async def test_get_run_requires_ownership(client: AsyncClient, test_db: AsyncSession):
    token = await _signup_and_login(client)
    resp = await client.get(f"/api/v1/parse-agent-runs/{uuid4()}",
                            headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_rejects_malformed_parse_config(client: AsyncClient, test_db: AsyncSession):
    token = await _signup_and_login(client)
    project_id = await _create_project(client, token)

    # Malformed JSON must be rejected with 400 before any background dispatch.
    resp = await client.post(
        "/api/v1/parse-agent-runs",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": project_id, "parser_type": "simple", "parse_config": "{not valid json"},
        files=[("file", ("test.pdf", MINIMAL_PDF, "application/pdf"))],
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_get_run_404_for_other_users_run(client: AsyncClient, test_db: AsyncSession):
    # User A creates a run via the patched happy path.
    token_a = await _signup_and_login(client)
    project_id = await _create_project(client, token_a)

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=test_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    async def fake_parse_and_persist(**kwargs):
        return _fake_parse_result(str(kwargs["source"].id))

    with (
        patch("app.database.AsyncSessionLocal", mock_session_factory),
        patch("app.services.parsing.parsing_service.ParsingService.parse_and_persist",
              new=AsyncMock(side_effect=fake_parse_and_persist)),
    ):
        resp = await client.post(
            "/api/v1/parse-agent-runs",
            headers={"Authorization": f"Bearer {token_a}"},
            data={"project_id": project_id, "parser_type": "simple"},
            files=[("file", ("test.pdf", MINIMAL_PDF, "application/pdf"))],
        )
        assert resp.status_code == 202, resp.text
        run_id = resp.json()["runId"]

    # User B owns no project pointing at this run -> the "run exists but not owned" branch 404s.
    token_b = await _signup_and_login(client, email="pb@example.com")
    got = await client.get(f"/api/v1/parse-agent-runs/{run_id}",
                           headers={"Authorization": f"Bearer {token_b}"})
    assert got.status_code == 404, got.text


@pytest.mark.asyncio
async def test_list_runs_returns_project_runs_newest_first(client: AsyncClient, test_db: AsyncSession):
    token = await _signup_and_login(client)
    project_id = await _create_project(client, token)

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=test_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    async def fake_parse_and_persist(**kwargs):
        return _fake_parse_result(str(kwargs["source"].id))

    with (
        patch("app.database.AsyncSessionLocal", mock_session_factory),
        patch("app.services.parsing.parsing_service.ParsingService.parse_and_persist",
              new=AsyncMock(side_effect=fake_parse_and_persist)),
    ):
        for name in ("a.pdf", "b.pdf"):
            resp = await client.post(
                "/api/v1/parse-agent-runs",
                headers={"Authorization": f"Bearer {token}"},
                data={"project_id": project_id, "parser_type": "simple"},
                files=[("file", (name, MINIMAL_PDF + name.encode(), "application/pdf"))],
            )
            assert resp.status_code == 202, resp.text

    listed = await client.get(
        f"/api/v1/parse-agent-runs?project_id={project_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert len(body) == 2
    assert {"id", "status", "startedAt", "sourceDocumentId"} <= set(body[0])
    # newest first
    assert body[0]["startedAt"] >= body[1]["startedAt"]


@pytest.mark.asyncio
async def test_list_runs_404_for_unowned_project(client: AsyncClient, test_db: AsyncSession):
    token_a = await _signup_and_login(client)
    project_id = await _create_project(client, token_a)

    token_b = await _signup_and_login(client, email="pc@example.com")
    resp = await client.get(
        f"/api/v1/parse-agent-runs?project_id={project_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
