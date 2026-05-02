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
        _block("b2", BlockRole.PARAGRAPH, "Revenue grew 12%.", y0=0.1).model_dump(),
        _block("b3", BlockRole.PARAGRAPH, "Margins held steady.", y0=0.2).model_dump(),
    ]
    chunks = svc.chunk_blocks(blocks=blocks, config=_config())

    assert len(chunks) == 1
    assert "Q3 Financial Results" in chunks[0].content
    assert "Revenue grew 12%." in chunks[0].content
    assert "Margins held steady." in chunks[0].content
    assert chunks[0].metadata["block_ids"] == ["b1", "b2", "b3"]
    assert chunks[0].metadata["block_roles"] == ["heading", "paragraph", "paragraph"]
