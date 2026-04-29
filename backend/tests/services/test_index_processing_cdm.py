import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models import IndexStatus, IndexDocumentStatus
from app.schemas.index import IndexConfig
from app.services.index_processing_service import IndexProcessingService
from app.services.exceptions import ValidationError


def _make_mock_index(source_representation="raw_text"):
    config = IndexConfig(
        source_representation=source_representation,
        chunking_strategy="recursive_character",
        parser="llamaparse" if source_representation != "raw_text" else None,
        parse_config_hash="abc123" if source_representation != "raw_text" else None,
    )
    index = MagicMock()
    index.id = uuid4()
    index.config = config.model_dump()
    index.status = IndexStatus.created
    return index


def _make_mock_index_doc(parse_run_id=None):
    doc = MagicMock()
    doc.document_id = uuid4()
    doc.parse_run_id = parse_run_id
    doc.processing_status = IndexDocumentStatus.pending
    doc.document = MagicMock()
    doc.document.id = doc.document_id
    doc.document.title = "Test Doc"
    doc.document.extracted_text = "raw extracted text"
    doc.document.source_metadata = {"filename": "test.pdf"}
    doc.document.processing_metadata = {}
    return doc


@pytest.mark.asyncio
async def test_start_processing_raises_when_cdm_doc_has_no_parse_run():
    index = _make_mock_index(source_representation="full_text")
    index_doc = _make_mock_index_doc(parse_run_id=None)  # no parse run set
    index.index_documents = [index_doc]

    index_repo = AsyncMock()
    index_repo.get_by_id_with_documents = AsyncMock(return_value=index)

    provider_key_repo = AsyncMock()
    provider_key_repo.get_for_provider = AsyncMock(return_value=MagicMock())

    service = IndexProcessingService(
        session=AsyncMock(),
        index_repo=index_repo,
        chunk_repo=AsyncMock(),
        provider_key_repo=provider_key_repo,
    )

    with pytest.raises(ValidationError, match="no parse run set"):
        await service.start_processing(index.id, uuid4(), uuid4())


@pytest.mark.asyncio
async def test_process_index_uses_full_text_from_parsed_document():
    index = _make_mock_index(source_representation="full_text")
    parse_run_id = uuid4()
    index_doc = _make_mock_index_doc(parse_run_id=parse_run_id)
    index.index_documents = [index_doc]
    index.version = 1

    parsed_doc = MagicMock()
    parsed_doc.full_text = "clean parsed text from CDM"

    index_repo = AsyncMock()
    index_repo.get_by_id_with_documents = AsyncMock(return_value=index)
    index_repo.get_pending_documents = AsyncMock(return_value=[index_doc])
    index_repo.update_document_status = AsyncMock()
    index_repo.update_status = AsyncMock()
    index_repo.update_stats = AsyncMock()
    index_repo.increment_version = AsyncMock()
    index_repo.write_index_event = AsyncMock()

    parsed_doc_repo = AsyncMock()
    parsed_doc_repo.get_by_run = AsyncMock(return_value=parsed_doc)

    chunk_repo = AsyncMock()
    chunk_repo.create_batch = AsyncMock()
    chunk_repo.get_stats = AsyncMock(return_value={
        "total_chunks": 2, "total_documents": 1,
        "avg_chunk_size_chars": 100.0, "avg_chunk_size_tokens": 20.0,
        "min_chunk_size_chars": 80, "max_chunk_size_chars": 120,
        "total_tokens": 40,
    })

    mock_embedding_provider = AsyncMock()
    mock_embedding_provider.embed_texts = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])
    mock_embedding_provider.get_dimensions = MagicMock(return_value=2)

    with patch("app.services.index_processing_service.EmbeddingProviderRegistry") as mock_registry, \
         patch("app.services.index_processing_service.ParsedDocumentRepository", return_value=parsed_doc_repo), \
         patch("app.services.index_processing_service.ProviderKeyService") as mock_pks:
        mock_registry.get_provider.return_value = mock_embedding_provider
        mock_pks.return_value.get_key_for_provider = AsyncMock(return_value="test-key")

        service = IndexProcessingService(
            session=AsyncMock(),
            index_repo=index_repo,
            chunk_repo=chunk_repo,
            provider_key_repo=AsyncMock(),
        )

        await service.process_index(index.id, uuid4(), uuid4())

    parsed_doc_repo.get_by_run.assert_called_once_with(parse_run_id)

    call_args = chunk_repo.create_batch.call_args[0][0]
    assert call_args[0]["source_type"] == "full_text"
    assert call_args[0]["parse_run_id"] == str(parse_run_id)
    assert call_args[0]["index_version"] == 2  # version + 1

    index_repo.increment_version.assert_called_once_with(index.id)
    index_repo.write_index_event.assert_called_once()


