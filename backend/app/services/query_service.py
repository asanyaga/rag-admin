"""Query service for semantic, keyword, and hybrid search."""
import time
import logging
from uuid import UUID

from app.models import Chunk, IndexStatus
from app.repositories.index_repository import IndexRepository
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.provider_key_repository import ProviderKeyRepository
from app.schemas.query import (
    QueryRequest,
    QueryResponse,
    RetrievalResult,
    RetrievalResultMetadata,
)
from app.services.embedding_provider import EmbeddingProviderRegistry
from app.services.exceptions import NotFoundError, ValidationError
from app.utils.encryption import decrypt

logger = logging.getLogger(__name__)


class QueryService:
    def __init__(
        self,
        index_repo: IndexRepository,
        chunk_repo: ChunkRepository,
        provider_key_repo: ProviderKeyRepository,
    ):
        self.index_repo = index_repo
        self.chunk_repo = chunk_repo
        self.provider_key_repo = provider_key_repo

    async def query_index(
        self,
        index_id: UUID,
        project_id: UUID,
        user_id: UUID,
        request: QueryRequest,
    ) -> QueryResponse:
        """Execute a search query against an index.

        Validates the index is ready, routes to the appropriate search method,
        and measures execution time.
        """
        # Validate index exists and is ready
        index = await self.index_repo.get_by_id(index_id, project_id)
        if not index:
            raise NotFoundError(f"Index {index_id} not found")
        if index.status != IndexStatus.ready:
            raise ValidationError(
                f"Index is not ready for querying (status: {index.status.value})"
            )

        start = time.perf_counter()

        search_type = request.search_type
        if search_type == "semantic":
            results = await self._semantic_search(
                index, user_id, project_id, request
            )
        elif search_type == "keyword":
            results = await self._keyword_search(index, request)
        elif search_type == "hybrid":
            results = await self._hybrid_search(
                index, user_id, project_id, request
            )
        else:
            raise ValidationError(f"Unsupported search type: {search_type}")

        elapsed_ms = (time.perf_counter() - start) * 1000

        return QueryResponse(
            query=request.query,
            results=results,
            total_results=len(results),
            search_type=search_type,
            execution_time_ms=round(elapsed_ms, 1),
        )

    # ------------------------------------------------------------------
    # Private search methods
    # ------------------------------------------------------------------

    async def _get_query_embedding(
        self,
        index_config: dict,
        user_id: UUID,
        project_id: UUID,
        query_text: str,
    ) -> list[float]:
        """Embed the query string using the index's configured provider/model."""
        provider_name = index_config.get("embedding_provider", "openai")
        model_name = index_config.get("embedding_model", "text-embedding-3-small")

        # Resolve the user's API key for this provider
        key_record = await self.provider_key_repo.get_for_provider(
            user_id=user_id,
            provider=provider_name,
            project_id=project_id,
        )
        if not key_record:
            raise ValidationError(
                f"No API key configured for provider '{provider_name}'. "
                "Add one in Settings → API Keys."
            )

        api_key = decrypt(key_record.api_key_encrypted)
        provider = EmbeddingProviderRegistry.get_provider(
            provider_name, api_key=api_key, model=model_name
        )
        embeddings = await provider.embed_texts([query_text])
        return embeddings[0]

    async def _semantic_search(
        self, index, user_id: UUID, project_id: UUID, request: QueryRequest
    ) -> list[RetrievalResult]:
        embedding = await self._get_query_embedding(
            index.config, user_id, project_id, request.query
        )
        scored_chunks = await self.chunk_repo.vector_search(
            index_id=index.id,
            query_embedding=embedding,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold,
        )
        return [
            self._to_result(chunk, score, rank)
            for rank, (chunk, score) in enumerate(scored_chunks, 1)
        ]

    async def _keyword_search(
        self, index, request: QueryRequest
    ) -> list[RetrievalResult]:
        # Fetch more than top_k so we can filter by threshold after normalizing
        raw_k = request.top_k * 3
        scored_chunks = await self.chunk_repo.fulltext_search(
            index_id=index.id,
            query_text=request.query,
            top_k=raw_k,
        )
        if not scored_chunks:
            return []

        # Normalize ts_rank scores to 0-1 range
        max_score = max(s for _, s in scored_chunks)
        if max_score > 0:
            normalized = [
                (chunk, score / max_score)
                for chunk, score in scored_chunks
            ]
        else:
            normalized = [(chunk, 0.0) for chunk, _ in scored_chunks]

        # Apply threshold and limit
        filtered = [
            (chunk, score)
            for chunk, score in normalized
            if score >= request.similarity_threshold
        ][:request.top_k]

        return [
            self._to_result(chunk, score, rank)
            for rank, (chunk, score) in enumerate(filtered, 1)
        ]

    async def _hybrid_search(
        self, index, user_id: UUID, project_id: UUID, request: QueryRequest
    ) -> list[RetrievalResult]:
        """Hybrid search using Reciprocal Rank Fusion (RRF)."""
        pool_k = request.top_k * 3

        embedding = await self._get_query_embedding(
            index.config, user_id, project_id, request.query
        )

        # Run sequentially — asyncpg doesn't support concurrent queries
        # on a single connection.
        vector_results = await self.chunk_repo.vector_search(
            index_id=index.id,
            query_embedding=embedding,
            top_k=pool_k,
            similarity_threshold=0.0,  # no threshold during fusion
        )
        keyword_results = await self.chunk_repo.fulltext_search(
            index_id=index.id,
            query_text=request.query,
            top_k=pool_k,
        )

        # Build RRF scores (k=60 is standard)
        rrf_k = 60
        rrf_scores: dict[UUID, float] = {}
        vector_score_map: dict[UUID, float] = {}

        for rank_idx, (chunk, sim_score) in enumerate(vector_results, 1):
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + 1.0 / (rrf_k + rank_idx)
            vector_score_map[chunk.id] = sim_score

        for rank_idx, (chunk, _) in enumerate(keyword_results, 1):
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + 1.0 / (rrf_k + rank_idx)

        # Collect all chunks by ID
        all_chunks: dict[UUID, Chunk] = {}
        for chunk, _ in vector_results:
            all_chunks[chunk.id] = chunk
        for chunk, _ in keyword_results:
            all_chunks[chunk.id] = chunk

        # Sort by RRF score descending
        sorted_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)

        # Use vector similarity as the display score (more intuitive for users)
        # For chunks only found via keyword, use 0.0
        results = []
        for cid in sorted_ids:
            display_score = vector_score_map.get(cid, 0.0)
            if display_score < request.similarity_threshold:
                continue
            results.append((all_chunks[cid], display_score))
            if len(results) >= request.top_k:
                break

        return [
            self._to_result(chunk, score, rank)
            for rank, (chunk, score) in enumerate(results, 1)
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_result(chunk: Chunk, score: float, rank: int) -> RetrievalResult:
        """Convert a Chunk ORM object to a RetrievalResult schema."""
        doc = chunk.document
        if doc:
            doc_name = (
                doc.source_metadata.get("filename")
                or doc.title
                or "Unknown"
            )
        else:
            doc_name = "Unknown"

        page = (chunk.chunk_metadata or {}).get("page")

        return RetrievalResult(
            chunk_id=str(chunk.id),
            rank=rank,
            score=round(score, 4),
            content=chunk.content,
            metadata=RetrievalResultMetadata(
                document_id=str(chunk.document_id),
                document_name=doc_name,
                page=page,
                chunk_index=chunk.chunk_index,
                token_count=chunk.token_count,
                char_count=chunk.char_count,
            ),
        )
