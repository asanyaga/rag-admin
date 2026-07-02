"""Tests for BlockChunkingService."""
from app.cdm.models import BBox, Block, BlockRole, CoordSpace, Quality
from app.schemas.index import IndexConfig
from app.services.block_chunking_service import BlockChunkingService


def _config(**overrides) -> IndexConfig:
    base = dict(
        parser="llamaparse",
        parse_config_hash="h" * 64,
        source_representation="block",
        chunking_strategy="block",
    )
    base.update(overrides)
    return IndexConfig(**base)


def _bbox(y0: float = 0.0) -> BBox:
    return BBox(x0=0.1, y0=y0, x1=0.9, y1=y0 + 0.05, space=CoordSpace.NORMALIZED)


def _block(
    bid: str,
    role: BlockRole,
    text: str,
    page: int = 0,
    y0: float = 0.0,
    confidence: float | None = None,
) -> Block:
    quality = Quality(confidence=confidence) if confidence is not None else None
    return Block(
        id=bid,
        role=role,
        native_type=role.value,
        page_index=page,
        bbox=_bbox(y0),
        text=text,
        quality=quality,
    )


def test_block_chunking_groups_by_heading():
    """A HEADING + following PARAGRAPHs form a single chunk."""
    svc = BlockChunkingService()
    blocks = [
        _block("b1", BlockRole.HEADING, "Q3 Financial Results", y0=0.0).model_dump(),
        _block("b2", BlockRole.TEXT, "Revenue grew 12%.", y0=0.1).model_dump(),
        _block("b3", BlockRole.TEXT, "Margins held steady.", y0=0.2).model_dump(),
    ]
    chunks = svc.chunk_blocks(blocks=blocks, config=_config())

    assert len(chunks) == 1
    assert "Q3 Financial Results" in chunks[0].content
    assert "Revenue grew 12%." in chunks[0].content
    assert "Margins held steady." in chunks[0].content
    assert chunks[0].metadata["block_ids"] == ["b1", "b2", "b3"]
    assert chunks[0].metadata["block_roles"] == ["heading", "text", "text"]


def test_block_chunking_table_not_split_when_cap_would_force_it():
    """A TABLE block always forms (or extends) a group; max_blocks_per_chunk
    never splits a single table off mid-table."""
    svc = BlockChunkingService()
    blocks = [
        _block("h1", BlockRole.HEADING, "Section", y0=0.0).model_dump(),
        _block("p1", BlockRole.TEXT, "Para 1", y0=0.1).model_dump(),
        _block("p2", BlockRole.TEXT, "Para 2", y0=0.2).model_dump(),
        _block("t1", BlockRole.TABLE, "table-text", y0=0.3).model_dump(),
    ]
    chunks = svc.chunk_blocks(blocks=blocks, config=_config(max_blocks_per_chunk=3))

    # Heading + 2 paragraphs hit cap, table joins via group_by_heading default.
    # Spec: TABLE never splits. Either it appends to current open group
    # (group_by_heading=True) or it closes and forms its own one-block group.
    table_chunks = [c for c in chunks if "t1" in c.metadata["block_ids"]]
    assert len(table_chunks) == 1
    assert table_chunks[0].metadata["block_ids"].count("t1") == 1


def test_block_chunking_table_standalone_when_no_open_group():
    """When group_by_heading=False, TABLE blocks emit their own one-block chunk."""
    svc = BlockChunkingService()
    blocks = [
        _block("t1", BlockRole.TABLE, "table-text", y0=0.0).model_dump(),
        _block("t2", BlockRole.TABLE, "another-table", y0=0.1).model_dump(),
    ]
    chunks = svc.chunk_blocks(blocks=blocks, config=_config(group_by_heading=False))

    assert len(chunks) == 2
    assert chunks[0].metadata["block_ids"] == ["t1"]
    assert chunks[1].metadata["block_ids"] == ["t2"]


