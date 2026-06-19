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


def test_dispatch_blocks_source_routes_to_block_service():
    from app.cdm.models import BBox, Block, BlockRole, CoordSpace

    bbox = BBox(x0=0.0, y0=0.0, x1=1.0, y1=0.05, space=CoordSpace.NORMALIZED)
    blocks = [
        Block(
            id="b1",
            role=BlockRole.HEADING,
            native_type="h1",
            page_index=0,
            bbox=bbox,
            text="Heading",
        ).model_dump(),
        Block(
            id="b2",
            role=BlockRole.PARAGRAPH,
            native_type="p",
            page_index=0,
            bbox=bbox.model_copy(update={"y0": 0.1, "y1": 0.2}),
            text="Body paragraph",
        ).model_dump(),
    ]
    src = BlocksSource(blocks=blocks)
    chunks = ChunkingDispatcher().dispatch(
        source=src,
        config=_config("block", "block"),
        source_document_id=str(uuid4()),
        source_filename="acme.pdf",
    )

    assert len(chunks) == 1
    assert chunks[0].metadata["block_ids"] == ["b1", "b2"]
    assert chunks[0].metadata["page_indices"] == [0]
    assert chunks[0].metadata["block_roles"] == ["heading", "paragraph"]


def test_dispatch_empty_text_returns_empty_list():
    src = TextSource(text="   ")
    assert ChunkingDispatcher().dispatch(
        source=src,
        config=_config("full_text"),
        source_document_id=str(uuid4()),
        source_filename=None,
    ) == []


def test_text_source_with_page_boundaries_produces_chunks_with_page_numbers():
    """Full-text chunks from a paged source must have page_numbers in metadata."""
    # 200 chars on page 1 (0-199), 200 chars on page 2 (200-399)
    text = "a " * 100 + "b " * 100        # 400 chars total
    src = TextSource(
        text=text,
        page_boundaries=[
            {"page": 1, "start_char": 0,   "end_char": 200},
            {"page": 2, "start_char": 200, "end_char": 400},
        ],
    )
    chunks = ChunkingDispatcher().dispatch(
        source=src,
        config=_config("full_text"),
        source_document_id=str(uuid4()),
        source_filename="paged.pdf",
    )
    assert chunks, "expected at least one chunk"
    for chunk in chunks:
        assert chunk.metadata.get("page_numbers"), (
            f"chunk missing page_numbers: {chunk.metadata}"
        )


def test_text_source_without_page_boundaries_produces_chunks_without_page_numbers():
    """Backward compat: empty page_boundaries → no page_numbers on chunks."""
    text = "content " * 100
    src = TextSource(text=text, page_boundaries=[])
    chunks = ChunkingDispatcher().dispatch(
        source=src,
        config=_config("full_text"),
        source_document_id=str(uuid4()),
        source_filename="nopages.pdf",
    )
    assert chunks
    for chunk in chunks:
        assert not chunk.metadata.get("page_numbers"), (
            f"unexpected page_numbers: {chunk.metadata}"
        )
