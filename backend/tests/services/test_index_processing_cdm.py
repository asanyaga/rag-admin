import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.cdm.models import BBox, Block, BlockRole, CoordSpace
from app.models import IndexStatus, IndexDocumentStatus
from app.schemas.index import IndexConfig
from app.services.exceptions import ValidationError
from app.services.index_processing_service import IndexProcessingService
from app.services.index_service import IndexService
from app.services.source_resolution_service import TextSource


def _make_mock_index(source_representation="full_text"):
    config = IndexConfig(
        source_representation=source_representation,
        chunking_strategy="recursive_character",
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

    with pytest.raises(ValidationError, match="no parse_run_id"):
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
    # Blocks with invalid shape all fail CDM validation → chunk_blocks returns [] →
    # processing raises "produced no chunks" (not NotImplementedError — block chunking
    # is now implemented).
    error_msg = failed_call[0].kwargs.get("error_message", "") or str(failed_call[0].args)
    assert "no chunks" in error_msg.lower() or "not yet implemented" in error_msg.lower()


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
async def test_process_index_block_source_produces_block_chunks():
    """End-to-end: block source_representation produces chunks with block metadata."""
    index = _make_mock_index()
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

    # Three valid CDM blocks on a single page: heading + two paragraphs.
    # group_by_heading defaults to True and max_blocks_per_chunk defaults to 10,
    # so all three blocks group into a single chunk.
    bbox = BBox(x0=0.1, y0=0.0, x1=0.9, y1=0.05, space=CoordSpace.NORMALIZED)
    blocks = [
        Block(id="b1", role=BlockRole.HEADING, native_type="h1", page_index=0, bbox=bbox, text="Heading").model_dump(),
        Block(id="b2", role=BlockRole.PARAGRAPH, native_type="p", page_index=0, bbox=bbox.model_copy(update={"y0": 0.1, "y1": 0.2}), text="para 1").model_dump(),
        Block(id="b3", role=BlockRole.PARAGRAPH, native_type="p", page_index=0, bbox=bbox.model_copy(update={"y0": 0.2, "y1": 0.3}), text="para 2").model_dump(),
    ]

    parsed_doc = MagicMock()
    parsed_doc.content = {"blocks": blocks}

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
        "avg_chunk_size_chars": 30.0, "avg_chunk_size_tokens": 6.0,
        "min_chunk_size_chars": 30, "max_chunk_size_chars": 30,
        "total_tokens": 6,
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

    chunk_repo.create_batch.assert_called_once()
    created_chunks = chunk_repo.create_batch.call_args[0][0]
    assert len(created_chunks) == 1

    chunk = created_chunks[0]
    assert chunk["source_type"] == "block"
    assert chunk["parse_run_id"] == str(parse_run_id)
    assert chunk["chunk_metadata"]["block_ids"] == ["b1", "b2", "b3"]
    assert chunk["chunk_metadata"]["block_roles"] == ["heading", "paragraph", "paragraph"]
    assert chunk["chunk_metadata"]["page_indices"] == [0]
