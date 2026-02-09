"""Service for chunk inspection and browsing."""
import math
from uuid import UUID

from app.repositories.chunk_repository import ChunkRepository
from app.repositories.index_repository import IndexRepository
from app.schemas.chunk import (
    ChunkResponse,
    ChunkListItem,
    ChunkListResponse,
)
from app.services.exceptions import NotFoundError


class ChunkService:
    def __init__(
        self,
        chunk_repo: ChunkRepository,
        index_repo: IndexRepository
    ):
        self.chunk_repo = chunk_repo
        self.index_repo = index_repo

    def _to_response(self, chunk) -> ChunkResponse:
        """Convert a Chunk model to a response."""
        return ChunkResponse(
            id=chunk.id,
            index_id=chunk.index_id,
            document_id=chunk.document_id,
            content=chunk.content,
            chunk_index=chunk.chunk_index,
            token_count=chunk.token_count,
            char_count=chunk.char_count,
            metadata=chunk.metadata,
            created_at=chunk.created_at,
            document_title=chunk.document.title if chunk.document else None,
            document_filename=chunk.document.source_metadata.get("filename") if chunk.document else None,
        )

    def _to_list_item(self, chunk) -> ChunkListItem:
        """Convert a Chunk model to a list item."""
        # Truncate content for preview
        content_preview = chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content

        return ChunkListItem(
            id=chunk.id,
            document_id=chunk.document_id,
            content_preview=content_preview,
            chunk_index=chunk.chunk_index,
            token_count=chunk.token_count,
            char_count=chunk.char_count,
            document_title=chunk.document.title if chunk.document else None,
        )

    async def get_chunk(
        self,
        chunk_id: UUID,
        index_id: UUID,
        project_id: UUID
    ) -> ChunkResponse:
        """Get a single chunk by ID.

        Raises:
        - NotFoundError: Index or chunk not found
        """
        # Verify index exists and belongs to project
        index = await self.index_repo.get_by_id(index_id, project_id)
        if not index:
            raise NotFoundError(f"Index {index_id} not found")

        chunk = await self.chunk_repo.get_by_id(chunk_id, index_id)
        if not chunk:
            raise NotFoundError(f"Chunk {chunk_id} not found")

        return self._to_response(chunk)

    async def list_chunks(
        self,
        index_id: UUID,
        project_id: UUID,
        page: int = 1,
        page_size: int = 20
    ) -> ChunkListResponse:
        """List chunks for an index with pagination.

        Raises:
        - NotFoundError: Index not found
        """
        # Verify index exists
        index = await self.index_repo.get_by_id(index_id, project_id)
        if not index:
            raise NotFoundError(f"Index {index_id} not found")

        chunks, total = await self.chunk_repo.list_by_index(
            index_id, page, page_size
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return ChunkListResponse(
            items=[self._to_list_item(c) for c in chunks],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def search_chunks(
        self,
        index_id: UUID,
        project_id: UUID,
        query: str,
        page: int = 1,
        page_size: int = 20
    ) -> ChunkListResponse:
        """Search chunks by content.

        Raises:
        - NotFoundError: Index not found
        """
        # Verify index exists
        index = await self.index_repo.get_by_id(index_id, project_id)
        if not index:
            raise NotFoundError(f"Index {index_id} not found")

        chunks, total = await self.chunk_repo.search_by_content(
            index_id, query, page, page_size
        )

        total_pages = math.ceil(total / page_size) if total > 0 else 1

        return ChunkListResponse(
            items=[self._to_list_item(c) for c in chunks],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def list_chunks_by_document(
        self,
        index_id: UUID,
        project_id: UUID,
        document_id: UUID
    ) -> list[ChunkResponse]:
        """List all chunks for a specific document.

        Raises:
        - NotFoundError: Index not found
        """
        # Verify index exists
        index = await self.index_repo.get_by_id(index_id, project_id)
        if not index:
            raise NotFoundError(f"Index {index_id} not found")

        chunks = await self.chunk_repo.list_by_document(index_id, document_id)
        return [self._to_response(c) for c in chunks]
