# backend/app/repositories/classification_run_repository.py
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cdm.classification import ClassifiedRegion
from app.cdm.models import ParsedDocument as CDMParsedDocument
from app.models.classification_region import ClassificationRegion as ClassificationRegionORM
from app.models.classification_run import ClassificationRun as ClassificationRunORM
from app.repositories.parsed_document_repository import ParsedDocumentRepository


@dataclass
class ClassificationRunCreate:
    parse_run_id: UUID
    document_id: UUID
    labels_requested: list[str]
    classifier_type: str
    classifier_config: dict


@dataclass
class AnnotatedBlock:
    block_id: str
    page_index: int
    role: str
    text: str
    markdown: str | None
    label: str | None


class ClassificationRunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: ClassificationRunCreate) -> ClassificationRunORM:
        run = ClassificationRunORM(
            parse_run_id=data.parse_run_id,
            document_id=data.document_id,
            labels_requested=data.labels_requested,
            classifier_type=data.classifier_type,
            classifier_config=data.classifier_config,
            status="pending",
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get(self, run_id: UUID) -> ClassificationRunORM | None:
        result = await self.session.execute(
            select(ClassificationRunORM).where(ClassificationRunORM.id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_for_document(self, document_id: UUID) -> list[ClassificationRunORM]:
        result = await self.session.execute(
            select(ClassificationRunORM)
            .where(ClassificationRunORM.document_id == document_id)
            .order_by(ClassificationRunORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_for_project(self, project_id: UUID) -> list[ClassificationRunORM]:
        from app.models.document import Document as DocumentORM
        result = await self.session.execute(
            select(ClassificationRunORM)
            .join(DocumentORM, ClassificationRunORM.document_id == DocumentORM.id)
            .where(DocumentORM.project_id == project_id)
            .order_by(ClassificationRunORM.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        run_id: UUID,
        status: str,
        error: str | None = None,
    ) -> None:
        run = await self.get(run_id)
        if run is None:
            return
        run.status = status
        if error is not None:
            run.error = error
        if status == "running":
            run.started_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def update_completed(
        self,
        run_id: UUID,
        input_tokens: int,
        output_tokens: int,
        duration_ms: int,
    ) -> None:
        run = await self.get(run_id)
        if run is None:
            return
        run.status = "completed"
        run.input_tokens = input_tokens
        run.output_tokens = output_tokens
        run.duration_ms = duration_ms
        run.finished_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def get_regions(self, run_id: UUID) -> list[ClassificationRegionORM]:
        result = await self.session.execute(
            select(ClassificationRegionORM)
            .where(ClassificationRegionORM.run_id == run_id)
            .order_by(ClassificationRegionORM.label, ClassificationRegionORM.page_start)
        )
        return list(result.scalars().all())

    async def save_regions(self, run_id: UUID, regions: list[ClassifiedRegion]) -> None:
        for region in regions:
            self.session.add(ClassificationRegionORM(
                run_id=run_id,
                label=region.label,
                page_start=region.page_start,
                page_end=region.page_end,
                block_ids=region.block_ids,
                confidence=region.confidence,
                reasoning=region.reasoning,
                source=region.source,
            ))
        await self.session.commit()

    async def get_annotated_blocks(self, run_id: UUID) -> list[AnnotatedBlock]:
        run = await self.get(run_id)
        if run is None:
            return []

        pd_repo = ParsedDocumentRepository(self.session)
        pd_orm = await pd_repo.get_by_run(run.parse_run_id)
        if pd_orm is None:
            return []

        doc = CDMParsedDocument.model_validate(pd_orm.content)
        regions = await self.get_regions(run_id)

        block_label: dict[str, str] = {}
        for region in regions:
            for block_id in region.block_ids:
                block_label[block_id] = region.label

        return [
            AnnotatedBlock(
                block_id=str(block.id),
                page_index=block.page_index,
                role=block.role.value if hasattr(block.role, "value") else block.role,
                text=block.text or "",
                markdown=block.markdown,
                label=block_label.get(str(block.id)),
            )
            for block in doc.blocks
        ]

    async def delete(self, run_id: UUID) -> None:
        run = await self.get(run_id)
        if run is not None:
            await self.session.delete(run)
            await self.session.commit()
