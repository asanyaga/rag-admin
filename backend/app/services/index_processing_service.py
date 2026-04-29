"""Service for processing indexes (chunking and embedding documents).

This service orchestrates the background task that:
1. Chunks documents according to index configuration
2. Generates embeddings using the configured provider
3. Stores chunks in the database
4. Updates index and document status
"""
import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IndexStatus, IndexDocumentStatus
from app.repositories.index_repository import IndexRepository
from app.repositories.chunk_repository import ChunkRepository
from app.schemas.index import IndexConfig, IndexStats
from app.services.chunking_service import ChunkingService, get_chunking_service
from app.services.markdown_chunking_service import (
    MarkdownChunkingService,
    get_markdown_chunking_service,
)
from app.services.embedding_provider import EmbeddingProviderRegistry
from app.services.provider_key_service import ProviderKeyService
from app.repositories.provider_key_repository import ProviderKeyRepository
from app.repositories.parsed_document_repository import ParsedDocumentRepository
from app.services.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class IndexProcessingService:
    """Service for processing indexes."""

    def __init__(
        self,
        session: AsyncSession,
        index_repo: IndexRepository,
        chunk_repo: ChunkRepository,
        provider_key_repo: ProviderKeyRepository
    ):
        self.session = session
        self.index_repo = index_repo
        self.chunk_repo = chunk_repo
        self.provider_key_service = ProviderKeyService(provider_key_repo)
        self.chunking_service = get_chunking_service()
        self.markdown_chunking_service = get_markdown_chunking_service()

    async def start_processing(
        self,
        index_id: UUID,
        project_id: UUID,
        user_id: UUID
    ) -> None:
        """Start processing an index.

        This method validates the index can be processed, then updates
        its status to 'processing'. The actual processing is done
        asynchronously via process_index().

        Raises:
        - NotFoundError: Index not found
        - ValidationError: Index cannot be processed (wrong status, no documents, no API key)
        """
        index = await self.index_repo.get_by_id_with_documents(index_id, project_id)
        if not index:
            raise NotFoundError(f"Index {index_id} not found")

        # Validate status
        if index.status not in [IndexStatus.created, IndexStatus.failed, IndexStatus.ready]:
            raise ValidationError(
                f"Cannot process index with status '{index.status.value}'. "
                "Only indexes in 'created', 'failed', or 'ready' status can be processed."
            )

        # Validate has documents
        if not index.index_documents:
            raise ValidationError("Index has no documents to process")

        # For ready indexes, ensure there are pending documents to process
        if index.status == IndexStatus.ready:
            has_pending = any(
                doc.processing_status == IndexDocumentStatus.pending
                for doc in index.index_documents
            )
            if not has_pending:
                raise ValidationError("No new documents to process")

        # Validate API key exists for the embedding provider
        config = IndexConfig.model_validate(index.config)
        if config.embedding_provider in ["openai", "voyage"]:
            has_key = await self.provider_key_service.has_key_for_provider(
                user_id=user_id,
                provider=config.embedding_provider,
                project_id=project_id
            )
            if not has_key:
                raise ValidationError(
                    f"No API key configured for embedding provider '{config.embedding_provider}'. "
                    "Please add your API key in settings."
                )

        # Validate CDM mode: all pending documents must have parse_run_id set
        if config.source_representation != "raw_text":
            for index_doc in index.index_documents:
                if index_doc.processing_status == IndexDocumentStatus.pending:
                    if not index_doc.parse_run_id:
                        raise ValidationError(
                            f"Document {index_doc.document_id} has no parse run set. "
                            "All documents require a parse run when source_representation "
                            "is not 'raw_text'."
                        )

        # Update status to processing
        await self.index_repo.update_status(index_id, IndexStatus.processing)

        # Reset any failed document statuses to pending for retry
        for index_doc in index.index_documents:
            if index_doc.processing_status == IndexDocumentStatus.failed:
                await self.index_repo.update_document_status(
                    index_id,
                    index_doc.document_id,
                    IndexDocumentStatus.pending
                )

    async def process_index(
        self,
        index_id: UUID,
        project_id: UUID,
        user_id: UUID
    ) -> None:
        """Process an index by chunking and embedding all documents.

        This is the main processing loop that should be run as a background task.
        """
        try:
            index = await self.index_repo.get_by_id_with_documents(index_id, project_id)
            if not index:
                logger.error(f"Index {index_id} not found during processing")
                return

            config = IndexConfig.model_validate(index.config)
            logger.info(f"Starting index processing for {index_id}")

            # Get embedding provider
            api_key = None
            if config.embedding_provider in ["openai", "voyage"]:
                api_key = await self.provider_key_service.get_key_for_provider(
                    user_id=user_id,
                    provider=config.embedding_provider,
                    project_id=project_id
                )

            embedding_provider = EmbeddingProviderRegistry.get_provider(
                provider_name=config.embedding_provider,
                api_key=api_key,
                model=config.embedding_model
            )

            # Get pending documents
            pending_docs = await self.index_repo.get_pending_documents(index_id)
            total_docs = len(pending_docs)
            processed_count = 0
            failed_count = 0

            for index_doc in pending_docs:
                document = index_doc.document
                doc_id = document.id

                try:
                    # Update document status to processing
                    await self.index_repo.update_document_status(
                        index_id, doc_id, IndexDocumentStatus.processing
                    )

                    logger.info(f"Processing document {doc_id} ({document.title})")

                    # Dispatch: source representation → chunks
                    if config.source_representation == "raw_text":
                        if not document.extracted_text:
                            raise ValueError("Document has no extracted text")
                        source_type = "raw_text"
                        doc_parse_run_id = None
                        chunks = self.chunking_service.chunk_text(
                            text=document.extracted_text,
                            config=config,
                            source_document_id=str(doc_id),
                            source_filename=document.source_metadata.get("filename"),
                            page_boundaries=document.processing_metadata.get("page_boundaries")
                                if document.processing_metadata else None,
                        )
                    elif config.source_representation == "full_text":
                        parsed_doc_repo = ParsedDocumentRepository(self.session)
                        parsed_doc = await parsed_doc_repo.get_by_run(index_doc.parse_run_id)
                        if not parsed_doc or not parsed_doc.full_text:
                            raise ValueError(
                                f"Parse run {index_doc.parse_run_id} did not produce full_text. "
                                "Re-parse with a configuration that outputs full text."
                            )
                        source_type = "full_text"
                        doc_parse_run_id = index_doc.parse_run_id
                        chunks = self.chunking_service.chunk_text(
                            text=parsed_doc.full_text,
                            config=config,
                            source_document_id=str(doc_id),
                            source_filename=document.source_metadata.get("filename"),
                            page_boundaries=document.processing_metadata.get("page_boundaries")
                                if document.processing_metadata else None,
                        )
                    elif config.source_representation == "full_markdown":
                        parsed_doc_repo = ParsedDocumentRepository(self.session)
                        parsed_doc = await parsed_doc_repo.get_by_run(index_doc.parse_run_id)
                        if not parsed_doc or not parsed_doc.full_markdown:
                            raise ValueError(
                                "Parse run did not produce full_markdown. "
                                "Re-parse the document with a configuration that outputs markdown."
                            )
                        source_type = "full_markdown"
                        doc_parse_run_id = index_doc.parse_run_id
                        chunks = self.markdown_chunking_service.chunk_markdown(
                            markdown=parsed_doc.full_markdown,
                            config=config,
                            source_document_id=str(doc_id),
                            source_filename=document.source_metadata.get("filename"),
                        )
                    else:
                        raise NotImplementedError(
                            f"source_representation '{config.source_representation}' not yet supported"
                        )

                    if not chunks:
                        raise ValueError("Document produced no chunks")

                    logger.info(f"Document {doc_id} split into {len(chunks)} chunks")

                    # Generate embeddings
                    chunk_texts = [c.content for c in chunks]
                    embeddings = await embedding_provider.embed_texts(chunk_texts)

                    logger.info(f"Generated {len(embeddings)} embeddings for document {doc_id}")

                    # Prepare chunk data for batch insert
                    chunk_data = []
                    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                        chunk_data.append({
                            "index_id": index_id,
                            "document_id": doc_id,
                            "content": chunk.content,
                            "embedding": embedding,
                            "chunk_index": chunk.chunk_index,
                            "token_count": chunk.token_count,
                            "char_count": chunk.char_count,
                            "chunk_metadata": chunk.metadata,
                            "index_version": index.version + 1,
                            "parse_run_id": str(doc_parse_run_id) if doc_parse_run_id else None,
                            "source_type": source_type,
                        })

                    # Store chunks
                    await self.chunk_repo.create_batch(chunk_data)

                    # Update document status to completed
                    await self.index_repo.update_document_status(
                        index_id,
                        doc_id,
                        IndexDocumentStatus.completed,
                        chunks_created=len(chunks)
                    )

                    processed_count += 1
                    logger.info(
                        f"Completed document {doc_id} "
                        f"({processed_count}/{total_docs})"
                    )

                except Exception as e:
                    logger.error(f"Failed to process document {doc_id}: {e}")
                    await self.index_repo.update_document_status(
                        index_id,
                        doc_id,
                        IndexDocumentStatus.failed,
                        error_message=str(e)
                    )
                    failed_count += 1

            # Calculate and store stats
            stats_dict = await self.chunk_repo.get_stats(index_id)
            embedding_dimensions = embedding_provider.get_dimensions()

            stats = IndexStats(
                total_chunks=stats_dict["total_chunks"],
                total_documents=stats_dict["total_documents"],
                avg_chunk_size_chars=stats_dict["avg_chunk_size_chars"],
                avg_chunk_size_tokens=stats_dict["avg_chunk_size_tokens"],
                min_chunk_size_chars=stats_dict["min_chunk_size_chars"],
                max_chunk_size_chars=stats_dict["max_chunk_size_chars"],
                total_tokens=stats_dict["total_tokens"],
                embedding_dimensions=embedding_dimensions,
                processed_at=datetime.utcnow(),
            )
            await self.index_repo.update_stats(index_id, stats.model_dump(mode="json"))

            # Increment version and write audit event
            await self.index_repo.increment_version(index_id)
            await self.index_repo.write_index_event(
                index_id=index_id,
                version=index.version + 1,
                config_snapshot=config.model_dump(mode="json"),
                document_bindings={
                    str(doc.document_id): str(doc.parse_run_id) if doc.parse_run_id else None
                    for doc in index.index_documents
                },
                triggered_by=user_id,
            )

            # Determine final status
            if failed_count == total_docs:
                # All documents failed
                await self.index_repo.update_status(
                    index_id,
                    IndexStatus.failed,
                    error_message="All documents failed to process"
                )
            elif failed_count > 0:
                # Some documents failed, but index is still usable
                await self.index_repo.update_status(
                    index_id,
                    IndexStatus.ready,
                    error_message=f"{failed_count} of {total_docs} documents failed"
                )
            else:
                # All documents processed successfully
                await self.index_repo.update_status(index_id, IndexStatus.ready)

            logger.info(
                f"Index {index_id} processing complete. "
                f"Processed: {processed_count}, Failed: {failed_count}"
            )

        except Exception as e:
            logger.error(f"Index processing failed: {e}")
            await self.index_repo.update_status(
                index_id,
                IndexStatus.failed,
                error_message=str(e)
            )
            raise


async def process_index_background(
    session: AsyncSession,
    index_id: UUID,
    project_id: UUID,
    user_id: UUID
) -> None:
    """Background task function for processing an index.

    This function is designed to be called from FastAPI BackgroundTasks.
    """
    from app.repositories.provider_key_repository import ProviderKeyRepository

    index_repo = IndexRepository(session)
    chunk_repo = ChunkRepository(session)
    provider_key_repo = ProviderKeyRepository(session)

    service = IndexProcessingService(
        session=session,
        index_repo=index_repo,
        chunk_repo=chunk_repo,
        provider_key_repo=provider_key_repo
    )

    await service.process_index(index_id, project_id, user_id)
