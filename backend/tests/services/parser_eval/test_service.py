import pytest
from app.cdm.models import ParsedDocument, Page
from app.repositories.parser_eval_repository import ParserEvalRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.schemas.parser_eval import CaseCreate, TargetInput, RunCreate
from app.services.parser_eval import engine as engine_mod
from app.services.parser_eval.service import ParserEvalService


def _build_service(db):
    """Wire the real repos with fake parsing_service/storage (capture is monkeypatched)."""
    repo = ParserEvalRepository(db)
    source_doc_repo = SourceDocumentRepository(db)
    return ParserEvalService(repo, source_doc_repo, parsing_service=object(), storage=object())


@pytest.mark.asyncio
async def test_create_case_then_run_produces_results(test_db, seed_project_user_source, monkeypatch):
    project_id, user_id, source_id = seed_project_user_source

    async def fake_capture(*a, **k):
        doc = ParsedDocument(id="d", source_document_id="s", parse_run_id="r",
                             page_count=1, pages=[Page(index=0, start_char=0, end_char=2)],
                             blocks=[], full_text="hi")
        return doc, {"usd": 0.0}, 5
    monkeypatch.setattr(engine_mod, "capture", fake_capture)

    service = _build_service(test_db)
    case = await service.create_case(project_id, user_id, CaseCreate(
        name="c", source_document_id=source_id,
        targets=[TargetInput(dimension="text", expected={"pages": ["hi"]})]))
    run = await service.create_run(project_id, user_id, RunCreate(
        name="r1", case_ids=[case.id], parsers=["docling"]))
    await service.execute_run(run.id)

    results = await service.get_results(run.id)
    assert len(results) == 1
    assert results[0].score == 1.0
