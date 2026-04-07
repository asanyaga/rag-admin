"""Repository for extraction ground truth data access."""
from uuid import UUID
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.extraction_ground_truth import ExtractionGroundTruthSet, ExtractionGroundTruthItem


class ExtractionGroundTruthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # Ground Truth Set CRUD
    # ------------------------------------------------------------------

    async def create_set(
        self,
        project_id: UUID,
        extraction_schema_id: UUID,
        user_id: UUID,
        name: str,
        description: str | None,
    ) -> ExtractionGroundTruthSet:
        gt_set = ExtractionGroundTruthSet(
            project_id=project_id,
            extraction_schema_id=extraction_schema_id,
            created_by=user_id,
            name=name,
            description=description,
        )
        self.session.add(gt_set)
        await self.session.commit()
        await self.session.refresh(gt_set)
        return gt_set

    async def get_set_by_id(self, set_id: UUID) -> ExtractionGroundTruthSet | None:
        result = await self.session.execute(
            select(ExtractionGroundTruthSet)
            .options(selectinload(ExtractionGroundTruthSet.extraction_schema))
            .where(ExtractionGroundTruthSet.id == set_id)
        )
        return result.scalar_one_or_none()

    async def get_set_with_items(self, set_id: UUID) -> ExtractionGroundTruthSet | None:
        result = await self.session.execute(
            select(ExtractionGroundTruthSet)
            .options(
                selectinload(ExtractionGroundTruthSet.items)
                .selectinload(ExtractionGroundTruthItem.document),
                selectinload(ExtractionGroundTruthSet.extraction_schema),
            )
            .where(ExtractionGroundTruthSet.id == set_id)
        )
        return result.scalar_one_or_none()

    async def list_sets_by_project(
        self, project_id: UUID, extraction_schema_id: UUID | None = None
    ) -> list[ExtractionGroundTruthSet]:
        query = (
            select(ExtractionGroundTruthSet)
            .options(
                selectinload(ExtractionGroundTruthSet.items),
                selectinload(ExtractionGroundTruthSet.extraction_schema),
            )
            .where(ExtractionGroundTruthSet.project_id == project_id)
        )
        if extraction_schema_id:
            query = query.where(
                ExtractionGroundTruthSet.extraction_schema_id == extraction_schema_id
            )
        query = query.order_by(ExtractionGroundTruthSet.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_set(
        self,
        set_id: UUID,
        name: str | None = None,
        description: str | None = None,
    ) -> ExtractionGroundTruthSet | None:
        gt_set = await self.get_set_by_id(set_id)
        if not gt_set:
            return None
        if name is not None:
            gt_set.name = name
        if description is not None:
            gt_set.description = description
        await self.session.commit()
        await self.session.refresh(gt_set)
        return gt_set

    async def delete_set(self, set_id: UUID) -> bool:
        result = await self.session.execute(
            delete(ExtractionGroundTruthSet).where(
                ExtractionGroundTruthSet.id == set_id
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    # ------------------------------------------------------------------
    # Ground Truth Item CRUD
    # ------------------------------------------------------------------

    async def create_item(
        self,
        ground_truth_set_id: UUID,
        document_id: UUID,
        user_id: UUID,
        expected_data: dict,
        annotations: dict | None = None,
    ) -> ExtractionGroundTruthItem:
        item = ExtractionGroundTruthItem(
            ground_truth_set_id=ground_truth_set_id,
            document_id=document_id,
            created_by=user_id,
            expected_data=expected_data,
            annotations=annotations,
        )
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def get_item_by_id(self, item_id: UUID) -> ExtractionGroundTruthItem | None:
        result = await self.session.execute(
            select(ExtractionGroundTruthItem)
            .options(selectinload(ExtractionGroundTruthItem.document))
            .where(ExtractionGroundTruthItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def list_items_by_set(self, set_id: UUID) -> list[ExtractionGroundTruthItem]:
        result = await self.session.execute(
            select(ExtractionGroundTruthItem)
            .options(selectinload(ExtractionGroundTruthItem.document))
            .where(ExtractionGroundTruthItem.ground_truth_set_id == set_id)
            .order_by(ExtractionGroundTruthItem.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_item(
        self,
        item_id: UUID,
        expected_data: dict | None = None,
        annotations: dict | None = None,
    ) -> ExtractionGroundTruthItem | None:
        item = await self.get_item_by_id(item_id)
        if not item:
            return None
        if expected_data is not None:
            item.expected_data = expected_data
        if annotations is not None:
            item.annotations = annotations
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def delete_item(self, item_id: UUID) -> bool:
        result = await self.session.execute(
            delete(ExtractionGroundTruthItem).where(
                ExtractionGroundTruthItem.id == item_id
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def count_items(self, set_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(ExtractionGroundTruthItem)
            .where(ExtractionGroundTruthItem.ground_truth_set_id == set_id)
        )
        return result.scalar() or 0
