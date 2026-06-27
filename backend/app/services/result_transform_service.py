# backend/app/services/result_transform_service.py
"""Service: run an ExtractionResultTransform over selected results; persist derived results."""
from __future__ import annotations

from uuid import UUID

from app.services.exceptions import NotFoundError
from app.services.extraction.transforms.base import TransformInput
from app.services.extraction.transforms.registry import build_transform

_RECORDS_KEY = "records"


class ResultTransformService:
    def __init__(self, result_repo):
        self.result_repo = result_repo

    async def _load_inputs(self, source_result_ids: list[UUID]) -> list[tuple[object, TransformInput]]:
        loaded = []
        for rid in source_result_ids:
            result = await self.result_repo.get_by_id(rid)
            if result is None:
                raise NotFoundError(f"Extraction result {rid} not found")
            rows = (result.structured_data or {}).get(_RECORDS_KEY, [])
            loaded.append((result, TransformInput(rows=rows, source_result_id=str(rid))))
        return loaded

    async def preview(self, source_result_ids: list[UUID], transform_type: str, config: dict) -> dict:
        loaded = await self._load_inputs(source_result_ids)
        out = build_transform(transform_type).apply([ti for _, ti in loaded], config)
        return {"rows": out.rows, "flags": out.flags}

    async def apply(self, source_result_ids: list[UUID], transform_type: str, config: dict, user_id: UUID, target_schema_id: UUID | None = None):
        if not source_result_ids:
            raise ValueError("source_result_ids must not be empty")
        loaded = await self._load_inputs(source_result_ids)
        primary, _ = loaded[0]
        out = build_transform(transform_type).apply([ti for _, ti in loaded], config)

        created = await self.result_repo.create(
            document_id=primary.document_id,
            extraction_schema_id=target_schema_id or primary.extraction_schema_id,
            schema_definition_snapshot=primary.schema_definition_snapshot,
            extraction_method="transform",
            created_by=user_id,
            config={"transformType": transform_type, "config": config},
        )
        return await self.result_repo.update_result(
            result_id=created.id,
            structured_data={_RECORDS_KEY: out.rows},
            extraction_metadata={
                "flags": out.flags,
                "lineage": {
                    "sourceResultIds": [str(x) for x in source_result_ids],
                    "transform": {"type": transform_type, "config": config},
                },
            },
        )
