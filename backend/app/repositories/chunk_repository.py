"""Repository for chunk data access."""
from uuid import UUID
from sqlalchemy import select, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Chunk, Document


class ChunkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_batch(
        self,
        chunks: list[dict]
    ) -> list[Chunk]:
        """Create multiple chunks in a batch.

        Each dict should contain:
        - index_id, document_id, content, embedding, chunk_index,
        - token_count, char_count, chunk_metadata
        """
        chunk_models = []
        for chunk_data in chunks:
            chunk = Chunk(
                index_id=chunk_data["index_id"],
                document_id=chunk_data["document_id"],
                content=chunk_data["content"],
                embedding=chunk_data["embedding"],
                chunk_index=chunk_data["chunk_index"],
                token_count=chunk_data["token_count"],
                char_count=chunk_data["char_count"],
                chunk_metadata=chunk_data.get("chunk_metadata", {}),
                index_version=chunk_data.get("index_version", 1),
                parse_run_id=chunk_data.get("parse_run_id"),
                source_type=chunk_data.get("source_type", "raw_text"),
            )
            self.session.add(chunk)
            chunk_models.append(chunk)

        await self.session.commit()
        return chunk_models

    async def get_by_id(
        self,
        chunk_id: UUID,
        index_id: UUID
    ) -> Chunk | None:
        """Get a chunk by ID, scoped to index."""
        result = await self.session.execute(
            select(Chunk)
            .options(selectinload(Chunk.document))
            .where(
                Chunk.id == chunk_id,
                Chunk.index_id == index_id
            )
        )
        return result.scalar_one_or_none()

    async def list_by_index(
        self,
        index_id: UUID,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[Chunk], int]:
        """List chunks for an index with pagination.

        Returns (chunks, total_count).
        """
        # Get total count
        count_result = await self.session.execute(
            select(func.count())
            .select_from(Chunk)
            .where(Chunk.index_id == index_id)
        )
        total = count_result.scalar() or 0

        # Get paginated chunks
        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(Chunk)
            .options(selectinload(Chunk.document))
            .where(Chunk.index_id == index_id)
            .order_by(Chunk.document_id, Chunk.chunk_index)
            .offset(offset)
            .limit(page_size)
        )
        chunks = list(result.scalars().all())

        return chunks, total

    async def list_by_document(
        self,
        index_id: UUID,
        document_id: UUID
    ) -> list[Chunk]:
        """List all chunks for a specific document within an index."""
        result = await self.session.execute(
            select(Chunk)
            .where(
                Chunk.index_id == index_id,
                Chunk.document_id == document_id
            )
            .order_by(Chunk.chunk_index)
        )
        return list(result.scalars().all())

    async def search_by_content(
        self,
        index_id: UUID,
        query: str,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[Chunk], int]:
        """Search chunks by content text (basic text match).

        Returns (chunks, total_count).
        """
        # Build the search condition - simple ILIKE for now
        search_pattern = f"%{query}%"

        # Get total count
        count_result = await self.session.execute(
            select(func.count())
            .select_from(Chunk)
            .where(
                Chunk.index_id == index_id,
                Chunk.content.ilike(search_pattern)
            )
        )
        total = count_result.scalar() or 0

        # Get paginated results
        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(Chunk)
            .options(selectinload(Chunk.document))
            .where(
                Chunk.index_id == index_id,
                Chunk.content.ilike(search_pattern)
            )
            .order_by(Chunk.document_id, Chunk.chunk_index)
            .offset(offset)
            .limit(page_size)
        )
        chunks = list(result.scalars().all())

        return chunks, total

    async def delete_by_index(self, index_id: UUID) -> int:
        """Delete all chunks for an index. Returns count deleted."""
        result = await self.session.execute(
            delete(Chunk).where(Chunk.index_id == index_id)
        )
        await self.session.commit()
        return result.rowcount

    async def delete_by_document(
        self,
        index_id: UUID,
        document_id: UUID
    ) -> int:
        """Delete all chunks for a document within an index. Returns count deleted."""
        result = await self.session.execute(
            delete(Chunk).where(
                Chunk.index_id == index_id,
                Chunk.document_id == document_id
            )
        )
        await self.session.commit()
        return result.rowcount

    async def vector_search(
        self,
        index_id: UUID,
        query_embedding: list[float],
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ) -> list[tuple[Chunk, float]]:
        """Cosine similarity search using pgvector <=> operator.

        Returns list of (Chunk, similarity_score) tuples ordered by score desc.
        The Chunk objects have their document relationship eagerly loaded.
        """
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        # Raw SQL: cosine distance (lower = more similar), convert to similarity.
        # Use CAST() instead of ::vector to avoid conflict with SQLAlchemy's
        # :name bind-parameter syntax.
        raw = await self.session.execute(
            text("""
                SELECT c.id,
                       (1 - (c.embedding <=> CAST(:embedding AS vector))) AS similarity
                FROM chunks c
                WHERE c.index_id = :index_id
                  AND (1 - (c.embedding <=> CAST(:embedding AS vector))) >= :threshold
                ORDER BY similarity DESC
                LIMIT :top_k
            """),
            {
                "embedding": embedding_str,
                "index_id": str(index_id),
                "threshold": similarity_threshold,
                "top_k": top_k,
            },
        )
        rows = raw.fetchall()

        if not rows:
            return []

        # Batch-load full Chunk ORM objects with document relationship
        chunk_ids = [row[0] for row in rows]
        score_map = {row[0]: float(row[1]) for row in rows}

        result = await self.session.execute(
            select(Chunk)
            .options(selectinload(Chunk.document))
            .where(Chunk.id.in_(chunk_ids))
        )
        chunks_by_id = {c.id: c for c in result.scalars().all()}

        # Preserve original ordering
        return [
            (chunks_by_id[cid], score_map[cid])
            for cid in chunk_ids
            if cid in chunks_by_id
        ]

    async def fulltext_search(
        self,
        index_id: UUID,
        query_text: str,
        top_k: int = 5,
    ) -> list[tuple[Chunk, float]]:
        """PostgreSQL full-text search using ts_rank and plainto_tsquery.

        Returns list of (Chunk, ts_rank_score) tuples ordered by rank desc.
        """
        raw = await self.session.execute(
            text("""
                SELECT c.id,
                       ts_rank(to_tsvector('english', c.content),
                               plainto_tsquery('english', :query)) AS rank
                FROM chunks c
                WHERE c.index_id = :index_id
                  AND to_tsvector('english', c.content) @@
                      plainto_tsquery('english', :query)
                ORDER BY rank DESC
                LIMIT :top_k
            """),
            {
                "query": query_text,
                "index_id": str(index_id),
                "top_k": top_k,
            },
        )
        rows = raw.fetchall()

        if not rows:
            return []

        chunk_ids = [row[0] for row in rows]
        score_map = {row[0]: float(row[1]) for row in rows}

        result = await self.session.execute(
            select(Chunk)
            .options(selectinload(Chunk.document))
            .where(Chunk.id.in_(chunk_ids))
        )
        chunks_by_id = {c.id: c for c in result.scalars().all()}

        return [
            (chunks_by_id[cid], score_map[cid])
            for cid in chunk_ids
            if cid in chunks_by_id
        ]

    async def get_stats(self, index_id: UUID) -> dict:
        """Get chunk statistics for an index."""
        # Get aggregates
        result = await self.session.execute(
            select(
                func.count(Chunk.id).label("total_chunks"),
                func.count(func.distinct(Chunk.document_id)).label("total_documents"),
                func.avg(Chunk.char_count).label("avg_char_count"),
                func.avg(Chunk.token_count).label("avg_token_count"),
                func.min(Chunk.char_count).label("min_char_count"),
                func.max(Chunk.char_count).label("max_char_count"),
                func.sum(Chunk.token_count).label("total_tokens")
            )
            .where(Chunk.index_id == index_id)
        )
        row = result.one()

        return {
            "total_chunks": row.total_chunks or 0,
            "total_documents": row.total_documents or 0,
            "avg_chunk_size_chars": float(row.avg_char_count or 0),
            "avg_chunk_size_tokens": float(row.avg_token_count or 0),
            "min_chunk_size_chars": row.min_char_count or 0,
            "max_chunk_size_chars": row.max_char_count or 0,
            "total_tokens": row.total_tokens or 0
        }
