import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models import IndexStatus, IndexDocumentStatus
from app.schemas.index import IndexConfig
from app.services.exceptions import ValidationError
from app.services.index_processing_service import IndexProcessingService
from app.services.index_service import IndexService
from app.services.source_resolution_service import TextSource


def _make_mock_index(source_representation="full_text"):
    strategy = "markdown_heading" if source_representation == "full_markdown" else "recursive_character"
    config = IndexConfig(
        source_representation=source_representation,
        chunking_strategy=strategy,
        parser="llamaparse",
        parse_config_hash="abc123",
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
         patch("app.services.source_resolution_service.ParsedDocumentRepository", return_value=parsed_doc_repo), \
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
    """block source_representation: seam resolves blocks but dispatcher raises NotImplementedError."""
    index = _make_mock_index()  # config overridden immediately below
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

    parsed_doc = MagicMock()
    parsed_doc.content = {"blocks": [{"type": "text", "content": "hello"}]}

    parsed_doc_repo = AsyncMock()
    parsed_doc_repo.get_by_run = AsyncMock(return_value=parsed_doc)

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
         patch("app.services.source_resolution_service.ParsedDocumentRepository", return_value=parsed_doc_repo), \
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
    # ChunkingDispatcher raises NotImplementedError for block-based chunking
    assert "not yet implemented" in failed_call[0].kwargs.get("error_message", "") or \
           "not yet implemented" in str(failed_call[0].args)


@pytest.mark.asyncio
async def test_process_index_full_markdown():
    """full_markdown: chunks sourced from ParsedDocument.full_markdown,
    source_type = "full_markdown", heading_path present in chunk metadata."""
    index = _make_mock_index(source_representation="full_markdown")
    index.config = {
        "source_representation": "full_markdown",
        "chunking_strategy": "markdown_heading",
        "parser": "llamaparse",
        "parse_config_hash": "abc123",
        "split_heading_level": 2,
        "max_section_chars": 4000,
        "chunk_size": 512,
        "chunk_overlap": 50,
        "chunk_unit": "characters",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": None,
    }
    parse_run_id = uuid4()
    index_doc = _make_mock_index_doc(parse_run_id=parse_run_id)
    index.index_documents = [index_doc]
    index.version = 1

    parsed_doc = MagicMock()
    parsed_doc.full_markdown = "# Section\nSome markdown content here."

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
        "total_chunks": 1, "total_documents": 1,
        "avg_chunk_size_chars": 37.0, "avg_chunk_size_tokens": 8.0,
        "min_chunk_size_chars": 37, "max_chunk_size_chars": 37,
        "total_tokens": 8,
    })

    mock_embedding_provider = AsyncMock()
    mock_embedding_provider.embed_texts = AsyncMock(return_value=[[0.1, 0.2]])
    mock_embedding_provider.get_dimensions = MagicMock(return_value=2)

    with patch("app.services.index_processing_service.EmbeddingProviderRegistry") as mock_reg, \
         patch("app.services.source_resolution_service.ParsedDocumentRepository",
               return_value=parsed_doc_repo), \
         patch("app.services.index_processing_service.ProviderKeyService") as mock_pks:
        mock_reg.get_provider.return_value = mock_embedding_provider
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
    assert call_args[0]["source_type"] == "full_markdown"
    assert call_args[0]["parse_run_id"] == str(parse_run_id)
    assert "heading_path" in call_args[0]["chunk_metadata"]


@pytest.mark.asyncio
async def test_full_markdown_missing_raises():
    """ValueError when parse run has no full_markdown."""
    index = _make_mock_index(source_representation="full_markdown")
    index.config = {
        "source_representation": "full_markdown",
        "chunking_strategy": "markdown_heading",
        "parser": "llamaparse",
        "parse_config_hash": "abc123",
        "split_heading_level": 2,
        "max_section_chars": 4000,
        "chunk_size": 512,
        "chunk_overlap": 50,
        "chunk_unit": "characters",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": None,
    }
    parse_run_id = uuid4()
    index_doc = _make_mock_index_doc(parse_run_id=parse_run_id)
    index.index_documents = [index_doc]
    index.version = 1

    parsed_doc = MagicMock()
    parsed_doc.full_markdown = None  # missing

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
    chunk_repo.get_stats = AsyncMock(return_value={
        "total_chunks": 0, "total_documents": 1,
        "avg_chunk_size_chars": 0.0, "avg_chunk_size_tokens": 0.0,
        "min_chunk_size_chars": 0, "max_chunk_size_chars": 0,
        "total_tokens": 0,
    })

    mock_embedding_provider = AsyncMock()
    mock_embedding_provider.embed_texts = AsyncMock(return_value=[])
    mock_embedding_provider.get_dimensions = MagicMock(return_value=1536)

    with patch("app.services.index_processing_service.EmbeddingProviderRegistry") as mock_reg, \
         patch("app.services.source_resolution_service.ParsedDocumentRepository",
               return_value=parsed_doc_repo), \
         patch("app.services.index_processing_service.ProviderKeyService") as mock_pks:
        mock_reg.get_provider.return_value = mock_embedding_provider
        mock_pks.return_value.get_key_for_provider = AsyncMock(return_value="test-key")

        service = IndexProcessingService(
            session=AsyncMock(),
            index_repo=index_repo,
            chunk_repo=chunk_repo,
            provider_key_repo=AsyncMock(),
        )
        await service.process_index(index.id, uuid4(), uuid4())

    # Document must be marked failed with a descriptive message.
    # After seam refactor, SourceResolutionService raises ValidationError (not ValueError).
    failed_calls = [
        c for c in index_repo.update_document_status.call_args_list
        if c.args[2] == IndexDocumentStatus.failed
    ]
    assert len(failed_calls) == 1
    error_msg = str(failed_calls[0])
    assert "full_markdown" in error_msg.lower() or "markdown" in error_msg.lower()


