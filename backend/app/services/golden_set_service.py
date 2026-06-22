"""Service for golden set business logic."""
from uuid import UUID

from app.models import GoldenSetStatus
from app.models.golden_set import GenerationStatus, ReviewStatus
from app.repositories.golden_set_repository import GoldenSetRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.golden_set import (
    GoldenSetCreate,
    GoldenSetUpdate,
    GoldenSetResponse,
    GoldenSetDetailResponse,
    GenerationProgress,
    QueryCreate,
    QueryUpdate,
    QueryResponse,
    SourceCreate,
    SourceResponse,
    BulkReviewRequest,
)
from app.services.exceptions import NotFoundError, ValidationError


class GoldenSetService:
    def __init__(
        self,
        golden_set_repo: GoldenSetRepository,
        document_repo: DocumentRepository,
    ):
        self.gs_repo = golden_set_repo
        self.doc_repo = document_repo

    # ------------------------------------------------------------------
    # Golden Set CRUD
    # ------------------------------------------------------------------

    async def create(
        self, project_id: UUID, user_id: UUID, data: GoldenSetCreate
    ) -> GoldenSetResponse:
        gs = await self.gs_repo.create(
            project_id=project_id,
            user_id=user_id,
            name=data.name,
            description=data.description,
        )
        return self._to_list_response(gs, query_count=0, doc_count=0)

    async def get(self, gs_id: UUID, project_id: UUID) -> GoldenSetDetailResponse:
        gs = await self.gs_repo.get_with_queries(gs_id, project_id)
        if not gs:
            raise NotFoundError(f"Golden set {gs_id} not found")
        query_ids_with_results = await self.gs_repo.get_query_ids_with_results(gs_id)
        return self._to_detail_response(gs, query_ids_with_results)

    async def list(self, project_id: UUID) -> list[GoldenSetResponse]:
        items = await self.gs_repo.list_by_project(project_id)
        results = []
        for gs in items:
            query_count = len(gs.queries) if gs.queries else 0
            doc_count = await self.gs_repo.count_documents(gs.id)
            results.append(self._to_list_response(gs, query_count, doc_count))
        return results

    async def update(
        self, gs_id: UUID, project_id: UUID, data: GoldenSetUpdate
    ) -> GoldenSetResponse:
        # Save gate: prevent completing while pending queries exist
        if data.status == "completed":
            pending_count = await self.gs_repo.count_pending_queries(gs_id)
            if pending_count > 0:
                raise ValidationError(
                    f"Cannot complete golden set: {pending_count} queries still pending review"
                )

        gs = await self.gs_repo.update(
            gs_id, project_id,
            name=data.name,
            description=data.description,
            status=data.status,
        )
        if not gs:
            raise NotFoundError(f"Golden set {gs_id} not found")
        query_count = await self.gs_repo.count_queries(gs.id)
        doc_count = await self.gs_repo.count_documents(gs.id)
        return self._to_list_response(gs, query_count, doc_count)

    async def delete(self, gs_id: UUID, project_id: UUID) -> None:
        deleted = await self.gs_repo.delete(gs_id, project_id)
        if not deleted:
            raise NotFoundError(f"Golden set {gs_id} not found")

    # ------------------------------------------------------------------
    # Query CRUD
    # ------------------------------------------------------------------

    async def add_query(
        self, gs_id: UUID, project_id: UUID, data: QueryCreate
    ) -> QueryResponse:
        gs = await self.gs_repo.get_by_id(gs_id, project_id)
        if not gs:
            raise NotFoundError(f"Golden set {gs_id} not found")
        query = await self.gs_repo.add_query(gs_id, data.query_text)
        # Reload with sources eagerly loaded to avoid async lazy-load error
        query = await self.gs_repo.get_query(query.id)
        return self._to_query_response(query)

    async def update_query(
        self, gs_id: UUID, project_id: UUID, query_id: UUID, data: QueryUpdate
    ) -> QueryResponse:
        gs = await self.gs_repo.get_by_id(gs_id, project_id)
        if not gs:
            raise NotFoundError(f"Golden set {gs_id} not found")

        # Determine review_status update
        review_status = data.review_status
        if data.query_text is not None:
            # Block text edits on queries that have run results — changing the text
            # would silently corrupt all historical metrics that reference this query.
            if await self.gs_repo.query_has_results(query_id):
                raise ValidationError(
                    "Query text cannot be modified: this query has evaluation run results referencing it"
                )
            # Auto-set "edited" when query text changes on an auto-generated query
            existing = await self.gs_repo.get_query(query_id)
            if existing and existing.source_method.value == "auto_generated" and review_status is None:
                review_status = "edited"

        # Build kwargs — only pass reference_answer if it was explicitly provided
        update_kwargs: dict = {
            "query_text": data.query_text,
            "review_status": review_status,
        }
        if "reference_answer" in data.model_fields_set:
            update_kwargs["reference_answer"] = data.reference_answer

        query = await self.gs_repo.update_query(query_id, **update_kwargs)
        if not query:
            raise NotFoundError(f"Query {query_id} not found")
        # Reload with sources
        query = await self.gs_repo.get_query(query_id)
        has_results = await self.gs_repo.query_has_results(query_id)
        return self._to_query_response(query, has_results=has_results)

    async def delete_query(
        self, gs_id: UUID, project_id: UUID, query_id: UUID
    ) -> None:
        gs = await self.gs_repo.get_by_id(gs_id, project_id)
        if not gs:
            raise NotFoundError(f"Golden set {gs_id} not found")
        # Block deletion of queries with run results — the FK CASCADE would silently
        # destroy all evaluation data for this query across every run.
        if await self.gs_repo.query_has_results(query_id):
            raise ValidationError(
                "Query cannot be deleted: it has evaluation run results referencing it"
            )
        deleted = await self.gs_repo.delete_query(query_id)
        if not deleted:
            raise NotFoundError(f"Query {query_id} not found")

    # ------------------------------------------------------------------
    # Bulk Review
    # ------------------------------------------------------------------

    async def bulk_review(
        self, gs_id: UUID, project_id: UUID, data: BulkReviewRequest
    ) -> int:
        """Bulk accept or reject queries. Returns count updated."""
        gs = await self.gs_repo.get_by_id(gs_id, project_id)
        if not gs:
            raise NotFoundError(f"Golden set {gs_id} not found")

        review_status = "accepted" if data.action == "accept" else "rejected"
        count = await self.gs_repo.bulk_update_review_status(data.query_ids, review_status)
        return count

    # ------------------------------------------------------------------
    # Source CRUD
    # ------------------------------------------------------------------

    async def add_source(
        self,
        gs_id: UUID,
        project_id: UUID,
        query_id: UUID,
        user_id: UUID,
        data: SourceCreate,
    ) -> SourceResponse:
        gs = await self.gs_repo.get_by_id(gs_id, project_id)
        if not gs:
            raise NotFoundError(f"Golden set {gs_id} not found")
        query = await self.gs_repo.get_query(query_id)
        if not query or query.golden_set_id != gs_id:
            raise NotFoundError(f"Query {query_id} not found")

        # Validate document exists and belongs to project
        doc = await self.doc_repo.get_by_id(data.document_id, user_id)
        if not doc or doc.project_id != project_id:
            raise ValidationError(f"Document {data.document_id} not found in project")

        source = await self.gs_repo.add_source(
            query_id=query_id,
            document_id=data.document_id,
            locator=data.locator.model_dump(),
        )

        doc_name = doc.source_metadata.get("filename") or doc.title or "Unknown"
        return SourceResponse(
            id=source.id,
            document_id=source.document_id,
            document_name=doc_name,
            locator=source.locator,
            created_at=source.created_at,
        )

    async def delete_source(
        self, gs_id: UUID, project_id: UUID, query_id: UUID, source_id: UUID
    ) -> None:
        gs = await self.gs_repo.get_by_id(gs_id, project_id)
        if not gs:
            raise NotFoundError(f"Golden set {gs_id} not found")
        deleted = await self.gs_repo.delete_source(source_id)
        if not deleted:
            raise NotFoundError(f"Source {source_id} not found")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _to_list_response(self, gs, query_count: int, doc_count: int) -> GoldenSetResponse:
        gen_progress = None
        if gs.generation_progress:
            gen_progress = GenerationProgress(
                total_windows=gs.generation_progress.get("totalWindows", 0),
                completed_windows=gs.generation_progress.get("completedWindows", 0),
                error_message=gs.generation_progress.get("errorMessage"),
            )

        return GoldenSetResponse(
            id=gs.id,
            name=gs.name,
            description=gs.description,
            status=gs.status.value if isinstance(gs.status, GoldenSetStatus) else gs.status,
            query_count=query_count,
            document_count=doc_count,
            generation_status=gs.generation_status.value if gs.generation_status else None,
            generation_progress=gen_progress,
            generation_config=gs.generation_config,
            created_by=gs.created_by,
            created_at=gs.created_at,
            updated_at=gs.updated_at,
        )

    def _to_detail_response(self, gs, query_ids_with_results: set | None = None) -> GoldenSetDetailResponse:
        if query_ids_with_results is None:
            query_ids_with_results = set()
        queries = []
        doc_ids = set()
        for q in (gs.queries or []):
            queries.append(self._to_query_response(q, has_results=q.id in query_ids_with_results))
            for s in (q.sources or []):
                doc_ids.add(s.document_id)

        gen_progress = None
        if gs.generation_progress:
            gen_progress = GenerationProgress(
                total_windows=gs.generation_progress.get("totalWindows", 0),
                completed_windows=gs.generation_progress.get("completedWindows", 0),
                error_message=gs.generation_progress.get("errorMessage"),
            )

        return GoldenSetDetailResponse(
            id=gs.id,
            name=gs.name,
            description=gs.description,
            status=gs.status.value if isinstance(gs.status, GoldenSetStatus) else gs.status,
            query_count=len(queries),
            document_count=len(doc_ids),
            generation_status=gs.generation_status.value if gs.generation_status else None,
            generation_progress=gen_progress,
            generation_config=gs.generation_config,
            created_by=gs.created_by,
            created_at=gs.created_at,
            updated_at=gs.updated_at,
            queries=queries,
        )

    @staticmethod
    def _to_query_response(query, has_results: bool = False) -> QueryResponse:
        sources = []
        for s in (query.sources or []):
            doc = s.document
            doc_name = ""
            if doc:
                doc_name = doc.source_metadata.get("filename") or doc.title or "Unknown"
            sources.append(SourceResponse(
                id=s.id,
                document_id=s.document_id,
                document_name=doc_name,
                locator=s.locator,
                created_at=s.created_at,
            ))

        source_method = query.source_method.value if hasattr(query.source_method, 'value') else str(query.source_method)
        review_status = query.review_status.value if hasattr(query.review_status, 'value') else str(query.review_status)

        return QueryResponse(
            id=query.id,
            query_text=query.query_text,
            source_method=source_method,
            review_status=review_status,
            reasoning=query.reasoning,
            question_type=query.question_type,
            reference_answer=query.reference_answer,
            has_results=has_results,
            sources=sources,
            created_at=query.created_at,
            updated_at=query.updated_at,
        )
