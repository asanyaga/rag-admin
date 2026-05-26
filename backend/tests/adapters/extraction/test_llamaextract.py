"""Unit tests for LlamaExtractAdapter."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from app.adapters.extraction.llamaextract import LlamaExtractAdapter


SOURCE_DOC_ID = "12345678-1234-5678-1234-567812345678"
PARSE_RUN_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture
def source_doc_repo():
    return AsyncMock()


@pytest.fixture
def storage_service():
    return AsyncMock()


@pytest.fixture
def adapter(source_doc_repo, storage_service):
    a = LlamaExtractAdapter(
        api_key="test-key",
        source_document_repo=source_doc_repo,
        storage_service=storage_service,
    )
    a._client = AsyncMock()  # replace real HTTP client
    return a


@pytest.fixture
def parsed_doc():
    doc = MagicMock()
    doc.source_document_id = SOURCE_DOC_ID
    doc.parse_run_id = PARSE_RUN_ID
    return doc


class TestGetFileBytes:
    async def test_fetches_bytes_from_storage(
        self, adapter, source_doc_repo, storage_service
    ):
        source_doc = MagicMock()
        source_doc.storage_uri = "uploads/test.pdf"
        source_doc.filename = "test.pdf"
        source_doc.mime_type = "application/pdf"
        source_doc_repo.get.return_value = source_doc
        storage_service.get.return_value = b"pdf bytes"

        file_bytes, filename, mime_type = await adapter._get_file_bytes(SOURCE_DOC_ID)

        source_doc_repo.get.assert_called_once_with(UUID(SOURCE_DOC_ID))
        storage_service.get.assert_called_once_with("uploads/test.pdf")
        assert file_bytes == b"pdf bytes"
        assert filename == "test.pdf"
        assert mime_type == "application/pdf"

    async def test_raises_when_source_doc_not_found(
        self, adapter, source_doc_repo
    ):
        source_doc_repo.get.return_value = None

        with pytest.raises(ValueError, match="SourceDocument .* not found"):
            await adapter._get_file_bytes(SOURCE_DOC_ID)

    async def test_image_formats_pass_through(
        self, adapter, source_doc_repo, storage_service
    ):
        """JPEG/PNG are supported by LlamaExtract — they should not be blocked."""
        source_doc = MagicMock()
        source_doc.storage_uri = "uploads/photo.jpg"
        source_doc.filename = "photo.jpg"
        source_doc.mime_type = "image/jpeg"
        source_doc_repo.get.return_value = source_doc
        storage_service.get.return_value = b"jpeg bytes"

        file_bytes, filename, mime_type = await adapter._get_file_bytes(SOURCE_DOC_ID)

        assert file_bytes == b"jpeg bytes"
        assert filename == "photo.jpg"
        assert mime_type == "image/jpeg"

    async def test_none_mime_type_falls_back_to_octet_stream(
        self, adapter, source_doc_repo, storage_service
    ):
        source_doc = MagicMock()
        source_doc.storage_uri = "uploads/doc"
        source_doc.filename = None
        source_doc.mime_type = None
        source_doc_repo.get.return_value = source_doc
        storage_service.get.return_value = b"bytes"

        file_bytes, filename, mime_type = await adapter._get_file_bytes(SOURCE_DOC_ID)

        assert file_bytes == b"bytes"
        assert filename == "document"
        assert mime_type == "application/octet-stream"


class TestExtractOutputMapping:
    async def _setup_mocks(self, adapter, source_doc_repo, storage_service, file_id="file-abc"):
        source_doc = MagicMock()
        source_doc.storage_uri = "uploads/doc.pdf"
        source_doc.filename = "doc.pdf"
        source_doc.mime_type = "application/pdf"
        source_doc_repo.get.return_value = source_doc
        storage_service.get.return_value = b"bytes"
        file_obj = MagicMock()
        file_obj.id = file_id
        adapter._client.files.create = AsyncMock(return_value=file_obj)
        adapter._client.files.delete = AsyncMock()

    async def test_structured_data_from_result(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)
        result_obj = MagicMock()
        result_obj.data = {"name": "Alice", "age": 30}
        result_obj.model_dump.return_value = {"data": {"name": "Alice"}, "run_id": "r1"}
        adapter._client.extraction.extract = AsyncMock(return_value=result_obj)

        output = await adapter.extract(parsed_doc, {"type": "object"}, {})

        assert output.structured_data == {"name": "Alice", "age": 30}
        assert output.source_parse_run_id == UUID(PARSE_RUN_ID)
        assert output.citations is None
        assert output.provider_response_raw == {"data": {"name": "Alice"}, "run_id": "r1"}
        assert output.extraction_metadata["file_id"] == "file-abc"
        assert "latency_ms" in output.extraction_metadata

    async def test_structured_data_defaults_to_empty_dict_when_none(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)
        result_obj = MagicMock()
        result_obj.data = None
        result_obj.model_dump.return_value = {"data": None}
        adapter._client.extraction.extract = AsyncMock(return_value=result_obj)

        output = await adapter.extract(parsed_doc, {"type": "object"}, {})

        assert output.structured_data == {}

    async def test_file_upload_uses_correct_purpose(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)
        result_obj = MagicMock()
        result_obj.data = {}
        result_obj.model_dump.return_value = {}
        adapter._client.extraction.extract = AsyncMock(return_value=result_obj)
        adapter._client.files.delete = AsyncMock()

        await adapter.extract(parsed_doc, {"type": "object"}, {})

        call_kwargs = adapter._client.files.create.call_args.kwargs
        assert call_kwargs["purpose"] == "extract"
        # filename and MIME type come from the source document, not hardcoded
        assert call_kwargs["file"] == ("doc.pdf", b"bytes", "application/pdf")


class TestExtractConfigPassthrough:
    async def _setup_mocks(self, adapter, source_doc_repo, storage_service):
        source_doc = MagicMock()
        source_doc.storage_uri = "uploads/doc.pdf"
        source_doc.filename = "doc.pdf"
        source_doc.mime_type = "application/pdf"
        source_doc_repo.get.return_value = source_doc
        storage_service.get.return_value = b"bytes"
        file_obj = MagicMock()
        file_obj.id = "file-1"
        adapter._client.files.create = AsyncMock(return_value=file_obj)
        adapter._client.files.delete = AsyncMock()
        result_obj = MagicMock()
        result_obj.data = {}
        result_obj.model_dump.return_value = {}
        adapter._client.extraction.extract = AsyncMock(return_value=result_obj)

    async def test_default_mode_and_target(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)

        await adapter.extract(parsed_doc, {"type": "object"}, {})

        cfg = adapter._client.extraction.extract.call_args.kwargs["config"]
        assert cfg["extraction_mode"] == "MULTIMODAL"
        assert cfg["extraction_target"] == "PER_DOC"

    async def test_optional_flags_absent_when_not_in_config(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)

        await adapter.extract(parsed_doc, {"type": "object"}, {})

        cfg = adapter._client.extraction.extract.call_args.kwargs["config"]
        assert "cite_sources" not in cfg
        assert "use_reasoning" not in cfg
        assert "confidence_scores" not in cfg
        assert "page_range" not in cfg
        assert "prompt_override" not in cfg

    async def test_system_prompt_maps_to_prompt_override(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)

        await adapter.extract(
            parsed_doc,
            {"type": "object"},
            {"system_prompt": "Extract only financial data."},
        )

        cfg = adapter._client.extraction.extract.call_args.kwargs["config"]
        assert cfg["prompt_override"] == "Extract only financial data."
        assert "system_prompt" not in cfg

    async def test_all_optional_flags_forwarded(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)

        await adapter.extract(
            parsed_doc,
            {"type": "object"},
            {
                "cite_sources": True,
                "use_reasoning": True,
                "confidence_scores": False,
                "page_range": "1-3",
                "extraction_mode": "FAST",
                "extraction_target": "PER_PAGE",
            },
        )

        cfg = adapter._client.extraction.extract.call_args.kwargs["config"]
        assert cfg["cite_sources"] is True
        assert cfg["use_reasoning"] is True
        assert cfg["confidence_scores"] is False
        assert cfg["page_range"] == "1-3"
        assert cfg["extraction_mode"] == "FAST"
        assert cfg["extraction_target"] == "PER_PAGE"

    async def test_schema_passed_as_data_schema(
        self, adapter, source_doc_repo, storage_service, parsed_doc
    ):
        await self._setup_mocks(adapter, source_doc_repo, storage_service)
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}

        await adapter.extract(parsed_doc, schema, {})

        call_kwargs = adapter._client.extraction.extract.call_args.kwargs
        assert call_kwargs["data_schema"] == schema