def test_index_response_includes_version_and_config_dirty():
    index = MagicMock()
    index.id = uuid4()
    index.project_id = uuid4()
    index.name = "my-index"
    index.description = None
    index.config = {
        "parser": "llamaparse",
        "parse_config_hash": "abc123",
        "chunking_strategy": "recursive_character",
        "source_representation": "full_text",
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

    service = IndexService(
        index_repo=MagicMock(),
        chunk_repo=MagicMock(),
        parsed_doc_repo=MagicMock(),
    )
    response = service._to_response(index)

    assert response.version == 3
    assert response.config_dirty is True


@pytest.mark.asyncio
async def test_process_index_full_markdown_calls_seam(monkeypatch):
    """Seam-pinning: process_index routes full_markdown through SourceResolutionService
    and ChunkingDispatcher rather than touching chunkers directly."""
    index = _make_mock_index(source_representation="full_markdown")
    index.config = {
        "source_representation": "full_markdown",
        "chunking_strategy": "markdown_heading",
        "parser": "llamaparse",
        "parse_config_hash": "abc123",
        "split_heading_level": 2,
        "max_section_chars": 4000,
        "chunk_size": 512,
        "chunk_overlap": 50,
        "chunk_unit": "characters",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "embedding_dimensions": None,
    }
    parse_run_id = uuid4()
    index_doc = _make_mock_index_doc(parse_run_id=parse_run_id)
    index.index_documents = [index_doc]
    index.version = 1

    parsed_doc = MagicMock()
    parsed_doc.full_markdown = "# Section\nSome markdown content here."

    parsed_doc_repo = AsyncMock()
    parsed_doc_repo.get_by_run = AsyncMock(return_value=parsed_doc)

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
        "avg_chunk_size_chars": 37.0, "avg_chunk_size_tokens": 8.0,
        "min_chunk_size_chars": 37, "max_chunk_size_chars": 37,
        "total_tokens": 8,
    })

    mock_embedding_provider = AsyncMock()
    mock_embedding_provider.embed_texts = AsyncMock(return_value=[[0.1, 0.2]])
    mock_embedding_provider.get_dimensions = MagicMock(return_value=2)

    resolve_calls = []
    dispatch_calls = []

    from app.services.source_resolution_service import SourceResolutionService
    from app.services.chunking_dispatcher import ChunkingDispatcher

    original_resolve = SourceResolutionService.resolve
    original_dispatch = ChunkingDispatcher.dispatch

    async def spy_resolve(self, *, parsed_document_id, source_representation):
        result = await original_resolve(
            self, parsed_document_id=parsed_document_id,
            source_representation=source_representation,
        )
        resolve_calls.append({
            "parsed_document_id": parsed_document_id,
            "source_representation": source_representation,
            "result": result,
        })
        return result

    def spy_dispatch(self, *, source, config, source_document_id=None, source_filename=None):
        result = original_dispatch(
            self, source=source, config=config,
            source_document_id=source_document_id,
            source_filename=source_filename,
        )
        dispatch_calls.append({"source": source, "config": config})
        return result

    monkeypatch.setattr(SourceResolutionService, "resolve", spy_resolve)
    monkeypatch.setattr(ChunkingDispatcher, "dispatch", spy_dispatch)

    with patch("app.services.index_processing_service.EmbeddingProviderRegistry") as mock_reg, \
         patch("app.services.source_resolution_service.ParsedDocumentRepository",
               return_value=parsed_doc_repo), \
         patch("app.services.index_processing_service.ProviderKeyService") as mock_pks:
        mock_reg.get_provider.return_value = mock_embedding_provider
        mock_pks.return_value.get_key_for_provider = AsyncMock(return_value="test-key")

        service = IndexProcessingService(
            session=AsyncMock(),
            index_repo=index_repo,
            chunk_repo=chunk_repo,
            provider_key_repo=AsyncMock(),
        )
        await service.process_index(index.id, uuid4(), uuid4())

    # Seam was used: resolve called once with correct args
    assert len(resolve_calls) == 1
    assert resolve_calls[0]["source_representation"] == "full_markdown"

    # Resolver returned a TextSource (full_markdown resolves to TextSource)
    assert isinstance(resolve_calls[0]["result"], TextSource)

    # Dispatcher was called
    assert len(dispatch_calls) == 1
