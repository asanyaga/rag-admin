"""Tests for the parser-eval router (project-scoped endpoints, canonical model)."""
import pytest
from uuid import uuid4
from httpx import AsyncClient

from app.main import app
from app.dependencies.auth import get_current_active_user


def _fake_capture():
    from app.cdm.models import ParsedDocument, Page

    async def fake_capture(*a, **k):
        doc = ParsedDocument(id="d", source_document_id="s", parse_run_id="r",
                             page_count=1, pages=[Page(index=0, start_char=0, end_char=2)],
                             blocks=[], full_text="hi")
        return doc, {"usd": 0.0}, 3
    return fake_capture


@pytest.mark.asyncio
async def test_dataset_run_snapshot_flow(client: AsyncClient, seed_project_user_source, monkeypatch):
    from app.services.parser_eval import engine as engine_mod
    monkeypatch.setattr(engine_mod, "capture", _fake_capture())

    project_id, user_id, source_id = seed_project_user_source

    class _FakeUser:
        id = user_id

    app.dependency_overrides[get_current_active_user] = lambda: _FakeUser()
    try:
        # Create a case (doc + dimension + ground truth).
        r = await client.post(
            f"/api/v1/projects/{project_id}/parser-eval/cases",
            json={"source_document_id": str(source_id), "dimension": "text",
                  "expected": {"pages": ["hi"]}})
        assert r.status_code == 200, r.text
        case_id = r.json()["id"]
        assert r.json()["review_status"] == "draft"

        # Create a dataset and add the case.
        r = await client.post(
            f"/api/v1/projects/{project_id}/parser-eval/datasets", json={"name": "smoke"})
        assert r.status_code == 200, r.text
        dataset_id = r.json()["id"]

        r = await client.post(
            f"/api/v1/projects/{project_id}/parser-eval/datasets/{dataset_id}/cases/{case_id}")
        assert r.status_code == 204

        r = await client.get(
            f"/api/v1/projects/{project_id}/parser-eval/datasets/{dataset_id}/cases")
        assert r.status_code == 200
        assert [c["id"] for c in r.json()] == [case_id]

        # Run against the dataset → snapshot + 202.
        r = await client.post(
            f"/api/v1/projects/{project_id}/parser-eval/runs",
            json={"variants": [{"adapter": "docling", "config": {}}], "dataset_id": dataset_id})
        assert r.status_code == 202, r.text
        run_id = r.json()["id"]

        # Results carry the metrics map, not a bare score.
        r = await client.get(f"/api/v1/projects/{project_id}/parser-eval/runs/{run_id}/results")
        assert r.status_code == 200
        results = r.json()
        assert len(results) == 1
        assert results[0]["metrics"]["similarity"] == 1.0
        assert results[0]["primary_metric"] == "similarity"
        assert results[0]["variant_key"].startswith("docling@")
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_create_run_unknown_adapter_returns_422(client: AsyncClient, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source

    class _FakeUser:
        id = user_id

    app.dependency_overrides[get_current_active_user] = lambda: _FakeUser()
    try:
        r = await client.post(
            f"/api/v1/projects/{project_id}/parser-eval/cases",
            json={"source_document_id": str(source_id), "dimension": "text",
                  "expected": {"pages": ["hi"]}})
        assert r.status_code == 200, r.text
        case_id = r.json()["id"]

        r = await client.post(
            f"/api/v1/projects/{project_id}/parser-eval/runs",
            json={"variants": [{"adapter": "not_a_parser", "config": {}}],
                  "eval_case_ids": [case_id]})
        assert r.status_code == 422
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_create_case_unknown_project_returns_404(client: AsyncClient, seed_project_user_source):
    _, user_id, source_id = seed_project_user_source

    class _FakeUser:
        id = user_id

    app.dependency_overrides[get_current_active_user] = lambda: _FakeUser()
    try:
        r = await client.post(
            f"/api/v1/projects/{uuid4()}/parser-eval/cases",
            json={"source_document_id": str(source_id), "dimension": "text",
                  "expected": {"pages": ["hi"]}})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)
