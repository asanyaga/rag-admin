"""Tests for ExtractionService CDM-based flow."""
import dataclasses
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4, UUID

from app.cdm.models import ParsedDocument, Page, Block, BlockRole
from app.models.extraction_result import ExtractionResultStatus
from app.ports.data_extraction import DataExtractor, ExtractionOutput, FieldCitation
from app.services.extraction_service import ExtractionService, process_extraction


def _make_cdm_doc(parse_run_id: str, source_document_id: str) -> ParsedDocument:
    return ParsedDocument(
        id="doc-1",
        source_document_id=source_document_id,
        parse_run_id=parse_run_id,
        page_count=1,
        pages=[Page(index=0, block_ids=["b1"])],
        blocks=[Block(id="b1", role=BlockRole.PARAGRAPH, native_type="p", text="hello", page_index=0)],
        full_markdown="hello",
    )


def _make_extraction_output(parse_run_id: UUID) -> ExtractionOutput:
    return ExtractionOutput(
        structured_data={"total": 1000},
        source_parse_run_id=parse_run_id,
        citations=[FieldCitation(field_path="total", page_index=0, block_ids=None, text_spans=None)],
        provider_response_raw=None,
        extraction_metadata={"latency_ms": 100},
    )


class StubExtractor(DataExtractor):
    def __init__(self, output: ExtractionOutput):
        self._output = output
    @property
    def extractor_type(self):
        return "stub"
    async def extract(self, parsed_document, schema, config=None):
        return self._output


def _make_service(
    *,
    schema_repo=None,
    result_repo=None,
    parsed_document_repo=None,
    document_repo=None,
) -> ExtractionService:
    return ExtractionService(
        schema_repo=schema_repo or AsyncMock(),
        result_repo=result_repo or AsyncMock(),
        parsed_document_repo=parsed_document_repo or AsyncMock(),
        document_repo=document_repo or AsyncMock(),
    )