def test_block_chunking_max_blocks_cap_emits_continuation_with_context():
    """When a group exceeds max_blocks_per_chunk, the next chunk is a
    continuation tagged with the most recent heading."""
    svc = BlockChunkingService()
    blocks = [
        _block("h1", BlockRole.HEADING, "Big Section", y0=0.0).model_dump(),
        *[
            _block(f"p{i}", BlockRole.TEXT, f"para {i}", y0=0.1 + i * 0.01).model_dump()
            for i in range(6)
        ],
    ]
    # Cap at 3 → first chunk = heading + 2 paras, second = 3 paras (continuation),
    # third = 1 para (continuation). Continuation chunks carry context_heading.
    chunks = svc.chunk_blocks(blocks=blocks, config=_config(max_blocks_per_chunk=3))

    assert len(chunks) == 3
    assert "context_heading" not in chunks[0].metadata
    assert chunks[0].content.startswith("Big Section")
    for cont in chunks[1:]:
        assert cont.metadata.get("context_heading") == "Big Section"
        assert cont.content.startswith("[context: Big Section]")


def test_block_chunking_role_filter_applies_whitelist():
    svc = BlockChunkingService()
    blocks = [
        _block("h1", BlockRole.HEADING, "H", y0=0.0).model_dump(),
        _block("p1", BlockRole.TEXT, "para", y0=0.1).model_dump(),
        _block("t1", BlockRole.TABLE, "tab", y0=0.2).model_dump(),
    ]
    chunks = svc.chunk_blocks(
        blocks=blocks, config=_config(block_role_filter=["table"])
    )

    assert len(chunks) == 1
    assert chunks[0].metadata["block_ids"] == ["t1"]
    assert chunks[0].metadata["block_roles"] == ["table"]


def test_block_chunking_skips_layout_blocks():
    svc = BlockChunkingService()
    blocks = [
        _block("hd", BlockRole.HEADER, "running header", y0=0.0).model_dump(),
        _block("h1", BlockRole.HEADING, "Real heading", y0=0.05).model_dump(),
        _block("p1", BlockRole.TEXT, "real para", y0=0.1).model_dump(),
        _block("ft", BlockRole.FOOTER, "page 1 of 5", y0=0.95).model_dump(),
        _block("mg", BlockRole.MARGINALIA, "[note]", y0=0.5).model_dump(),
    ]
    chunks = svc.chunk_blocks(blocks=blocks, config=_config())

    all_ids = {bid for c in chunks for bid in c.metadata["block_ids"]}
    assert "hd" not in all_ids
    assert "ft" not in all_ids
    assert "mg" not in all_ids
    assert all_ids == {"h1", "p1"}


def test_block_chunking_layout_skipped_even_when_in_filter():
    """Layout blocks are dropped even if explicitly listed in block_role_filter."""
    svc = BlockChunkingService()
    blocks = [
        _block("hd", BlockRole.HEADER, "noise", y0=0.0).model_dump(),
        _block("p1", BlockRole.TEXT, "real", y0=0.1).model_dump(),
    ]
    chunks = svc.chunk_blocks(
        blocks=blocks, config=_config(block_role_filter=["header", "text"])
    )
    all_ids = {bid for c in chunks for bid in c.metadata["block_ids"]}
    assert "hd" not in all_ids
    assert "p1" in all_ids


def test_block_chunking_no_headings_groups_all_content():
    svc = BlockChunkingService()
    blocks = [
        _block(f"p{i}", BlockRole.TEXT, f"para {i}", y0=0.1 * i).model_dump()
        for i in range(4)
    ]
    chunks = svc.chunk_blocks(blocks=blocks, config=_config(max_blocks_per_chunk=10))

    assert len(chunks) == 1
    assert chunks[0].metadata["block_ids"] == ["p0", "p1", "p2", "p3"]
    assert "context_heading" not in chunks[0].metadata


