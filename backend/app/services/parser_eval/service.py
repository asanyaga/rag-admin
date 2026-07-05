"""Service orchestrating parser-eval CRUD and run execution."""
from __future__ import annotations

from uuid import UUID

from app.models.parser_eval import ParserEvalDimension
from app.repositories.parser_eval_repository import ParserEvalRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.schemas.parser_eval import (
    CaseCreate, CaseResponse, RunCreate, RunResponse, ResultResponse,
)
from app.services.exceptions import NotFoundError
from app.services.parser_eval.engine import run_evaluation


class ParserEvalService:
    def __init__(self, repo: ParserEvalRepository, source_doc_repo: SourceDocumentRepository,
                 parsing_service, storage):
        self.repo = repo
        self.source_doc_repo = source_doc_repo
        self.parsing_service = parsing_service
        self.storage = storage

    async def create_case(self, project_id: UUID, user_id: UUID, data: CaseCreate) -> CaseResponse:
        source = await self.source_doc_repo.get(data.source_document_id)
        if source is None:
            raise NotFoundError(f"Source document {data.source_document_id} not found")
        case = await self.repo.create_case(project_id, data.name, data.doc_type,
                                           data.source_document_id, source.filename, user_id)
        for t in data.targets:
            await self.repo.add_target(case.id, ParserEvalDimension(t.dimension), t.expected)
        return CaseResponse.model_validate(case)

    async def list_cases(self, project_id: UUID) -> list[CaseResponse]:
        return [CaseResponse.model_validate(c) for c in await self.repo.list_cases(project_id)]

    async def create_run(self, project_id: UUID, user_id: UUID, data: RunCreate) -> RunResponse:
        name = data.name or "Parser eval run"
        run = await self.repo.create_run(
            project_id, name, data.parsers, [str(cid) for cid in data.case_ids], user_id)
        return RunResponse.model_validate(run)

    async def execute_run(self, run_id: UUID) -> None:
        run = await self.repo.get_run(run_id)
        if run is None:
            raise NotFoundError(f"Parser eval run {run_id} not found")
        # Load only the cases selected for this run (persisted in run.case_ids).
        selected = {str(cid) for cid in (run.case_ids or [])}
        cases = [c for c in await self.repo.list_cases(run.project_id) if str(c.id) in selected]

        # Resolve each case's source document fields for capture, once.
        source_cache: dict[UUID, object] = {}

        async def _resolve(case):
            src = source_cache.get(case.source_document_id)
            if src is None:
                src = await self.source_doc_repo.get(case.source_document_id)
                source_cache[case.source_document_id] = src
            return (str(case.source_document_id), src.storage_uri, src.filename, src.mime_type)

        # run_evaluation expects a sync resolver; pre-resolve into a dict.
        resolved = {c.id: await _resolve(c) for c in cases}
        await run_evaluation(
            self.repo, self.parsing_service, self.storage,
            run_id=run_id, cases=cases, parsers=list(run.parsers),
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
