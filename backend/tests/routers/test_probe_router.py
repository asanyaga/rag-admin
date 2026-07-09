"""Integration tests for POST /probe."""
import uuid
import fitz
import pytest
from httpx import AsyncClient


async def _login(client: AsyncClient) -> str:
    await client.post("/api/v1/auth/signup", json={
        "email": "probe@example.com", "password": "ValidPass123!",
        "password_confirm": "ValidPass123!", "full_name": "Probe Test User",
    })
    resp = await client.post("/api/v1/auth/signin", json={
        "email": "probe@example.com", "password": "ValidPass123!"})
    return resp.json()["access_token"]


async def _project(client: AsyncClient, token: str) -> str:
    resp = await client.post("/api/v1/projects", headers={"Authorization": f"Bearer {token}"},
                             json={"name": "Probe Test Project"})
    return resp.json()["id"]


def _real_pdf_bytes() -> bytes:
    doc = fitz.open(); page = doc.new_page()
    page.insert_text((72, 72), "Hello probe world with enough text")
    data = doc.tobytes(); doc.close(); return data


async def _upload(client: AsyncClient, token: str, project_id: str) -> str:
    resp = await client.post(
        "/api/v1/documents/bulk", headers={"Authorization": f"Bearer {token}"},
        data={"project_id": project_id, "parser_type": "simple"},
        files=[("files", ("probe.pdf", _real_pdf_bytes(), "application/pdf"))])
    return resp.json()["results"][0]["document"]["id"]


@pytest.mark.asyncio
async def test_probe_endpoint_returns_report(client: AsyncClient):
    token = await _login(client)
    project_id = await _project(client, token)
    document_id = await _upload(client, token, project_id)

    resp = await client.post("/api/v1/probe", headers={"Authorization": f"Bearer {token}"},
                             json={"document_id": document_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["document_id"] == document_id
    assert "pages" in body and "suggestion" in body


@pytest.mark.asyncio
async def test_probe_endpoint_404_for_unknown_document(client: AsyncClient):
    token = await _login(client)
    resp = await client.post("/api/v1/probe", headers={"Authorization": f"Bearer {token}"},
                             json={"document_id": str(uuid.uuid4())})
    assert resp.status_code == 404
