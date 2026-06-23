"""Integration tests for GET /source-documents."""
import pytest
from httpx import AsyncClient

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


async def _signup_and_login(client: AsyncClient, email: str = "src@example.com") -> str:
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "Src User",
        },
    )
    resp = await client.post(
        "/api/v1/auth/signin",
        json={"email": email, "password": "ValidPass123!"},
    )
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_list_source_documents_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/source-documents")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_source_documents_returns_empty_list(client: AsyncClient):
    token = await _signup_and_login(client)
    resp = await client.get(
        "/api/v1/source-documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_source_documents_returns_uploaded_files(client: AsyncClient):
    token = await _signup_and_login(client, "src2@example.com")

    # Create a project
    proj = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Src Test Project"},
    )
    project_id = proj.json()["id"]

    # Upload a document (creates a source_document)
    await client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": project_id, "title": "My Doc", "parser_type": "simple"},
        files=[("file", ("test.pdf", MINIMAL_PDF, "application/pdf"))],
    )

    resp = await client.get(
        "/api/v1/source-documents",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    item = items[0]
    assert item["filename"] == "test.pdf"
    assert item["projectCount"] == 1
    assert "id" in item
    assert "sha256" in item
    assert "createdAt" in item
