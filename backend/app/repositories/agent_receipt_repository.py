"""Repository for agent receipt data access."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_receipt import AgentReceipt, AgentReceiptStatus


class AgentReceiptRepository:
    """Repository for agent receipt data access."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        project_id: UUID,
        document_id: UUID,
        extraction_schema_id: UUID,
        created_by: UUID,
    ) -> AgentReceipt:
        receipt = AgentReceipt(
            project_id=project_id,
            document_id=document_id,
            extraction_schema_id=extraction_schema_id,
            created_by=created_by,
            status=AgentReceiptStatus.pending,
        )
        self.session.add(receipt)
        await self.session.commit()
        await self.session.refresh(receipt)
        return receipt

    async def get_by_id(self, receipt_id: UUID) -> AgentReceipt | None:
        result = await self.session.execute(
            select(AgentReceipt).where(AgentReceipt.id == receipt_id)
        )
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: UUID) -> list[AgentReceipt]:
        result = await self.session.execute(
            select(AgentReceipt)
            .where(AgentReceipt.project_id == project_id)
            .order_by(AgentReceipt.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        receipt_id: UUID,
        status: AgentReceiptStatus,
        status_message: str | None = None,
    ) -> AgentReceipt | None:
        receipt = await self.get_by_id(receipt_id)
        if not receipt:
            return None
        receipt.status = status
        receipt.status_message = status_message
        await self.session.commit()
        await self.session.refresh(receipt)
        return receipt

    async def update_extracted_data(
        self,
        receipt_id: UUID,
        extracted_data: dict,
        thread_id: str,
    ) -> AgentReceipt | None:
        receipt = await self.get_by_id(receipt_id)
        if not receipt:
            return None
        receipt.extracted_data = extracted_data
        receipt.thread_id = thread_id
        receipt.status = AgentReceiptStatus.reviewing
        await self.session.commit()
        await self.session.refresh(receipt)
        return receipt

    async def update_reviewed_data(
        self,
        receipt_id: UUID,
        reviewed_data: dict | None,
        status: AgentReceiptStatus,
    ) -> AgentReceipt | None:
        receipt = await self.get_by_id(receipt_id)
        if not receipt:
            return None
        receipt.reviewed_data = reviewed_data
        receipt.status = status
        await self.session.commit()
        await self.session.refresh(receipt)
        return receipt
