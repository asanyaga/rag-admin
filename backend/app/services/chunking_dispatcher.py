"""Dispatch a resolved ChunkSource + IndexConfig to the right chunker."""
from app.schemas.index import IndexConfig
from app.services.block_chunking_service import (
    BlockChunkingService,
    get_block_chunking_service,
)
from app.services.chunking_service import (
    ChunkResult,
    ChunkingService,
    get_chunking_service,
)
from app.services.markdown_chunking_service import (
    MarkdownChunkingService,
    get_markdown_chunking_service,
)
from app.services.source_resolution_service import (
    BlocksSource,
    ChunkSource,
    TextSource,
)


class ChunkingDispatcher:
    """Routes a `ChunkSource` to the right chunker based on the config."""

    def __init__(
        self,
        chunking_service: ChunkingService | None = None,
        markdown_chunking_service: MarkdownChunkingService | None = None,
        block_chunking_service: BlockChunkingService | None = None,
    ) -> None:
        self.chunking_service = chunking_service or get_chunking_service()
        self.markdown_chunking_service = (
            markdown_chunking_service or get_markdown_chunking_service()
        )
        self.block_chunking_service = (
            block_chunking_service or get_block_chunking_service()
        )

    def dispatch(
        self,
        *,
        source: ChunkSource,
        config: IndexConfig,
        source_document_id: str | None = None,
        source_filename: str | None = None,
    ) -> list[ChunkResult]:
        if isinstance(source, TextSource):
            if config.source_representation == "full_markdown":
                return self.markdown_chunking_service.chunk_markdown(
                    markdown=source.text,
                    config=config,
                    source_document_id=source_document_id,
                    source_filename=source_filename,
                )
            # full_text uses the plain-text chunker.
            return self.chunking_service.chunk_text(
                text=source.text,
                config=config,
                source_document_id=source_document_id,
                source_filename=source_filename,
                page_boundaries=source.page_boundaries or None,
            )
        if isinstance(source, BlocksSource):
            if config.chunking_strategy == "classified_block":
                raise NotImplementedError(
                    "classified_block chunking requires a classification run "
                    "and is not yet implemented"
                )
            return self.block_chunking_service.chunk_blocks(
                blocks=source.blocks,
                config=config,
                source_document_id=source_document_id,
                source_filename=source_filename,
            )
        raise TypeError(f"Unsupported ChunkSource type: {type(source).__name__}")
