"""Tests for ChunkingDispatcher."""
from uuid import uuid4

import pytest

from app.schemas.index import IndexConfig
from app.services.chunking_dispatcher import ChunkingDispatcher
from app.services.source_resolution_service import TextSource, BlocksSource


def _config(source_rep: str = "full_text", chunking_strategy: str = "recursive_character") -> IndexConfig:
    return IndexConfig.model_validate({
        "parser": "llamaparse",
        "parse_config_hash": "h" * 64,
        "source_representation": source_rep,
        "chunking_strategy": chunking_strategy,
        "chunk_size": 200,
        "chunk_overlap": 20,
        "chunk_unit": "characters",
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
    })


def test_dispatch_text_source_full_text_routes_to_chunking_service():
    src = TextSource(text="abcdef " * 200)
    chunks = ChunkingDispatcher().dispatch(
        source=src,
        config=_config("full_text"),
        source_document_id=str(uuid4()),
        source_filename="acme.pdf",
    )
    assert chunks
    # Plain text chunker emits no heading_path metadata
    assert "heading_path" not in chunks[0].metadata


def test_dispatch_text_source_full_markdown_routes_to_markdown_service():
    md = "# Title\n\nbody " * 200
    src = TextSource(text=md)
    config = _config("full_markdown", chunking_strategy="markdown_heading")
    chunks = ChunkingDispatcher().dispatch(
        source=src,
        config=config,
        source_document_id=str(uuid4()),
        source_filename="acme.md",
    )
    assert chunks
    assert chunks[0].metadata.get("heading_path") == ["Title"]


def test_dispatch_text_source_passes_metadata_through():
    sdid = uuid4()
    src = TextSource(text="content " * 100)
    chunks = ChunkingDispatcher().dispatch(
        source=src,
        config=_config("full_text"),
        source_document_id=str(sdid),
        source_filename="acme.pdf",
    )
    assert chunks[0].metadata["source_filename"] == "acme.pdf"
    assert chunks[0].metadata["source_document_id"] == str(sdid)


def test_dispatch_blocks_source_raises_not_implemented():
    src = BlocksSource(blocks=[{"text": "foo"}])
    with pytest.raises(NotImplementedError, match="block"):
        ChunkingDispatcher().dispatch(
            source=src,
            config=_config("block", "block"),
            source_document_id=str(uuid4()),
            source_filename=None,
        )


def test_dispatch_empty_text_returns_empty_list():
    src = TextSource(text="   ")
    assert ChunkingDispatcher().dispatch(
        source=src,
        config=_config("full_text"),
        source_document_id=str(uuid4()),
        source_filename=None,
    ) == []
