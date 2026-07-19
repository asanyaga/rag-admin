"""Integration tests for POST /documents/from-source."""
import pytest
from httpx import AsyncClient

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


async def _signup_and_login(client: AsyncClient, email: str) -> str:
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "Test User",
        },
    )
    resp = await client.post(
        "/api/v1/auth/signin",
        json={"email": email, "password": "ValidPass123!"},
    )
    return resp.json()["access_token"]


async def _create_project(client: AsyncClient, token: str, name: str) -> str:
    resp = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name},
    )
    return resp.json()["id"]


async def _upload_doc(client: AsyncClient, token: str, project_id: str) -> dict:
    """Upload a document to get a source_document_id created."""
    resp = await client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": project_id, "title": "seed.pdf", "parser_type": "simple"},
        files=[("file", ("seed.pdf", MINIMAL_PDF, "application/pdf"))],
    )
    return resp.json()


@pytest.mark.asyncio
async def test_from_source_returns_202(client: AsyncClient):
    token = await _signup_and_login(client, "fromsource1@example.com")
    project_a = await _create_project(client, token, "Project A")
    project_b = await _create_project(client, token, "Project B")

    doc_a = await _upload_doc(client, token, project_a)
    source_document_id = doc_a["sourceDocumentId"]
    assert source_document_id is not None

    resp = await client.post(
        "/api/v1/documents/from-source",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "project_id": project_b,
            "source_document_id": source_document_id,
            "parser_type": "simple",
        },
    )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "processing"
    assert data["sourceDocumentId"] == source_document_id
    assert data["projectId"] == project_b


@pytest.mark.asyncio
async def test_from_source_404_on_bad_source_document(client: AsyncClient):
    token = await _signup_and_login(client, "fromsource2@example.com")
    project_id = await _create_project(client, token, "Project C")

    resp = await client.post(
        "/api/v1/documents/from-source",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "project_id": project_id,
            "source_document_id": "00000000-0000-0000-0000-000000000000",
            "parser_type": "simple",
        },
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_from_source_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/documents/from-source",
        json={
            "project_id": "00000000-0000-0000-0000-000000000000",
            "source_document_id": "00000000-0000-0000-0000-000000000000",
            "parser_type": "simple",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_from_source_rejects_invalid_parser_config(client: AsyncClient):
    """This endpoint names its config field `parse_config`, not `config` — a
    validator reading the wrong attribute 500s instead of 422ing."""
    token = await _signup_and_login(client, "fromsource4@example.com")
    project_a = await _create_project(client, token, "Project A")
    project_b = await _create_project(client, token, "Project B")
    doc_a = await _upload_doc(client, token, project_a)

    resp = await client.post(
        "/api/v1/documents/from-source",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "project_id": project_b,
            "source_document_id": doc_a["sourceDocumentId"],
            "parser_type": "docling",
            "parse_config": {"ocr_options": {"kind": "not-an-engine"}},
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_from_source_rejects_unknown_parser(client: AsyncClient):
    token = await _signup_and_login(client, "fromsource5@example.com")
    project_a = await _create_project(client, token, "Project A")
    project_b = await _create_project(client, token, "Project B")
    doc_a = await _upload_doc(client, token, project_a)

    resp = await client.post(
        "/api/v1/documents/from-source",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "project_id": project_b,
            "source_document_id": doc_a["sourceDocumentId"],
            "parser_type": "magic_parser",
        },
    )
    assert resp.status_code == 422
