"""Tests for the parser-eval router (project-scoped endpoints)."""
import pytest
from httpx import AsyncClient

from app.main import app
from app.dependencies.auth import get_current_active_user


@pytest.mark.asyncio
async def test_create_case_and_run_flow(client: AsyncClient, seed_project_user_source, monkeypatch):
    from app.services.parser_eval import engine as engine_mod
    from app.cdm.models import ParsedDocument, Page

    async def fake_capture(*a, **k):
        doc = ParsedDocument(id="d", source_document_id="s", parse_run_id="r",
                              page_count=1, pages=[Page(index=0, start_char=0, end_char=2)],
                              blocks=[], full_text="hi")
        return doc, {"usd": 0.0}, 3
    monkeypatch.setattr(engine_mod, "capture", fake_capture)

    project_id, user_id, source_id = seed_project_user_source

    class _FakeUser:
        id = user_id

    app.dependency_overrides[get_current_active_user] = lambda: _FakeUser()
    try:
        r = await client.post(
            f"/api/v1/projects/{project_id}/parser-eval/cases",
            json={"name": "c", "source_document_id": str(source_id),
                  "targets": [{"dimension": "text", "expected": {"pages": ["hi"]}}]})
        assert r.status_code == 200, r.text
        case_id = r.json()["id"]

        r = await client.get(f"/api/v1/projects/{project_id}/parser-eval/cases")
        assert r.status_code == 200
        assert len(r.json()) == 1

        r = await client.post(
            f"/api/v1/projects/{project_id}/parser-eval/runs",
            json={"name": "run", "case_ids": [case_id], "parsers": ["docling"]})
        assert r.status_code == 202, r.text
        run_id = r.json()["id"]

        r = await client.get(f"/api/v1/projects/{project_id}/parser-eval/runs")
        assert r.status_code == 200
        assert len(r.json()) == 1

        r = await client.get(
            f"/api/v1/projects/{project_id}/parser-eval/runs/{run_id}/results")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["score"] == 1.0
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_create_case_unknown_project_returns_404(client: AsyncClient, seed_project_user_source):
    from uuid import uuid4

    _, user_id, source_id = seed_project_user_source

    class _FakeUser:
        id = user_id

    app.dependency_overrides[get_current_active_user] = lambda: _FakeUser()
    try:
        r = await client.post(
            f"/api/v1/projects/{uuid4()}/parser-eval/cases",
            json={"name": "c", "source_document_id": str(source_id),
                  "targets": [{"dimension": "text", "expected": {"pages": ["hi"]}}]})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
