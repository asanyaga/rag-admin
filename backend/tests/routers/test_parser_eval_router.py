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
        assert r.json()["reviewStatus"] == "draft"

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
        assert results[0]["primaryMetric"] == "similarity"
        assert results[0]["variantKey"].startswith("docling@")

        # get-one-run route (used by the run-detail page)
        r = await client.get(f"/api/v1/projects/{project_id}/parser-eval/runs/{run_id}")
        assert r.status_code == 200
        assert r.json()["id"] == run_id
        assert r.json()["status"] in ("pending", "running", "completed")
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


def _fake_capture_table():
    from app.cdm.models import Block, BlockRole, ParsedDocument, Page, Table

    async def fake_capture(*a, **k):
        html = "<table><tr><td>a</td></tr></table>"
        doc = ParsedDocument(
            id="d", source_document_id="s", parse_run_id="r", page_count=1,
            pages=[Page(index=0)],
            blocks=[Block(id="b0", role=BlockRole.TABLE, native_type="table",
                          page_index=0, reading_order=0,
                          table=Table(rows=1, cols=1, cells=[], html=html))])
        return doc, {"usd": 0.0}, 100
    return fake_capture


@pytest.mark.asyncio
async def test_bootstrap_get_review_delete_flow(client: AsyncClient, seed_project_user_source, monkeypatch):
    from app.services.parser_eval import service as service_mod
    monkeypatch.setattr(service_mod, "capture", _fake_capture_table())

    project_id, user_id, source_id = seed_project_user_source

    class _FakeUser:
        id = user_id

    app.dependency_overrides[get_current_active_user] = lambda: _FakeUser()
    try:
        r = await client.post(
            f"/api/v1/projects/{project_id}/parser-eval/cases/bootstrap-table",
            json={"sourceDocumentId": str(source_id), "adapter": "docling", "config": {}})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["dimension"] == "table"
        assert body["reviewStatus"] == "draft"
        assert body["expected"]["tables"][0]["html"].startswith("<table")
        case_id = body["id"]

        g = await client.get(f"/api/v1/projects/{project_id}/parser-eval/cases/{case_id}")
        assert g.status_code == 200
        assert g.json()["expected"]["tables"][0]["page"] == 1

        p = await client.patch(
            f"/api/v1/projects/{project_id}/parser-eval/cases/{case_id}",
            json={"reviewStatus": "verified"})
        assert p.status_code == 200
        assert p.json()["reviewStatus"] == "verified"

        d = await client.delete(f"/api/v1/projects/{project_id}/parser-eval/cases/{case_id}")
        assert d.status_code == 204
        gone = await client.get(f"/api/v1/projects/{project_id}/parser-eval/cases/{case_id}")
        assert gone.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.asyncio
async def test_bootstrap_duplicate_returns_409(client: AsyncClient, seed_project_user_source, monkeypatch):
    from app.services.parser_eval import service as service_mod
    monkeypatch.setattr(service_mod, "capture", _fake_capture_table())

    project_id, user_id, source_id = seed_project_user_source

    class _FakeUser:
        id = user_id

    app.dependency_overrides[get_current_active_user] = lambda: _FakeUser()
    try:
        first = await client.post(
            f"/api/v1/projects/{project_id}/parser-eval/cases/bootstrap-table",
            json={"sourceDocumentId": str(source_id), "adapter": "docling", "config": {}})
        assert first.status_code == 200
        dup = await client.post(
            f"/api/v1/projects/{project_id}/parser-eval/cases/bootstrap-table",
            json={"sourceDocumentId": str(source_id), "adapter": "docling", "config": {}})
        assert dup.status_code == 409
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
