"""Repository for golden set data access."""
from uuid import UUID
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import GoldenSet, GoldenSetQuery, GoldenSetSource


class GoldenSetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # Golden Set CRUD
    # ------------------------------------------------------------------

    async def create(
        self,
        project_id: UUID,
        user_id: UUID,
        name: str,
        description: str | None,
    ) -> GoldenSet:
        gs = GoldenSet(
            project_id=project_id,
            created_by=user_id,
            name=name,
            description=description,
        )
        self.session.add(gs)
        await self.session.commit()
        await self.session.refresh(gs)
        return gs

    async def get_by_id(self, gs_id: UUID, project_id: UUID) -> GoldenSet | None:
        result = await self.session.execute(
            select(GoldenSet).where(
                GoldenSet.id == gs_id,
                GoldenSet.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_with_queries(self, gs_id: UUID, project_id: UUID) -> GoldenSet | None:
        """Get golden set with queries and sources eagerly loaded."""
        result = await self.session.execute(
            select(GoldenSet)
            .options(
                selectinload(GoldenSet.queries)
                .selectinload(GoldenSetQuery.sources)
                .selectinload(GoldenSetSource.document)
            )
            .where(
                GoldenSet.id == gs_id,
                GoldenSet.project_id == project_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: UUID) -> list[GoldenSet]:
        result = await self.session.execute(
            select(GoldenSet)
            .options(selectinload(GoldenSet.queries))
            .where(GoldenSet.project_id == project_id)
            .order_by(GoldenSet.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(
        self,
        gs_id: UUID,
        project_id: UUID,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
    ) -> GoldenSet | None:
        gs = await self.get_by_id(gs_id, project_id)
        if not gs:
            return None
        if name is not None:
            gs.name = name
        if description is not None:
            gs.description = description
        if status is not None:
            gs.status = status
        await self.session.commit()
        await self.session.refresh(gs)
        return gs

    async def delete(self, gs_id: UUID, project_id: UUID) -> bool:
        result = await self.session.execute(
            delete(GoldenSet).where(
                GoldenSet.id == gs_id,
                GoldenSet.project_id == project_id,
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    # ------------------------------------------------------------------
    # Query CRUD
    # ------------------------------------------------------------------

    async def add_query(self, golden_set_id: UUID, query_text: str) -> GoldenSetQuery:
        query = GoldenSetQuery(
            golden_set_id=golden_set_id,
            query_text=query_text,
        )
        self.session.add(query)
        await self.session.commit()
        await self.session.refresh(query)
        return query

    async def get_query(self, query_id: UUID) -> GoldenSetQuery | None:
        result = await self.session.execute(
            select(GoldenSetQuery)
            .options(
                selectinload(GoldenSetQuery.sources)
                .selectinload(GoldenSetSource.document)
            )
            .where(GoldenSetQuery.id == query_id)
        )
        return result.scalar_one_or_none()

    async def update_query(self, query_id: UUID, query_text: str) -> GoldenSetQuery | None:
        result = await self.session.execute(
            select(GoldenSetQuery).where(GoldenSetQuery.id == query_id)
        )
        query = result.scalar_one_or_none()
        if not query:
            return None
        query.query_text = query_text
        await self.session.commit()
        await self.session.refresh(query)
        return query

    async def delete_query(self, query_id: UUID) -> bool:
        result = await self.session.execute(
            delete(GoldenSetQuery).where(GoldenSetQuery.id == query_id)
        )
        await self.session.commit()
        return result.rowcount > 0

    # ------------------------------------------------------------------
    # Source CRUD
    # ------------------------------------------------------------------

    async def add_source(
        self,
        query_id: UUID,
        document_id: UUID,
        locator: dict,
    ) -> GoldenSetSource:
        source = GoldenSetSource(
            query_id=query_id,
            document_id=document_id,
            locator=locator,
        )
        self.session.add(source)
        await self.session.commit()
        await self.session.refresh(source)
        return source

    async def delete_source(self, source_id: UUID) -> bool:
        result = await self.session.execute(
            delete(GoldenSetSource).where(GoldenSetSource.id == source_id)
        )
        await self.session.commit()
        return result.rowcount > 0

    # ------------------------------------------------------------------
    # Counts
    # ------------------------------------------------------------------

    async def count_queries(self, golden_set_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(GoldenSetQuery)
            .where(GoldenSetQuery.golden_set_id == golden_set_id)
        )
        return result.scalar() or 0

    async def count_documents(self, golden_set_id: UUID) -> int:
        """Count distinct documents referenced across all sources."""
        result = await self.session.execute(
            select(func.count(func.distinct(GoldenSetSource.document_id)))
            .select_from(GoldenSetSource)
            .join(GoldenSetQuery, GoldenSetSource.query_id == GoldenSetQuery.id)
            .where(GoldenSetQuery.golden_set_id == golden_set_id)
        )
        return result.scalar() or 0
