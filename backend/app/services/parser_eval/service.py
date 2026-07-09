"""Service orchestrating parser-eval CRUD and run execution (canonical model)."""
from __future__ import annotations

from uuid import UUID

from app.models.parser_eval import (
    ParserEvalDimension, ParserEvalSourceMethod, ParserEvalReviewStatus,
)
from app.repositories.parser_eval_repository import ParserEvalRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.schemas.parser_eval import (
    BootstrapTableRequest, CaseCreate, CaseDetailResponse, CaseExpectedUpdate, CaseResponse,
    DatasetCreate, DatasetResponse, RunCreate, RunResponse, ResultResponse,
)
from app.services.exceptions import ConflictError, NotFoundError, ValidationError
from app.services.parser_eval.capture import capture
from app.services.parser_eval.engine import run_evaluation
from app.services.parser_eval.table_html import extract_cdm_tables, sanitize_table_html


class ParserEvalService:
    def __init__(self, repo: ParserEvalRepository, source_doc_repo: SourceDocumentRepository,
                 parsing_service, storage):
        self.repo = repo
        self.source_doc_repo = source_doc_repo
        self.parsing_service = parsing_service
        self.storage = storage

    # --- cases ---
    async def create_case(self, project_id: UUID, user_id: UUID, data: CaseCreate) -> CaseResponse:
        source = await self.source_doc_repo.get(data.source_document_id)
        if source is None:
            raise NotFoundError(f"Source document {data.source_document_id} not found")
        case = await self.repo.create_case(
            project_id, data.source_document_id, ParserEvalDimension(data.dimension),
            data.expected, user_id,
            source_method=ParserEvalSourceMethod(data.source_method or "human"),
            review_status=ParserEvalReviewStatus(data.review_status or "draft"))
        return CaseResponse.model_validate(case)

    async def list_cases(self, project_id: UUID) -> list[CaseResponse]:
        return [CaseResponse.model_validate(c) for c in await self.repo.list_cases(project_id)]

    async def get_case(self, case_id: UUID) -> CaseDetailResponse:
        case = await self.repo.get_case(case_id)
        if case is None:
            raise NotFoundError(f"Parser eval case {case_id} not found")
        return CaseDetailResponse.model_validate(case)

    async def bootstrap_table_case(self, project_id: UUID, user_id: UUID,
                                   data: BootstrapTableRequest) -> CaseDetailResponse:
        source = await self.source_doc_repo.get(data.source_document_id)
        if source is None:
            raise NotFoundError(f"Source document {data.source_document_id} not found")
        existing = await self.repo.get_case_by_doc_dimension(
            data.source_document_id, ParserEvalDimension.table)
        if existing is not None:
            raise ConflictError("A table case already exists for this document")

        cdm, _cost, _latency = await capture(
            self.parsing_service, self.storage,
            source_document_id=str(data.source_document_id), storage_uri=source.storage_uri,
            filename=source.filename, mime_type=source.mime_type, parser=data.adapter,
            project_id=project_id, config=data.config or {})
        if cdm is None:
            raise ValidationError(
                "Bootstrap parse failed — the chosen parser could not parse this document")

        expected = {"tables": [{"page": page_index + 1, "html": html}
                               for page_index, html in extract_cdm_tables(cdm)]}
        case = await self.repo.create_case(
            project_id, data.source_document_id, ParserEvalDimension.table, expected, user_id,
            source_method=ParserEvalSourceMethod.bootstrapped,
            review_status=ParserEvalReviewStatus.draft)
        return CaseDetailResponse.model_validate(case)

    async def set_case_review(self, case_id: UUID, review_status: str) -> CaseDetailResponse:
        case = await self.repo.update_case_review_status(
            case_id, ParserEvalReviewStatus(review_status))
        if case is None:
            raise NotFoundError(f"Parser eval case {case_id} not found")
        return CaseDetailResponse.model_validate(case)

    _MAX_CELLS_PER_TABLE = 2000

    async def replace_case_tables(self, case_id: UUID,
                                  data: CaseExpectedUpdate) -> CaseDetailResponse:
        case = await self.repo.get_case(case_id)
        if case is None:
            raise NotFoundError(f"Parser eval case {case_id} not found")
        if case.dimension != ParserEvalDimension.table:
            raise ValidationError("Only table cases support table replacement")

        clean_tables = []
        for t in data.tables:
            html = sanitize_table_html(t["html"])
            cell_count = html.lower().count("<td") + html.lower().count("<th")
            if "<table" not in html.lower() or cell_count == 0:
                raise ValidationError("each table must contain at least one cell")
            if cell_count > self._MAX_CELLS_PER_TABLE:
                raise ValidationError(f"table exceeds {self._MAX_CELLS_PER_TABLE} cells")
            clean_tables.append({"page": t["page"], "html": html})

        updated = await self.repo.replace_case_expected(case_id, {"tables": clean_tables})
        return CaseDetailResponse.model_validate(updated)

    async def delete_case(self, case_id: UUID) -> None:
        if not await self.repo.delete_case(case_id):
            raise NotFoundError(f"Parser eval case {case_id} not found")

    # --- datasets ---
    async def create_dataset(self, project_id: UUID, user_id: UUID,
                             data: DatasetCreate) -> DatasetResponse:
        ds = await self.repo.create_dataset(project_id, data.name, data.description, user_id)
        return DatasetResponse.model_validate(ds)

    async def list_datasets(self, project_id: UUID) -> list[DatasetResponse]:
        return [DatasetResponse.model_validate(d) for d in await self.repo.list_datasets(project_id)]

    async def add_case_to_dataset(self, dataset_id: UUID, eval_case_id: UUID) -> None:
        await self.repo.add_case_to_dataset(dataset_id, eval_case_id)

    async def remove_case_from_dataset(self, dataset_id: UUID, eval_case_id: UUID) -> None:
        await self.repo.remove_case_from_dataset(dataset_id, eval_case_id)

    async def list_dataset_cases(self, dataset_id: UUID) -> list[CaseResponse]:
        ids = await self.repo.list_dataset_case_ids(dataset_id)
        return [CaseResponse.model_validate(c) for c in await self.repo.get_cases_by_ids(ids)]

    # --- runs ---
    async def create_run(self, project_id: UUID, user_id: UUID, data: RunCreate) -> RunResponse:
        name = data.name or "Parser eval run"
        case_ids = [str(cid) for cid in data.eval_case_ids]
        if not case_ids and data.dataset_id is not None:
            case_ids = [str(cid) for cid in await self.repo.list_dataset_case_ids(data.dataset_id)]
        variants = [v.model_dump() for v in data.variants]
        run = await self.repo.create_run(project_id, name, variants, case_ids, user_id,
                                         dataset_id=data.dataset_id)
        return RunResponse.model_validate(run)

    async def execute_run(self, run_id: UUID) -> None:
        run = await self.repo.get_run(run_id)
        if run is None:
            raise NotFoundError(f"Parser eval run {run_id} not found")
        selected = [UUID(cid) for cid in (run.eval_case_ids or [])]
        cases = await self.repo.get_cases_by_ids(selected)

        source_cache: dict[UUID, object] = {}

        async def _resolve(case):
            src = source_cache.get(case.source_document_id)
            if src is None:
                src = await self.source_doc_repo.get(case.source_document_id)
                source_cache[case.source_document_id] = src
            return (str(case.source_document_id), src.storage_uri, src.filename, src.mime_type)

        resolved = {c.id: await _resolve(c) for c in cases}
        await run_evaluation(
            self.repo, self.parsing_service, self.storage,
            run_id=run_id, cases=cases, variants=list(run.variants),
            project_id=run.project_id, _case_source=lambda c: resolved[c.id])

    async def get_run(self, run_id: UUID) -> RunResponse:
        run = await self.repo.get_run(run_id)
        if run is None:
            raise NotFoundError(f"Parser eval run {run_id} not found")
        return RunResponse.model_validate(run)

    async def list_runs(self, project_id: UUID) -> list[RunResponse]:
        return [RunResponse.model_validate(r) for r in await self.repo.list_runs(project_id)]

    async def get_results(self, run_id: UUID) -> list[ResultResponse]:
        run = await self.repo.get_run(run_id)
        if run is None:
            raise NotFoundError(f"Parser eval run {run_id} not found")
        return [ResultResponse.model_validate(r) for r in await self.repo.get_results(run_id)]