def test_block_chunking_provenance_fields_populated():
    svc = BlockChunkingService()
    blocks = [
        _block("h1", BlockRole.HEADING, "Heading", page=2, y0=0.0).model_dump(),
        _block("p1", BlockRole.TEXT, "paragraph A", page=2, y0=0.1).model_dump(),
        _block("p2", BlockRole.TEXT, "paragraph B", page=3, y0=0.0).model_dump(),
    ]
    chunks = svc.chunk_blocks(
        blocks=blocks,
        config=_config(),
        source_document_id="doc-1",
        source_filename="report.pdf",
    )

    meta = chunks[0].metadata
    assert meta["block_ids"] == ["h1", "p1", "p2"]
    assert meta["page_indices"] == [2, 3]
    assert meta["block_roles"] == ["heading", "text", "text"]
    assert len(meta["bboxes"]) == 3
    for bb in meta["bboxes"]:
        assert set(bb.keys()) == {"x0", "y0", "x1", "y1"}
    assert meta["source_document_id"] == "doc-1"
    assert meta["source_filename"] == "report.pdf"


def test_block_chunking_bbox_null_when_block_has_no_bbox():
    svc = BlockChunkingService()
    block_dict = Block(
        id="b1",
        role=BlockRole.TEXT,
        native_type="p",
        page_index=0,
        text="no bbox",
    ).model_dump()
    chunks = svc.chunk_blocks(blocks=[block_dict], config=_config())

    assert chunks[0].metadata["bboxes"] == [None]


def test_block_chunking_empty_input_returns_empty():
    svc = BlockChunkingService()
    assert svc.chunk_blocks(blocks=[], config=_config()) == []


def test_block_chunking_skips_chunk_when_heading_has_no_text():
    """Adjacent headings where the first has no text must not produce an empty chunk."""
    svc = BlockChunkingService()
    blocks = [
        _block("h1", BlockRole.HEADING, "", y0=0.0).model_dump(),   # empty text
        _block("h2", BlockRole.HEADING, "Real Heading", y0=0.1).model_dump(),
        _block("p1", BlockRole.TEXT, "content", y0=0.2).model_dump(),
    ]
    chunks = svc.chunk_blocks(blocks=blocks, config=_config())

    assert all(c.content.strip() for c in chunks), "empty-content chunk produced"
    assert len(chunks) == 1
    assert "Real Heading" in chunks[0].content
    assert "content" in chunks[0].content


def test_block_chunking_skips_chunk_when_table_has_no_text():
    """A TABLE with empty text appearing before any heading must not produce an empty chunk."""
    svc = BlockChunkingService()
    blocks = [
        _block("t1", BlockRole.TABLE, "", y0=0.0).model_dump(),     # empty text
        _block("p1", BlockRole.TEXT, "caption text", y0=0.1).model_dump(),
    ]
    chunks = svc.chunk_blocks(blocks=blocks, config=_config())

    assert all(c.content.strip() for c in chunks), "empty-content chunk produced"
    assert len(chunks) == 1
    assert "caption text" in chunks[0].content


def test_block_chunking_table_uses_markdown_when_text_empty():
    """TABLE with empty text but non-empty markdown (LlamaParse) must contribute content."""
    svc = BlockChunkingService()
    table_block = Block(
        id="t1",
        role=BlockRole.TABLE,
        native_type="table",
        page_index=0,
        bbox=_bbox(y0=0.1),
        text="",
        markdown="| Name | Value |\n| --- | --- |\n| Revenue | 1,081,557 |",
    ).model_dump()
    blocks = [
        _block("h1", BlockRole.HEADING, "Financials", y0=0.0).model_dump(),
        table_block,
    ]
    chunks = svc.chunk_blocks(blocks=blocks, config=_config())

    assert len(chunks) == 1
    assert "Revenue" in chunks[0].content
    assert "1,081,557" in chunks[0].content
    assert "---" not in chunks[0].content


def test_block_chunking_table_markdown_strips_html_br():
    """<br/> tags within markdown table cells must not appear in chunk content."""
    svc = BlockChunkingService()
    table_block = Block(
        id="t1",
        role=BlockRole.TABLE,
        native_type="table",
        page_index=0,
        bbox=_bbox(y0=0.0),
        text="",
        markdown="| Note | 2024<br/>KShs 000 |\n| --- | --- |\n| Revenue | 1,081,557 |",
    ).model_dump()
    chunks = svc.chunk_blocks(blocks=[table_block], config=_config(group_by_heading=False))

    assert len(chunks) == 1
    assert "<br/>" not in chunks[0].content
    assert "KShs 000" in chunks[0].content