@pytest.mark.asyncio
async def test_process_index_raises_not_implemented_for_unsupported_representation():
    index = _make_mock_index(source_representation="raw_text")
    index.config = {
        "source_representation": "block",
        "chunking_strategy": "block",
        "parser": "llamaparse",
        "parse_config_hash": "abc123",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
    }
    parse_run_id = uuid4()
    index_doc = _make_mock_index_doc(parse_run_id=parse_run_id)
    index.index_documents = [index_doc]
    index.version = 1

    index_repo = AsyncMock()
    index_repo.get_by_id_with_documents = AsyncMock(return_value=index)
    index_repo.get_pending_documents = AsyncMock(return_value=[index_doc])
    index_repo.update_document_status = AsyncMock()
    index_repo.update_status = AsyncMock()
    index_repo.update_stats = AsyncMock()
    index_repo.increment_version = AsyncMock()
    index_repo.write_index_event = AsyncMock()

    chunk_repo = AsyncMock()
    chunk_repo.get_stats = AsyncMock(return_value={
        "total_chunks": 0, "total_documents": 1,
        "avg_chunk_size_chars": 0.0, "avg_chunk_size_tokens": 0.0,
        "min_chunk_size_chars": 0, "max_chunk_size_chars": 0,
        "total_tokens": 0,
    })

    mock_embedding_provider = AsyncMock()
    mock_embedding_provider.embed_texts = AsyncMock(return_value=[])
    mock_embedding_provider.get_dimensions = MagicMock(return_value=1536)

    with patch("app.services.index_processing_service.EmbeddingProviderRegistry") as mock_registry, \
         patch("app.services.index_processing_service.ProviderKeyService") as mock_pks:
        mock_registry.get_provider.return_value = mock_embedding_provider
        mock_pks.return_value.get_key_for_provider = AsyncMock(return_value="test-key")

        service = IndexProcessingService(
            session=AsyncMock(),
            index_repo=index_repo,
            chunk_repo=chunk_repo,
            provider_key_repo=AsyncMock(),
        )

        await service.process_index(index.id, uuid4(), uuid4())

    failed_call = [
        c for c in index_repo.update_document_status.call_args_list
        if c.args[2] == IndexDocumentStatus.failed
    ]
    assert len(failed_call) == 1
    assert "not yet supported" in failed_call[0].kwargs.get("error_message", "") or \
           "not yet supported" in str(failed_call[0].args)


