"""Tests for ExtractionResultRepository provenance fields."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.repositories.extraction_result_repository import ExtractionResultRepository
from app.models.extraction_result import ExtractionResult, ExtractionResultStatus


def _make_mock_result(**kwargs):
    result = MagicMock(spec=ExtractionResult)
    result.id = kwargs.get("id", uuid4())
    result.structured_data = kwargs.get("structured_data", None)
    result.citations = kwargs.get("citations", None)
    result.provider_response_raw = kwargs.get("provider_response_raw", None)
    result.extraction_metadata = kwargs.get("extraction_metadata", None)
    result.status = kwargs.get("status", ExtractionResultStatus.pending)
    result.source_parse_run_id = kwargs.get("source_parse_run_id", None)
    return result


class TestCreateAcceptsSourceParseRunId:
    @pytest.mark.asyncio
    async def test_create_passes_source_parse_run_id_to_orm(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        repo = ExtractionResultRepository(session)
        doc_id = uuid4()
        schema_id = uuid4()
        user_id = uuid4()
        parse_run_id = uuid4()

        added_instance = None
        def capture_add(obj):
            nonlocal added_instance
            added_instance = obj
        session.add.side_effect = capture_add

        await repo.create(
            document_id=doc_id,
            source_parse_run_id=parse_run_id,
            extraction_schema_id=schema_id,
            schema_definition_snapshot={"type": "object"},
            extraction_method="ollama",
            created_by=user_id,
        )
        assert added_instance is not None
        assert added_instance.source_parse_run_id == parse_run_id

    @pytest.mark.asyncio
    async def test_create_without_source_parse_run_id_defaults_none(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        repo = ExtractionResultRepository(session)
        added_instance = None
        def capture_add(obj):
            nonlocal added_instance
            added_instance = obj
        session.add.side_effect = capture_add

        await repo.create(
            document_id=uuid4(),
            extraction_schema_id=uuid4(),
            schema_definition_snapshot={},
            extraction_method="ollama",
            created_by=uuid4(),
        )
        assert added_instance.source_parse_run_id is None


class TestUpdateResultAcceptsProvenanceFields:
    @pytest.mark.asyncio
    async def test_update_result_sets_citations(self):
        mock_result = _make_mock_result()
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        repo = ExtractionResultRepository(session)
        repo.get_by_id = AsyncMock(return_value=mock_result)

        citations_data = [{"field_path": "total", "page_index": 1, "block_ids": None, "text_spans": None}]
        await repo.update_result(
            result_id=mock_result.id,
            structured_data={"total": 1000},
            citations=citations_data,
        )
        assert mock_result.citations == citations_data

    @pytest.mark.asyncio
    async def test_update_result_sets_provider_response_raw(self):
        mock_result = _make_mock_result()
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        repo = ExtractionResultRepository(session)
        repo.get_by_id = AsyncMock(return_value=mock_result)

        raw = {"data": {"total": 1000}, "_meta": {"model": "llama"}}
        await repo.update_result(
            result_id=mock_result.id,
            structured_data={"total": 1000},
            provider_response_raw=raw,
        )
        assert mock_result.provider_response_raw == raw

    @pytest.mark.asyncio
    async def test_update_result_omitting_provenance_leaves_none(self):
        mock_result = _make_mock_result()
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        repo = ExtractionResultRepository(session)
        repo.get_by_id = AsyncMock(return_value=mock_result)

        await repo.update_result(result_id=mock_result.id, structured_data={"x": 1})
        assert mock_result.citations is None
        assert mock_result.provider_response_raw is None


class TestUpdateFailed:
    @pytest.mark.asyncio
    async def test_sets_status_failed_and_message(self):
        mock_result = _make_mock_result()
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        repo = ExtractionResultRepository(session)
        repo.get_by_id = AsyncMock(return_value=mock_result)

        await repo.update_failed(mock_result.id, "something went wrong")

        assert mock_result.status == ExtractionResultStatus.failed
        assert mock_result.status_message == "something went wrong"

    @pytest.mark.asyncio
    async def test_stores_extraction_metadata_when_provided(self):
        mock_result = _make_mock_result()
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        repo = ExtractionResultRepository(session)
        repo.get_by_id = AsyncMock(return_value=mock_result)

        meta = {"model": "gpt-4o", "provider": "openai", "latency_ms": 500}
        await repo.update_failed(mock_result.id, "parse failed", extraction_metadata=meta)

        assert mock_result.extraction_metadata == meta

    @pytest.mark.asyncio
    async def test_stores_provider_response_raw_when_provided(self):
        mock_result = _make_mock_result()
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        repo = ExtractionResultRepository(session)
        repo.get_by_id = AsyncMock(return_value=mock_result)

        raw = {"raw_content": "not json content here"}
        await repo.update_failed(mock_result.id, "parse failed", provider_response_raw=raw)

        assert mock_result.provider_response_raw == raw

    @pytest.mark.asyncio
    async def test_does_not_overwrite_existing_metadata_when_not_passed(self):
        mock_result = _make_mock_result(extraction_metadata={"prior": "value"})
        session = AsyncMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        repo = ExtractionResultRepository(session)
        repo.get_by_id = AsyncMock(return_value=mock_result)

        await repo.update_failed(mock_result.id, "oops")

        assert mock_result.extraction_metadata == {"prior": "value"}

    @pytest.mark.asyncio
    async def test_returns_none_when_result_not_found(self):
        session = AsyncMock()
        repo = ExtractionResultRepository(session)
        repo.get_by_id = AsyncMock(return_value=None)

        result = await repo.update_failed(uuid4(), "oops")

        assert result is None


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_returns_true_when_found(self):
        mock_result = _make_mock_result()
        session = AsyncMock()
        session.delete = AsyncMock()
        session.commit = AsyncMock()
        repo = ExtractionResultRepository(session)
        repo.get_by_id = AsyncMock(return_value=mock_result)

        result = await repo.delete(mock_result.id)

        assert result is True
        session.delete.assert_called_once_with(mock_result)
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self):
        session = AsyncMock()
        repo = ExtractionResultRepository(session)
        repo.get_by_id = AsyncMock(return_value=None)

        result = await repo.delete(uuid4())

        assert result is False
        session.delete.assert_not_called()
