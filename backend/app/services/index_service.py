"""Service for index management."""
from datetime import datetime
from uuid import UUID
from sqlalchemy.exc import IntegrityError

from app.models import IndexStatus, IndexDocumentStatus
from app.repositories.index_repository import IndexRepository
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.schemas.index import (
    AddParsedDocumentsRequest,
    IndexConfig,
    IndexParsedDocumentItem,
    IndexStats,
    IndexCreate,
    IndexUpdate,
    IndexResponse,
    IndexListResponse,
    IndexProcessingStatusResponse,
    IndexDocumentStatusResponse,
)
from app.services.exceptions import ConflictError, NotFoundError, ValidationError


class IndexService:
    def __init__(
        self,
        index_repo: IndexRepository,
        chunk_repo: ChunkRepository,
        parsed_doc_repo: ParsedDocumentRepository,
    ):
        self.index_repo = index_repo
        self.chunk_repo = chunk_repo
        self.parsed_doc_repo = parsed_doc_repo

    def _to_response(self, index, include_counts: bool = True) -> IndexResponse:
        """Convert an Index model to a response."""
        config = IndexConfig.model_validate(index.config)
        stats = IndexStats.model_validate(index.stats) if index.stats else None

        response_data = {
            "id": index.id,
            "project_id": index.project_id,
            "name": index.name,
            "description": index.description,
            "config": config,
            "stats": stats,
            "status": index.status.value,
            "error_message": index.error_message,
            "created_by": index.created_by,
            "created_at": index.created_at,
            "updated_at": index.updated_at,
            "document_count": 0,
            "chunk_count": 0,
            "version": getattr(index, "version", 1),
            "config_dirty": getattr(index, "config_dirty", False),
        }

        return IndexResponse.model_validate(response_data)

    def _to_list_response(self, index) -> IndexListResponse:
        """Convert an Index model to a list response."""
        config = index.config or {}
        return IndexListResponse(
            id=index.id,
            project_id=index.project_id,
            name=index.name,
            description=index.description,
            status=index.status.value,
            document_count=0,  # Will be populated by caller if needed
            chunk_count=0,
            embedding_model=config.get("embedding_model"),
            chunking_strategy=config.get("chunking_strategy"),
            created_at=index.created_at,
        )

    async def create_index(
        self,
        project_id: UUID,
        user_id: UUID,
        data: IndexCreate,
    ) -> IndexResponse:
        """Create a new index. Validates parsed-doc family + segment per spec §4."""
        config = data.config

        if data.parsed_document_ids:
            await self._validate_parsed_documents(
                project_id=project_id,
                config=config,
                parsed_document_ids=data.parsed_document_ids,
            )

        try:
            index = await self.index_repo.create(
                project_id=project_id,
                user_id=user_id,
                name=data.name,
                description=data.description,
                config=config,
            )
            if data.parsed_document_ids:
                await self.index_repo.add_parsed_documents(
                    index.id, data.parsed_document_ids,
                )
            return self._to_response(index)
        except IntegrityError as e:
            if "uq_indexes_project_name" in str(e).lower():
                raise ConflictError(
                    f"Index with name '{data.name}' already exists in this project"
                )
            raise

    async def get_index(
        self,
        index_id: UUID,
        project_id: UUID
    ) -> IndexResponse:
        """Get an index by ID.

        Raises:
        - NotFoundError: Index not found
        """
        index = await self.index_repo.get_by_id(index_id, project_id)
        if not index:
            raise NotFoundError(f"Index {index_id} not found")

        response = self._to_response(index)

        # Add counts and document IDs
        response.document_count = await self.index_repo.count_documents(index_id)
        response.chunk_count = await self.index_repo.count_chunks(index_id)
        response.document_ids = await self.index_repo.get_document_ids(index_id)

        return response

    async def list_indexes(self, project_id: UUID) -> list[IndexListResponse]:
        """List all indexes for a project."""
        indexes = await self.index_repo.list_by_project(project_id)
        responses = []

        for index in indexes:
            response = self._to_list_response(index)
            response.document_count = await self.index_repo.count_documents(index.id)
            response.chunk_count = await self.index_repo.count_chunks(index.id)
            responses.append(response)

        return responses

    async def update_index(
        self,
        index_id: UUID,
        project_id: UUID,
        data: IndexUpdate
    ) -> IndexResponse:
        """Update an index's name and/or description.

        Raises:
        - NotFoundError: Index not found
        - ValidationError: Cannot update index that's not in 'created' status
        - ConflictError: New name conflicts with existing index
        """
        index = await self.index_repo.get_by_id(index_id, project_id)
        if not index:
            raise NotFoundError(f"Index {index_id} not found")

        # Only allow updates when status is 'created'
        if index.status != IndexStatus.created:
            raise ValidationError(
                f"Cannot update index with status '{index.status.value}'. "
                "Only indexes in 'created' status can be modified."
            )

        # Check for name conflicts if changing name
        if data.name and data.name != index.name:
            existing = await self.index_repo.get_by_name(project_id, data.name)
            if existing:
                raise ConflictError(f"Index with name '{data.name}' already exists")

        update_data = data.model_dump(exclude_unset=True)
        index = await self.index_repo.update(
            index_id,
            project_id,
            name=update_data.get("name"),
            description=update_data.get("description")
        )

        if not index:
            raise NotFoundError(f"Index {index_id} not found")

        return self._to_response(index)

    async def delete_index(
        self,
        index_id: UUID,
        project_id: UUID
    ) -> None:
        """Delete an index.

        Raises:
        - NotFoundError: Index not found
        """
        deleted = await self.index_repo.delete(index_id, project_id)
        if not deleted:
            raise NotFoundError(f"Index {index_id} not found")

    async def add_parsed_documents(
        self,
        index_id: UUID,
        project_id: UUID,
        request: AddParsedDocumentsRequest,
    ) -> IndexResponse:
        """Add parsed-documents to an index."""
        index = await self.index_repo.get_by_id(index_id, project_id)
        if not index:
            raise NotFoundError(f"Index {index_id} not found")

        if index.status == IndexStatus.processing:
            raise ValidationError("Cannot add parsed-documents while index is processing")

        config = IndexConfig.model_validate(index.config)
        await self._validate_parsed_documents(
            project_id=project_id,
            config=config,
            parsed_document_ids=request.parsed_document_ids,
        )
        await self.index_repo.add_parsed_documents(
            index_id=index_id,
            parsed_document_ids=request.parsed_document_ids,
        )
        return await self.get_index(index_id, project_id)

    async def _validate_parsed_documents(
        self,
        *,
        project_id: UUID,
        config: IndexConfig,
        parsed_document_ids: list[UUID],
    ) -> None:
        """Validate every parsed_doc against the index's declared family + segment."""
        if not parsed_document_ids:
            return

        rows = await self.parsed_doc_repo.get_for_validation(
            parsed_document_ids=parsed_document_ids,
            project_id=project_id,
        )
        by_id = {row.parse_run_id: row for row in rows}

        missing = [pid for pid in parsed_document_ids if pid not in by_id]
        if missing:
            raise NotFoundError(
                f"parsed_document(s) not found in project: "
                f"{', '.join(str(m) for m in missing)}"
            )

        family_mismatch: list[UUID] = []
        failed_runs: list[UUID] = []
        segment_missing: list[UUID] = []
        for pid, row in by_id.items():
            if row.parser != config.parser or row.parse_config_hash != config.parse_config_hash:
                family_mismatch.append(pid)
                continue
            if row.run_status != "succeeded":
                failed_runs.append(pid)
                continue
            if config.source_representation == "full_markdown" and row.full_markdown is None:
                segment_missing.append(pid)
            elif config.source_representation == "block" and row.block_count == 0:
                segment_missing.append(pid)
            # full_text is always populated by invariant

        if family_mismatch:
            raise ValidationError(
                f"parsed_document(s) do not match declared family "
                f"({config.parser}, {config.parse_config_hash}): "
                f"{', '.join(str(m) for m in family_mismatch)}"
            )
        if failed_runs:
            raise ValidationError(
                f"parsed_document(s) come from a non-succeeded parse run: "
                f"{', '.join(str(m) for m in failed_runs)}"
            )
        if segment_missing:
            raise ValidationError(
                f"parsed_document(s) lack {config.source_representation} segment: "
                f"{', '.join(str(m) for m in segment_missing)}"
            )

    async def remove_document(
        self,
        index_id: UUID,
        project_id: UUID,
        document_id: UUID
    ) -> IndexResponse:
        """Remove a document from an index.

        Raises:
        - NotFoundError: Index or document not found
        - ValidationError: Index is processing
        """
        index = await self.index_repo.get_by_id(index_id, project_id)
        if not index:
            raise NotFoundError(f"Index {index_id} not found")

        if index.status == IndexStatus.processing:
            raise ValidationError("Cannot remove documents while index is processing")

        removed = await self.index_repo.remove_document(index_id, document_id)
        if not removed:
            raise NotFoundError(f"Document {document_id} not found in index")

        return await self.get_index(index_id, project_id)

    async def list_index_parsed_documents(
        self,
        index_id: UUID,
        project_id: UUID,
    ) -> list[IndexParsedDocumentItem]:
        """List parsed-document rows for the index detail tab.

        Raises:
            - NotFoundError: Index not found
        """
        index = await self.index_repo.get_by_id(index_id, project_id)
        if not index:
            raise NotFoundError(f"Index {index_id} not found")

        rows = await self.index_repo.list_index_parsed_documents(index_id)
        return [
            IndexParsedDocumentItem(
                parse_run_id=row.parse_run_id,
                source_filename=row.source_filename,
                parsed_at=row.finished_at,  # parse_run.finished_at is when parsing completed
                status=row.processing_status.value if row.processing_status else "pending",
                chunks_created=row.chunks_created,
            )
            for row in rows
        ]

    async def remove_parsed_document(
        self,
        index_id: UUID,
        project_id: UUID,
        parse_run_id: UUID,
    ) -> IndexResponse:
        """Remove a specific parsed-document from an index.

        Raises:
            - NotFoundError: Index or parsed-document row not found
            - ValidationError: Index is currently processing
        """
        index = await self.index_repo.get_by_id(index_id, project_id)
        if not index:
            raise NotFoundError(f"Index {index_id} not found")

        if index.status == IndexStatus.processing:
            raise ValidationError("Cannot remove documents while index is processing")

        removed = await self.index_repo.remove_parsed_document(index_id, parse_run_id)
        if not removed:
            raise NotFoundError(
                f"Parsed document with parse_run_id={parse_run_id} not found in index"
            )

        return await self.get_index(index_id, project_id)

    async def get_processing_status(
        self,
        index_id: UUID,
        project_id: UUID
    ) -> IndexProcessingStatusResponse:
        """Get detailed processing status for an index.

        Raises:
        - NotFoundError: Index not found
        """
        index = await self.index_repo.get_by_id_with_documents(index_id, project_id)
        if not index:
            raise NotFoundError(f"Index {index_id} not found")

        stats = await self.index_repo.get_processing_stats(index_id)

        # Build document status list
        doc_statuses = []
        for index_doc in index.index_documents:
            doc_statuses.append(IndexDocumentStatusResponse(
                document_id=index_doc.document_id,
                status=index_doc.processing_status.value,
                chunks_created=index_doc.chunks_created,
                error_message=index_doc.error_message,
                processed_at=index_doc.processed_at,
            ))

        total = stats["total"]
        completed = stats["completed"]
        failed = stats["failed"]

        progress = 0
        if total > 0:
            progress = int((completed + failed) / total * 100)

        return IndexProcessingStatusResponse(
            status=index.status.value,
            total_documents=total,
            processed_documents=completed,
            failed_documents=failed,
            progress_percent=progress,
            started_at=index.updated_at if index.status != IndexStatus.created else None,
            documents=doc_statuses,
        )

    async def get_stats(self, index_id: UUID) -> IndexStats | None:
        """Get computed stats for an index."""
        stats = await self.chunk_repo.get_stats(index_id)
        if stats["total_chunks"] == 0:
            return None

        # Get embedding dimensions from index config
        index_result = await self.index_repo.session.execute(
            "SELECT config FROM indexes WHERE id = :id",
            {"id": str(index_id)}
        )
        # This is a simplified approach - in practice we'd get this from the config
        embedding_dimensions = 1536  # Default for text-embedding-3-small

        return IndexStats(
            total_chunks=stats["total_chunks"],
            total_documents=stats["total_documents"],
            avg_chunk_size_chars=stats["avg_chunk_size_chars"],
            avg_chunk_size_tokens=stats["avg_chunk_size_tokens"],
            min_chunk_size_chars=stats["min_chunk_size_chars"],
            max_chunk_size_chars=stats["max_chunk_size_chars"],
            total_tokens=stats["total_tokens"],
            embedding_dimensions=embedding_dimensions,
            processed_at=datetime.utcnow(),
        )