@pytest.mark.asyncio
async def test_process_index_raw_text_still_works():
    """Regression: raw_text mode unchanged from before this slice."""
    index = _make_mock_index(source_representation="raw_text")
    index_doc = _make_mock_index_doc(parse_run_id=None)
    index.index_documents = [index_doc]
    index.version = 1

    index_repo = AsyncMock()
    index_repo.get_by_id_with_documents = AsyncMock(return_value=index)
    index_repo.get_pending_documents = AsyncMock(return_value=[index_doc])
    index_repo.update_document_status = AsyncMock()
    index_repo.update_status = AsyncMock()
    index_repo.update_stats = AsyncMock()
    index_repo.increment_version = AsyncMock()
    index_repo.write_index_event = AsyncMock()

    chunk_repo = AsyncMock()
    chunk_repo.create_batch = AsyncMock()
    chunk_repo.get_stats = AsyncMock(return_value={
        "total_chunks": 1, "total_documents": 1,
        "avg_chunk_size_chars": 100.0, "avg_chunk_size_tokens": 20.0,
        "min_chunk_size_chars": 100, "max_chunk_size_chars": 100,
        "total_tokens": 20,
    })

    mock_embedding_provider = AsyncMock()
    mock_embedding_provider.embed_texts = AsyncMock(return_value=[[0.1, 0.2]])
    mock_embedding_provider.get_dimensions = MagicMock(return_value=2)

    with patch("app.services.index_processing_service.EmbeddingProviderRegistry") as mock_registry, \
         patch("app.services.index_processing_service.ProviderKeyService") as mock_pks:
        mock_registry.get_provider.return_value = mock_embedding_provider
        mock_pks.return_value.get_key_for_provider = AsyncMock(return_value="test-key")

        service = IndexProcessingService(
            session=AsyncMock(),
            index_repo=index_repo,
            chunk_repo=chunk_repo,
            provider_key_repo=AsyncMock(),
        )
        await service.process_index(index.id, uuid4(), uuid4())

    call_args = chunk_repo.create_batch.call_args[0][0]
    assert call_args[0]["source_type"] == "raw_text"
    assert call_args[0]["parse_run_id"] is None
    index_repo.increment_version.assert_called_once()


from app.services.index_service import IndexService
from app.schemas.index import AddDocumentsRequest


@pytest.mark.asyncio
async def test_add_documents_passes_parse_run_ids_to_repo():
    doc_id = uuid4()
    run_id = uuid4()

    _index_id = uuid4()
    _project_id = uuid4()
    _mock_index = MagicMock()
    _mock_index.id = _index_id
    _mock_index.project_id = _project_id
    _mock_index.status = IndexStatus.created
    _mock_index.index_documents = []
    _mock_index.name = "test"
    _mock_index.description = None
    _mock_index.config = {
        "chunking_strategy": "recursive_character",
        "source_representation": "raw_text",
        "chunk_size": 512,
        "chunk_overlap": 50,
        "chunk_unit": "characters",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": None,
    }
    _mock_index.stats = None
    _mock_index.error_message = None
    _mock_index.created_by = uuid4()
    _mock_index.created_at = MagicMock()
    _mock_index.updated_at = MagicMock()
    _mock_index.version = 1
    _mock_index.config_dirty = False

    index_repo = AsyncMock()
    index_repo.get_by_id = AsyncMock(return_value=_mock_index)
    index_repo.add_documents = AsyncMock(return_value=[])
    index_repo.get_document_ids = AsyncMock(return_value=[doc_id])
    index_repo.count_documents = AsyncMock(return_value=1)
    index_repo.count_chunks = AsyncMock(return_value=0)

    service = IndexService(index_repo=index_repo, chunk_repo=AsyncMock())
    request = AddDocumentsRequest(
        document_ids=[doc_id],
        parse_run_ids={doc_id: run_id},
    )

    await service.add_documents(_index_id, _project_id, request)

    index_repo.add_documents.assert_called_once()
    call_kwargs = index_repo.add_documents.call_args
    assert call_kwargs.kwargs.get("parse_run_ids") == {doc_id: run_id} or \
           (len(call_kwargs.args) > 2 and call_kwargs.args[2] == {doc_id: run_id})


def test_index_response_includes_version_and_config_dirty():
    index = MagicMock()
    index.id = uuid4()
    index.project_id = uuid4()
    index.name = "my-index"
    index.description = None
    index.config = {
        "chunking_strategy": "recursive_character",
        "source_representation": "raw_text",
        "chunk_size": 512,
        "chunk_overlap": 50,
        "chunk_unit": "characters",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": None,
    }
    index.stats = None
    index.status = IndexStatus.created
    index.error_message = None
    index.created_by = uuid4()
    index.created_at = MagicMock()
    index.updated_at = MagicMock()
    index.version = 3
    index.config_dirty = True

    service = IndexService(index_repo=MagicMock(), chunk_repo=MagicMock())
    response = service._to_response(index)

    assert response.version == 3
    assert response.config_dirty is True
