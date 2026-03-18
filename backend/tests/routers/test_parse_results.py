"""Tests for parse results router."""
import pytest
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ── Helpers ──────────────────────────────────────────────────────────────

async def create_user_and_login(client: AsyncClient, test_db: AsyncSession) -> tuple[str, str]:
    """Create a user and return (user_id, auth_token)."""
    await client.post("/api/v1/auth/signup", json={
        "email": "test@example.com",
        "password": "TestPassword123!",
        "password_confirm": "TestPassword123!",
        "full_name": "Test User",
    })
    response = await client.post("/api/v1/auth/signin", json={
        "email": "test@example.com",
        "password": "TestPassword123!",
    })
    data = response.json()
    # Get user ID from the users/me endpoint
    me_resp = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    return me_resp.json()["id"], data["access_token"]


async def create_project(client: AsyncClient, token: str) -> str:
    """Create a project and return its ID."""
    response = await client.post(
        "/api/v1/projects",
        json={"name": "Test Project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def create_document(client: AsyncClient, token: str, project_id: str) -> str:
    """Create a document via the upload endpoint and return its ID."""
    import io
    files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 fake content"), "application/pdf")}
    data = {
        "project_id": project_id,
        "title": "Test Document",
    }
    response = await client.post(
        "/api/v1/documents",
        data=data,
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 202
    return response.json()["id"]


async def create_parse_result(
    test_db: AsyncSession,
    document_id: str,
    user_id: str,
    parser_type: str = "llamaparse",
) -> str:
    """Create a parse result directly in the database."""
    from app.models.parse_result import ParseResult, ParseResultStatus
    from uuid import UUID
    pr = ParseResult(
        id=uuid4(),
        document_id=UUID(document_id),
        parser_type=parser_type,
        created_by=UUID(user_id),
        status=ParseResultStatus.completed,
        raw_text="Extracted text from parser",
        fidelity="text",
        diagnostics={"char_count": 25, "non_empty": True},
    )
    test_db.add(pr)
    await test_db.commit()
    await test_db.refresh(pr)
    return str(pr.id)


# ── Tests ────────────────────────────────────────────────────────────────

class TestListParsers:

    async def test_list_parsers(self, client: AsyncClient, test_db: AsyncSession):
        _, token = await create_user_and_login(client, test_db)
        response = await client.get(
            "/api/v1/parsers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        parser_types = [p["parserType"] for p in data]
        assert "simple" in parser_types

    async def test_list_parsers_unauthorized(self, client: AsyncClient):
        response = await client.get("/api/v1/parsers")
        assert response.status_code == 401


class TestListParseResults:

    async def test_list_parse_results(self, client: AsyncClient, test_db: AsyncSession):
        user_id, token = await create_user_and_login(client, test_db)
        project_id = await create_project(client, token)
        document_id = await create_document(client, token, project_id)

        # Create a parse result
        pr_id = await create_parse_result(test_db, document_id, user_id)

        response = await client.get(
            f"/api/v1/documents/{document_id}/parse-results",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == pr_id

    async def test_list_parse_results_empty(self, client: AsyncClient, test_db: AsyncSession):
        _, token = await create_user_and_login(client, test_db)
        project_id = await create_project(client, token)
        document_id = await create_document(client, token, project_id)

        response = await client.get(
            f"/api/v1/documents/{document_id}/parse-results",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json() == []


class TestGetParseResult:

    async def test_get_parse_result(self, client: AsyncClient, test_db: AsyncSession):
        user_id, token = await create_user_and_login(client, test_db)
        project_id = await create_project(client, token)
        document_id = await create_document(client, token, project_id)
        pr_id = await create_parse_result(test_db, document_id, user_id)

        response = await client.get(
            f"/api/v1/parse-results/{pr_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == pr_id
        assert data["parserType"] == "llamaparse"
        assert data["rawText"] == "Extracted text from parser"
        assert data["diagnostics"]["char_count"] == 25

    async def test_get_parse_result_not_found(self, client: AsyncClient, test_db: AsyncSession):
        _, token = await create_user_and_login(client, test_db)

        response = await client.get(
            f"/api/v1/parse-results/{uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestReparse:

    async def test_reparse_simple_not_allowed(self, client: AsyncClient, test_db: AsyncSession):
        _, token = await create_user_and_login(client, test_db)
        project_id = await create_project(client, token)
        document_id = await create_document(client, token, project_id)

        response = await client.post(
            f"/api/v1/documents/{document_id}/parse",
            json={"parserType": "simple"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400


class TestUploadWithParser:

    async def test_upload_with_simple_parser(self, client: AsyncClient, test_db: AsyncSession):
        """Upload with simple parser should work as before."""
        import io
        _, token = await create_user_and_login(client, test_db)
        project_id = await create_project(client, token)

        files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 fake content"), "application/pdf")}
        data = {
            "project_id": project_id,
            "title": "Test Document",
            "parser_type": "simple",
        }
        response = await client.post(
            "/api/v1/documents",
            data=data,
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 202
        assert response.json()["status"] == "processing"

    async def test_upload_default_parser_is_simple(self, client: AsyncClient, test_db: AsyncSession):
        """Default parser type should be simple."""
        import io
        _, token = await create_user_and_login(client, test_db)
        project_id = await create_project(client, token)

        files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 fake content"), "application/pdf")}
        data = {
            "project_id": project_id,
            "title": "Test Document",
            # No parser_type specified
        }
        response = await client.post(
            "/api/v1/documents",
            data=data,
            files=files,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 202
