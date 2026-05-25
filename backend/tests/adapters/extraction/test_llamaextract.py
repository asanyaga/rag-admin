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
        source_doc_repo.get.return_value = source_doc
        storage_service.get.return_value = b"pdf bytes"

        result = await adapter._get_file_bytes(SOURCE_DOC_ID)

        source_doc_repo.get.assert_called_once_with(UUID(SOURCE_DOC_ID))
        storage_service.get.assert_called_once_with("uploads/test.pdf")
        assert result == b"pdf bytes"

    async def test_raises_when_source_doc_not_found(
        self, adapter, source_doc_repo
    ):
        source_doc_repo.get.return_value = None

        with pytest.raises(ValueError, match="SourceDocument .* not found"):
            await adapter._get_file_bytes(SOURCE_DOC_ID)
