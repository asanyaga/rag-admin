"""Service for chunking a CDM ParsedDocument's blocks by semantic role.

Grouping algorithm (per spec slice 3):

1. Sort blocks by (page_index, bbox.y0). Blocks without a bbox sort to the
   top of their page (y0 treated as -infinity for ordering only).
2. Apply block_role_filter (whitelist) if set.
3. Iterate:
   - HEADER/FOOTER/MARGINALIA: skip entirely (layout, never content).
   - TITLE/HEADING: closes any open group, opens a new one with this block.
   - TABLE/FIGURE: never split. If group_by_heading and a group is open,
     append; else close the current group and emit a single-block group.
   - Other content roles (PARAGRAPH/LIST/CAPTION/CODE/FORMULA): append to
     the open group; if no group is open, start one without a heading.
4. If appending would push current group over max_blocks_per_chunk and the
   incoming block is NOT a TABLE/FIGURE, close the group and start a new one.
   The new group is a "continuation": its metadata records `context_heading`
   from the most recently seen TITLE/HEADING and the chunk content is
   prefixed with `[context: <heading>]`.
5. Close any open group at end.
"""
from __future__ import annotations

import tiktoken

from app.cdm.models import Block, BlockRole
from app.schemas.index import IndexConfig
from app.services.chunking_service import ChunkResult


_HEADING_OPENERS = {BlockRole.TITLE, BlockRole.HEADING}
_NEVER_SPLIT = {BlockRole.TABLE, BlockRole.FIGURE}
_LAYOUT_SKIP = {BlockRole.HEADER, BlockRole.FOOTER, BlockRole.MARGINALIA}


class BlockChunkingService:
    """Groups CDM blocks into chunks per the block-chunking spec."""

    def __init__(self) -> None:
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        return len(self._tokenizer.encode(text))

    def chunk_blocks(
        self,
        *,
        blocks: list[dict],
        config: IndexConfig,
        source_document_id: str | None = None,
        source_filename: str | None = None,
    ) -> list[ChunkResult]:
        if not blocks:
            return []

        # 1. Validate dicts → Block. Skip rows that fail validation defensively.
        validated: list[Block] = []
        for raw in blocks:
            try:
                validated.append(Block.model_validate(raw))
            except Exception:
                continue
        if not validated:
            return []

        # 2. Sort by (page_index, bbox.y0). y0 missing → -inf within its page.
        validated.sort(
            key=lambda b: (b.page_index, b.bbox.y0 if b.bbox else float("-inf"))
        )

        # 3. Apply role filter (whitelist).
        role_filter = (
            {r for r in (config.block_role_filter or [])} or None
        )
        if role_filter is not None:
            validated = [b for b in validated if b.role.value in role_filter]
        if not validated:
            return []

        # 4. Iterate.
        chunks: list[ChunkResult] = []
        current: list[Block] = []
        current_is_continuation = False
        last_heading_text: str | None = None
        chunk_index_counter = 0

        def emit_current() -> None:
            nonlocal chunk_index_counter, current, current_is_continuation
            if not current:
                return
            chunks.append(
                self._build_chunk(
                    blocks=current,
                    chunk_index=chunk_index_counter,
                    context_heading=last_heading_text if current_is_continuation else None,
                    source_document_id=source_document_id,
                    source_filename=source_filename,
                )
            )
            chunk_index_counter += 1
            current = []
            current_is_continuation = False

        for block in validated:
            if block.role in _LAYOUT_SKIP:
                continue

            # Heading opens a new group.
            if block.role in _HEADING_OPENERS:
                emit_current()
                last_heading_text = block.text or last_heading_text
                current.append(block)
                continue

            # Table / Figure: never split.
            if block.role in _NEVER_SPLIT:
                if config.group_by_heading and current:
                    current.append(block)
                else:
                    emit_current()
                    current.append(block)
                    emit_current()
                continue

            # Generic content block.
            if current and len(current) >= config.max_blocks_per_chunk:
                emit_current()
                current_is_continuation = True
            current.append(block)

        emit_current()
        return chunks

    def _build_chunk(
        self,
        *,
        blocks: list[Block],
        chunk_index: int,
        context_heading: str | None,
        source_document_id: str | None,
        source_filename: str | None,
    ) -> ChunkResult:
        body = "\n\n".join(b.text for b in blocks if b.text)
        if context_heading:
            content = f"[context: {context_heading}]\n\n{body}"
        else:
            content = body

        page_indices = sorted({b.page_index for b in blocks})
        bboxes = [
            (
                {"x0": b.bbox.x0, "y0": b.bbox.y0, "x1": b.bbox.x1, "y1": b.bbox.y1}
                if b.bbox
                else None
            )
            for b in blocks
        ]

        metadata: dict = {
            "chunk_index": chunk_index,
            "block_ids": [b.id for b in blocks],
            "page_indices": page_indices,
            "block_roles": [b.role.value for b in blocks],
            "bboxes": bboxes,
        }
        if context_heading:
            metadata["context_heading"] = context_heading
        if source_document_id:
            metadata["source_document_id"] = source_document_id
        if source_filename:
            metadata["source_filename"] = source_filename

        return ChunkResult(
            content=content,
            chunk_index=chunk_index,
            token_count=self.count_tokens(content),
            char_count=len(content),
            start_char=0,
            end_char=len(content),
            metadata=metadata,
        )


_block_chunking_service: BlockChunkingService | None = None


def get_block_chunking_service() -> BlockChunkingService:
    global _block_chunking_service
    if _block_chunking_service is None:
        _block_chunking_service = BlockChunkingService()
    return _block_chunking_service
