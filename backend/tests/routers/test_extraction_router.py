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


@pytest.mark.asyncio
async def test_run_extraction_folds_applied_filter_into_config(client: AsyncClient):
    """A category_filter stage is resolved and its summary folded into the run config."""
    summary = {
        "classificationRunId": str(uuid4()), "categories": ["fin"],
        "granularity": "page", "keptPages": 2, "keptBlocks": 0,
    }
    resolved_pre = [{"stage": "category_filter", "config": {"keepPages": [1, 2], "keepBlockIds": []}}]

    app.dependency_overrides[get_current_active_user] = _mock_user
    try:
        with patch("app.routers.extraction.resolve_api_key", new_callable=AsyncMock, return_value="key"), \
             patch("app.routers.extraction.create_adapter"), \
             patch("app.routers.extraction.get_extractor"), \
             patch("app.routers.extraction.process_extraction"), \
             patch("app.routers.extraction.resolve_category_filter_stages",
                   new_callable=AsyncMock, return_value=(resolved_pre, summary)) as mock_resolve, \
             patch("app.routers.extraction.ExtractionService.run_extraction",
                   new_callable=AsyncMock) as mock_run:
            mock_run.return_value = MagicMock(id=uuid4())
            # The mock return can't satisfy the response_model, but resolver + run_extraction
            # run before serialization — so we assert on those interactions, not the response.
            try:
                await client.post("/api/v1/extractions/run", json={
                    "parseRunId": str(uuid4()),
                    "extractionSchemaId": str(uuid4()),
                    "extractionMethod": "llm",
                    "preprocess": [{"stage": "category_filter", "config": {
                        "classificationRunId": summary["classificationRunId"],
                        "categories": ["fin"], "granularity": "page"}}],
                })
            except Exception:
                pass
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)

    assert mock_resolve.await_count == 1
    assert mock_run.await_args.kwargs["config"]["applied_filter"] == summary


@pytest.mark.asyncio
async def test_run_extraction_category_filter_error_returns_400(client: AsyncClient):
    """A resolver ValueError (e.g. empty match) surfaces as HTTP 400 before dispatch."""
    app.dependency_overrides[get_current_active_user] = _mock_user
    try:
        with patch("app.routers.extraction.resolve_api_key", new_callable=AsyncMock, return_value="key"), \
             patch("app.routers.extraction.create_adapter"), \
             patch("app.routers.extraction.get_extractor"), \
             patch("app.routers.extraction.process_extraction"), \
             patch("app.routers.extraction.resolve_category_filter_stages", new_callable=AsyncMock,
                   side_effect=ValueError("Selected categories matched no content in classification run X")):
            response = await client.post("/api/v1/extractions/run", json={
                "parseRunId": str(uuid4()),
                "extractionSchemaId": str(uuid4()),
                "extractionMethod": "llm",
                "preprocess": [{"stage": "category_filter", "config": {
                    "classificationRunId": str(uuid4()), "categories": ["fin"], "granularity": "page"}}],
            })
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "matched no content" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_llm_extraction_defaults(client: AsyncClient):
    """GET /extractors/llm/defaults returns the two hardcoded prompt constants."""
    from app.adapters.extraction.llm import (
        DEFAULT_EXTRACTION_SYSTEM_PROMPT,
        DEFAULT_USER_PROMPT_TEMPLATE,
    )
    from app.dependencies.auth import get_current_active_user

    app.dependency_overrides[get_current_active_user] = lambda: _mock_user()
    try:
        response = await client.get("/api/v1/extractors/llm/defaults")
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == 200
    data = response.json()
    assert data["systemPrompt"] == DEFAULT_EXTRACTION_SYSTEM_PROMPT
    assert data["userPromptTemplate"] == DEFAULT_USER_PROMPT_TEMPLATE


@pytest.mark.asyncio
async def test_delete_extraction_result_returns_204(client: AsyncClient):
    """DELETE /extraction-results/{id} returns 204 when the result exists."""
    from app.services.extraction_service import ExtractionService
    from app.services.exceptions import NotFoundError

    result_id = uuid4()
    app.dependency_overrides[get_current_active_user] = _mock_user

    try:
        with patch.object(ExtractionService, "delete_result", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = None
            response = await client.delete(
                f"/api/v1/extraction-results/{result_id}",
            )
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.asyncio
async def test_delete_extraction_result_returns_404_when_not_found(client: AsyncClient):
    """DELETE /extraction-results/{id} returns 404 when the result does not exist."""
    from app.services.extraction_service import ExtractionService
    from app.services.exceptions import NotFoundError

    result_id = uuid4()
    app.dependency_overrides[get_current_active_user] = _mock_user

    try:
        with patch.object(ExtractionService, "delete_result", new_callable=AsyncMock) as mock_delete:
            mock_delete.side_effect = NotFoundError("not found")
            response = await client.delete(
                f"/api/v1/extraction-results/{result_id}",
            )
    finally:
        app.dependency_overrides.pop(get_current_active_user, None)

    assert response.status_code == status.HTTP_404_NOT_FOUND
