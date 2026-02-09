"""Service for golden set business logic."""
from uuid import UUID

from app.models import GoldenSetStatus
from app.repositories.golden_set_repository import GoldenSetRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.golden_set import (
    GoldenSetCreate,
    GoldenSetUpdate,
    GoldenSetResponse,
    GoldenSetDetailResponse,
    QueryCreate,
    QueryUpdate,
    QueryResponse,
    SourceCreate,
    SourceResponse,
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
        return GoldenSetResponse(
            id=gs.id,
            name=gs.name,
            description=gs.description,
            status=gs.status.value,
            query_count=0,
            document_count=0,
            created_by=gs.created_by,
            created_at=gs.created_at,
            updated_at=gs.updated_at,
        )

    async def get(self, gs_id: UUID, project_id: UUID) -> GoldenSetDetailResponse:
        gs = await self.gs_repo.get_with_queries(gs_id, project_id)
        if not gs:
            raise NotFoundError(f"Golden set {gs_id} not found")
        return self._to_detail_response(gs)

    async def list(self, project_id: UUID) -> list[GoldenSetResponse]:
        items = await self.gs_repo.list_by_project(project_id)
        results = []
        for gs in items:
            query_count = len(gs.queries) if gs.queries else 0
            doc_count = await self.gs_repo.count_documents(gs.id)
            results.append(GoldenSetResponse(
                id=gs.id,
                name=gs.name,
                description=gs.description,
                status=gs.status.value,
                query_count=query_count,
                document_count=doc_count,
                created_by=gs.created_by,
                created_at=gs.created_at,
                updated_at=gs.updated_at,
            ))
        return results

    async def update(
        self, gs_id: UUID, project_id: UUID, data: GoldenSetUpdate
    ) -> GoldenSetResponse:
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
        return GoldenSetResponse(
            id=gs.id,
            name=gs.name,
            description=gs.description,
            status=gs.status.value if isinstance(gs.status, GoldenSetStatus) else gs.status,
            query_count=query_count,
            document_count=doc_count,
            created_by=gs.created_by,
            created_at=gs.created_at,
            updated_at=gs.updated_at,
        )

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
        return QueryResponse(
            id=query.id,
            query_text=query.query_text,
            sources=[],
            created_at=query.created_at,
            updated_at=query.updated_at,
        )

    async def update_query(
        self, gs_id: UUID, project_id: UUID, query_id: UUID, data: QueryUpdate
    ) -> QueryResponse:
        gs = await self.gs_repo.get_by_id(gs_id, project_id)
        if not gs:
            raise NotFoundError(f"Golden set {gs_id} not found")
        query = await self.gs_repo.update_query(query_id, data.query_text)
        if not query:
            raise NotFoundError(f"Query {query_id} not found")
        # Reload with sources
        query = await self.gs_repo.get_query(query_id)
        return self._to_query_response(query)

    async def delete_query(
        self, gs_id: UUID, project_id: UUID, query_id: UUID
    ) -> None:
        gs = await self.gs_repo.get_by_id(gs_id, project_id)
        if not gs:
            raise NotFoundError(f"Golden set {gs_id} not found")
        deleted = await self.gs_repo.delete_query(query_id)
        if not deleted:
            raise NotFoundError(f"Query {query_id} not found")

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

    def _to_detail_response(self, gs) -> GoldenSetDetailResponse:
        queries = []
        doc_ids = set()
        for q in (gs.queries or []):
            queries.append(self._to_query_response(q))
            for s in (q.sources or []):
                doc_ids.add(s.document_id)

        return GoldenSetDetailResponse(
            id=gs.id,
            name=gs.name,
            description=gs.description,
            status=gs.status.value if isinstance(gs.status, GoldenSetStatus) else gs.status,
            query_count=len(queries),
            document_count=len(doc_ids),
            created_by=gs.created_by,
            created_at=gs.created_at,
            updated_at=gs.updated_at,
            queries=queries,
        )

    @staticmethod
    def _to_query_response(query) -> QueryResponse:
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
        return QueryResponse(
            id=query.id,
            query_text=query.query_text,
            sources=sources,
            created_at=query.created_at,
            updated_at=query.updated_at,
        )