class TestRunExtraction:
    @pytest.mark.asyncio
    async def test_run_extraction_uses_project_document_id(self):
        """document_id on the result must come from documents.id, not source_documents.id."""
        parse_run_id = uuid4()
        source_doc_id = uuid4()
        project_id = uuid4()
        schema_id = uuid4()
        user_id = uuid4()
        document_id = uuid4()  # the project-scoped documents.id — different from source_doc_id

        mock_orm_parsed_doc = MagicMock()
        mock_orm_parsed_doc.source_document_id = source_doc_id
        mock_parsed_doc_repo = AsyncMock()
        mock_parsed_doc_repo.get_by_run.return_value = mock_orm_parsed_doc

        mock_schema = MagicMock()
        mock_schema.project_id = project_id
        mock_schema.schema_definition = {"type": "object"}
        mock_schema.extraction_target = "PER_DOC"
        mock_schema_repo = AsyncMock()
        mock_schema_repo.get_by_id.return_value = mock_schema

        mock_document = MagicMock()
        mock_document.id = document_id
        mock_document_repo = AsyncMock()
        mock_document_repo.get_by_source_document_for_project.return_value = mock_document

        mock_result = MagicMock()
        mock_result.id = uuid4()
        mock_result.document_id = document_id
        mock_result.extraction_schema_id = schema_id
        mock_result.schema_definition_snapshot = {"type": "object"}
        mock_result.extraction_method = "stub"
        mock_result.config = {}
        mock_result.structured_data = None
        mock_result.citations = None
        mock_result.provider_response_raw = None
        mock_result.extraction_metadata = None
        mock_result.status = "pending"
        mock_result.status_message = None
        mock_result.started_at = None
        mock_result.source_parse_run_id = parse_run_id
        mock_result.created_by = user_id
        mock_result.created_at = datetime(2024, 1, 1)
        mock_result.updated_at = datetime(2024, 1, 1)
        mock_result_repo = AsyncMock()
        mock_result_repo.create.return_value = mock_result

        service = _make_service(
            schema_repo=mock_schema_repo,
            result_repo=mock_result_repo,
            parsed_document_repo=mock_parsed_doc_repo,
            document_repo=mock_document_repo,
        )

        await service.run_extraction(
            parse_run_id=parse_run_id,
            extraction_schema_id=schema_id,
            extraction_method="stub",
            user_id=user_id,
        )

        mock_parsed_doc_repo.get_by_run.assert_called_once_with(parse_run_id)
        mock_document_repo.get_by_source_document_for_project.assert_called_once_with(
            source_document_id=source_doc_id,
            project_id=project_id,
        )
        call_kwargs = mock_result_repo.create.call_args.kwargs
        assert call_kwargs["source_parse_run_id"] == parse_run_id
        # Must be documents.id, not source_documents.id
        assert call_kwargs["document_id"] == document_id
        assert call_kwargs["document_id"] != source_doc_id

    @pytest.mark.asyncio
    async def test_run_extraction_raises_not_found_when_parse_run_missing(self):
        from app.services.exceptions import NotFoundError
        mock_parsed_doc_repo = AsyncMock()
        mock_parsed_doc_repo.get_by_run.return_value = None

        service = _make_service(parsed_document_repo=mock_parsed_doc_repo)
        with pytest.raises(NotFoundError):
            await service.run_extraction(
                parse_run_id=uuid4(),
                extraction_schema_id=uuid4(),
                extraction_method="stub",
                user_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_run_extraction_raises_not_found_when_document_not_in_project(self):
        """If no document in the project wraps the source_document, raise NotFoundError."""
        from app.services.exceptions import NotFoundError

        mock_orm_parsed_doc = MagicMock()
        mock_orm_parsed_doc.source_document_id = uuid4()
        mock_parsed_doc_repo = AsyncMock()
        mock_parsed_doc_repo.get_by_run.return_value = mock_orm_parsed_doc

        mock_schema = MagicMock()
        mock_schema.project_id = uuid4()
        mock_schema.extraction_target = "PER_DOC"
        mock_schema_repo = AsyncMock()
        mock_schema_repo.get_by_id.return_value = mock_schema

        mock_document_repo = AsyncMock()
        mock_document_repo.get_by_source_document_for_project.return_value = None

        service = _make_service(
            schema_repo=mock_schema_repo,
            parsed_document_repo=mock_parsed_doc_repo,
            document_repo=mock_document_repo,
        )
        with pytest.raises(NotFoundError):
            await service.run_extraction(
                parse_run_id=uuid4(),
                extraction_schema_id=uuid4(),
                extraction_method="stub",
                user_id=uuid4(),
            )


class TestProcessExtraction:
    @pytest.mark.asyncio
    async def test_passes_cdm_parsed_doc_to_extractor(self):
        parse_run_id = uuid4()
        result_id = uuid4()

        cdm_content = _make_cdm_doc(str(parse_run_id), str(uuid4())).model_dump()

        mock_extraction_result = MagicMock()
        mock_extraction_result.source_parse_run_id = parse_run_id
        mock_extraction_result.schema_definition_snapshot = {"type": "object"}
        mock_extraction_result.config = None

        mock_orm_parsed_doc = MagicMock()
        mock_orm_parsed_doc.content = cdm_content

        mock_result_repo = AsyncMock()
        mock_result_repo.set_started.return_value = None
        mock_result_repo.get_by_id.return_value = mock_extraction_result
        mock_result_repo.update_result.return_value = None

        mock_parsed_doc_repo = AsyncMock()
        mock_parsed_doc_repo.get_by_run.return_value = mock_orm_parsed_doc

        output = _make_extraction_output(parse_run_id)
        extractor = StubExtractor(output)
        received_docs = []
        original_extract = extractor.extract
        async def capture_extract(parsed_document, schema, config=None):
            received_docs.append(parsed_document)
            return await original_extract(parsed_document, schema, config)
        extractor.extract = capture_extract

        await process_extraction(
            extraction_result_id=result_id,
            result_repo=mock_result_repo,
            parsed_document_repo=mock_parsed_doc_repo,
            extractor=extractor,
        )

        assert len(received_docs) == 1
        assert received_docs[0].parse_run_id == str(parse_run_id)

    @pytest.mark.asyncio
    async def test_citations_persisted_on_success(self):
        parse_run_id = uuid4()
        result_id = uuid4()
        cdm_content = _make_cdm_doc(str(parse_run_id), str(uuid4())).model_dump()

        mock_extraction_result = MagicMock()
        mock_extraction_result.source_parse_run_id = parse_run_id
        mock_extraction_result.schema_definition_snapshot = {"type": "object"}
        mock_extraction_result.config = None

        mock_orm_parsed_doc = MagicMock()
        mock_orm_parsed_doc.content = cdm_content

        mock_result_repo = AsyncMock()
        mock_result_repo.set_started.return_value = None
        mock_result_repo.get_by_id.return_value = mock_extraction_result
        mock_result_repo.update_result.return_value = None

        mock_parsed_doc_repo = AsyncMock()
        mock_parsed_doc_repo.get_by_run.return_value = mock_orm_parsed_doc

        output = _make_extraction_output(parse_run_id)
        extractor = StubExtractor(output)

        await process_extraction(
            extraction_result_id=result_id,
            result_repo=mock_result_repo,
            parsed_document_repo=mock_parsed_doc_repo,
            extractor=extractor,
        )

        call_kwargs = mock_result_repo.update_result.call_args.kwargs
        assert call_kwargs["citations"] is not None
        assert call_kwargs["citations"][0]["field_path"] == "total"

    @pytest.mark.asyncio
    async def test_marks_failed_when_parse_run_not_found(self):
        result_id = uuid4()

        mock_extraction_result = MagicMock()
        mock_extraction_result.source_parse_run_id = uuid4()
        mock_extraction_result.schema_definition_snapshot = {}
        mock_extraction_result.config = None

        mock_result_repo = AsyncMock()
        mock_result_repo.set_started.return_value = None
        mock_result_repo.get_by_id.return_value = mock_extraction_result
        mock_result_repo.update_status.return_value = None

        mock_parsed_doc_repo = AsyncMock()
        mock_parsed_doc_repo.get_by_run.return_value = None

        await process_extraction(
            extraction_result_id=result_id,
            result_repo=mock_result_repo,
            parsed_document_repo=mock_parsed_doc_repo,
            extractor=MagicMock(),
        )

        mock_result_repo.update_status.assert_called_once_with(
            result_id, ExtractionResultStatus.failed, "ParsedDocument not found for parse_run_id"
        )
