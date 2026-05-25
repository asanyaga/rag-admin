"""Tests for extraction router — parse_run_id request contract."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from httpx import AsyncClient, ASGITransport
from fastapi import status

from app.main import app
from app.dependencies.auth import get_current_active_user
from app.database import get_db


def _mock_user():
    """Return a lightweight fake user for auth bypass."""
    user = MagicMock()
    user.id = uuid4()
    user.email = "test@example.com"
    user.is_active = True
    return user


@pytest.mark.asyncio
async def test_run_extraction_accepts_parse_run_id(client: AsyncClient):
    """POST /extractions/run must accept parseRunId not documentId."""
    parse_run_id = uuid4()
    schema_id = uuid4()

    with patch("app.routers.extraction.get_extractor") as mock_factory, \
         patch("app.routers.extraction.ExtractionService.run_extraction", new_callable=AsyncMock) as mock_run:

        mock_extractor = AsyncMock()
        mock_extractor.extractor_type = "stub"
        mock_factory.return_value = mock_extractor

        mock_result = AsyncMock()
        mock_result.id = uuid4()
        mock_result.document_id = uuid4()
        mock_result.source_parse_run_id = parse_run_id
        mock_result.extraction_schema_id = schema_id
        mock_result.schema_definition_snapshot = {}
        mock_result.extraction_method = "stub"
        mock_result.config = None
        mock_result.structured_data = None
        mock_result.citations = None
        mock_result.provider_response_raw = None
        mock_result.extraction_metadata = None
        from app.models.extraction_result import ExtractionResultStatus
        mock_result.status = ExtractionResultStatus.pending
        mock_result.status_message = None
        mock_result.started_at = None
        mock_run.return_value = mock_result

        response = await client.post(
            "/api/v1/extractions/run",
            json={
                "parseRunId": str(parse_run_id),
                "extractionSchemaId": str(schema_id),
                "extractionMethod": "stub",
            },
            headers={"Authorization": "Bearer test-token"},
        )

    # 401 is expected (no real auth) — the important check is NOT 422
    assert response.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY, \
        f"422 means parseRunId was rejected: {response.json()}"


@pytest.mark.asyncio
async def test_run_extraction_rejects_document_id(client: AsyncClient):
    """documentId is no longer accepted in the request body.

    Auth is bypassed so that pydantic body validation is the only gate.
    """
    # Override auth so body validation is the deciding factor
    app.dependency_overrides[get_current_active_user] = _mock_user

    try:
        response = await client.post(
            "/api/v1/extractions/run",
            json={
                "documentId": str(uuid4()),          # old field — parseRunId missing
                "extractionSchemaId": str(uuid4()),
                "extractionMethod": "stub",
            },
        )
    finally:
        # Restore to avoid leaking override into other tests
        app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, \
        f"Expected 422 (missing parseRunId), got {response.status_code}: {response.json()}"
