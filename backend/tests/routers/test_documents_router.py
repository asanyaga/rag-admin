"""Integration tests for POST /documents/bulk."""
import pytest
from httpx import AsyncClient

# Minimal valid PDF bytes — distinct checksums so no duplicate conflict
MINIMAL_PDF_1 = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
MINIMAL_PDF_2 = b"%PDF-1.5\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


async def create_user_and_login(client: AsyncClient) -> str:
    await client.post(
        "/api/v1/auth/signup",
        json={
            "email": "bulktest@example.com",
            "password": "ValidPass123!",
            "password_confirm": "ValidPass123!",
            "full_name": "Bulk Test User",
        },
    )
    response = await client.post(
        "/api/v1/auth/signin",
        json={"email": "bulktest@example.com", "password": "ValidPass123!"},
    )
    return response.json()["access_token"]


async def create_project(client: AsyncClient, token: str) -> str:
    response = await client.post(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Bulk Upload Test Project"},
    )
    return response.json()["id"]


@pytest.mark.asyncio
async def test_bulk_upload_returns_202_with_results(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    response = await client.post(
        "/api/v1/documents/bulk",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": project_id, "parser_type": "simple"},
        files=[
            ("files", ("doc1.pdf", MINIMAL_PDF_1, "application/pdf")),
            ("files", ("doc2.pdf", MINIMAL_PDF_2, "application/pdf")),
        ],
    )

    assert response.status_code == 202
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 2
    for result in data["results"]:
        assert result["document"] is not None
        assert result["error"] is None
        assert result["document"]["status"] == "processing"


@pytest.mark.asyncio
async def test_bulk_upload_rejects_more_than_20_files(client: AsyncClient):
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    files = [
        ("files", (f"doc{i}.pdf", f"%PDF-1.4 file{i}".encode(), "application/pdf"))
        for i in range(21)
    ]

    response = await client.post(
        "/api/v1/documents/bulk",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": project_id, "parser_type": "simple"},
        files=files,
    )

    assert response.status_code == 400
    assert "20" in response.json()["detail"]


@pytest.mark.asyncio
async def test_bulk_upload_mixed_valid_invalid_files(client: AsyncClient):
    """Invalid file type returns per-item error; valid file succeeds."""
    token = await create_user_and_login(client)
    project_id = await create_project(client, token)

    response = await client.post(
        "/api/v1/documents/bulk",
        headers={"Authorization": f"Bearer {token}"},
        data={"project_id": project_id, "parser_type": "simple"},
        files=[
            ("files", ("valid.pdf", MINIMAL_PDF_1, "application/pdf")),
            ("files", ("bad.txt", b"plain text content here", "text/plain")),
        ],
    )

    assert response.status_code == 202
    data = response.json()
    results = {r["filename"]: r for r in data["results"]}
    assert results["valid.pdf"]["document"] is not None
    assert results["valid.pdf"]["error"] is None
    assert results["bad.txt"]["document"] is None
    assert results["bad.txt"]["error"] is not None


@pytest.mark.asyncio
async def test_bulk_upload_requires_auth(client: AsyncClient):
    response = await client.post(
        "/api/v1/documents/bulk",
        data={"project_id": "00000000-0000-0000-0000-000000000000"},
        files=[("files", ("doc.pdf", MINIMAL_PDF_1, "application/pdf"))],
    )
    assert response.status_code == 401
