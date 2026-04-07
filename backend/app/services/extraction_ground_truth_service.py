"""Service for extraction ground truth management."""
import logging
from uuid import UUID

from app.repositories.extraction_ground_truth_repository import ExtractionGroundTruthRepository
from app.schemas.extraction_ground_truth import (
    GroundTruthSetCreate,
    GroundTruthSetUpdate,
    GroundTruthSetResponse,
    GroundTruthItemCreate,
    GroundTruthItemUpdate,
    GroundTruthItemResponse,
    BulkImportRequest,
    BulkImportResponse,
)
from app.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


class ExtractionGroundTruthService:
    def __init__(self, repo: ExtractionGroundTruthRepository):
        self.repo = repo

    # ------------------------------------------------------------------
    # Sets
    # ------------------------------------------------------------------

    async def create_set(
        self, project_id: UUID, user_id: UUID, data: GroundTruthSetCreate
    ) -> GroundTruthSetResponse:
        gt_set = await self.repo.create_set(
            project_id=project_id,
            extraction_schema_id=data.extraction_schema_id,
            user_id=user_id,
            name=data.name,
            description=data.description,
        )
        gt_set = await self.repo.get_set_by_id(gt_set.id)
        return self._set_to_response(gt_set, 0)

    async def get_set(self, set_id: UUID) -> GroundTruthSetResponse:
        gt_set = await self.repo.get_set_by_id(set_id)
        if not gt_set:
            raise NotFoundError(f"Ground truth set {set_id} not found")
        item_count = await self.repo.count_items(set_id)
        return self._set_to_response(gt_set, item_count)

    async def list_sets(
        self, project_id: UUID, extraction_schema_id: UUID | None = None
    ) -> list[GroundTruthSetResponse]:
        sets = await self.repo.list_sets_by_project(project_id, extraction_schema_id)
        return [
            self._set_to_response(s, len(s.items) if s.items else 0)
            for s in sets
        ]

    async def update_set(
        self, set_id: UUID, data: GroundTruthSetUpdate
    ) -> GroundTruthSetResponse:
        gt_set = await self.repo.update_set(
            set_id=set_id,
            name=data.name,
            description=data.description,
        )
        if not gt_set:
            raise NotFoundError(f"Ground truth set {set_id} not found")
        item_count = await self.repo.count_items(set_id)
        return self._set_to_response(gt_set, item_count)

    async def delete_set(self, set_id: UUID) -> None:
        deleted = await self.repo.delete_set(set_id)
        if not deleted:
            raise NotFoundError(f"Ground truth set {set_id} not found")

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------

    async def create_item(
        self, set_id: UUID, user_id: UUID, data: GroundTruthItemCreate
    ) -> GroundTruthItemResponse:
        # Verify set exists
        gt_set = await self.repo.get_set_by_id(set_id)
        if not gt_set:
            raise NotFoundError(f"Ground truth set {set_id} not found")

        item = await self.repo.create_item(
            ground_truth_set_id=set_id,
            document_id=data.document_id,
            user_id=user_id,
            expected_data=data.expected_data,
            annotations=data.annotations,
        )
        item = await self.repo.get_item_by_id(item.id)
        return self._item_to_response(item)

    async def bulk_create_items(
        self, set_id: UUID, user_id: UUID, data: BulkImportRequest
    ) -> BulkImportResponse:
        gt_set = await self.repo.get_set_by_id(set_id)
        if not gt_set:
            raise NotFoundError(f"Ground truth set {set_id} not found")

        created = 0
        errors = []
        for i, item_data in enumerate(data.items):
            try:
                await self.repo.create_item(
                    ground_truth_set_id=set_id,
                    document_id=item_data.document_id,
                    user_id=user_id,
                    expected_data=item_data.expected_data,
                    annotations=item_data.annotations,
                )
                created += 1
            except Exception as e:
                errors.append(f"Item {i}: {str(e)}")

        return BulkImportResponse(created=created, errors=errors)

    async def get_item(self, item_id: UUID) -> GroundTruthItemResponse:
        item = await self.repo.get_item_by_id(item_id)
        if not item:
            raise NotFoundError(f"Ground truth item {item_id} not found")
        return self._item_to_response(item)

    async def list_items(self, set_id: UUID) -> list[GroundTruthItemResponse]:
        items = await self.repo.list_items_by_set(set_id)
        return [self._item_to_response(item) for item in items]

    async def update_item(
        self, item_id: UUID, data: GroundTruthItemUpdate
    ) -> GroundTruthItemResponse:
        item = await self.repo.update_item(
            item_id=item_id,
            expected_data=data.expected_data,
            annotations=data.annotations,
        )
        if not item:
            raise NotFoundError(f"Ground truth item {item_id} not found")
        return self._item_to_response(item)

    async def delete_item(self, item_id: UUID) -> None:
        deleted = await self.repo.delete_item(item_id)
        if not deleted:
            raise NotFoundError(f"Ground truth item {item_id} not found")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _set_to_response(
        gt_set, item_count: int
    ) -> GroundTruthSetResponse:
        schema_name = ""
        if gt_set.extraction_schema:
            schema_name = gt_set.extraction_schema.name
        return GroundTruthSetResponse(
            id=gt_set.id,
            project_id=gt_set.project_id,
            extraction_schema_id=gt_set.extraction_schema_id,
            extraction_schema_name=schema_name,
            name=gt_set.name,
            description=gt_set.description,
            item_count=item_count,
            created_by=gt_set.created_by,
            created_at=gt_set.created_at,
            updated_at=gt_set.updated_at,
        )

    @staticmethod
    def _item_to_response(item) -> GroundTruthItemResponse:
        doc_title = ""
        if item.document:
            doc_title = item.document.title or ""
        return GroundTruthItemResponse(
            id=item.id,
            ground_truth_set_id=item.ground_truth_set_id,
            document_id=item.document_id,
            document_title=doc_title,
            expected_data=item.expected_data,
            annotations=item.annotations,
            created_by=item.created_by,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
