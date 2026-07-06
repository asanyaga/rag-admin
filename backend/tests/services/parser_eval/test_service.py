import pytest
from app.cdm.models import ParsedDocument, Page
from app.repositories.parser_eval_repository import ParserEvalRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.schemas.parser_eval import CaseCreate, DatasetCreate, RunCreate, VariantInput
from app.services.parser_eval import engine as engine_mod
from app.services.parser_eval.service import ParserEvalService


def _service(db):
    return ParserEvalService(ParserEvalRepository(db), SourceDocumentRepository(db),
                             parsing_service=object(), storage=object())


@pytest.mark.asyncio
async def test_case_then_run_produces_metric_result(test_db, seed_project_user_source, monkeypatch):
    project_id, user_id, source_id = seed_project_user_source

    async def fake_capture(*a, **k):
        doc = ParsedDocument(id="d", source_document_id="s", parse_run_id="r", page_count=1,
                             pages=[Page(index=0, start_char=0, end_char=2)], blocks=[], full_text="hi")
        return doc, {"usd": 0.0}, 5
    monkeypatch.setattr(engine_mod, "capture", fake_capture)

    service = _service(test_db)
    case = await service.create_case(project_id, user_id, CaseCreate(
        source_document_id=source_id, dimension="text", expected={"pages": ["hi"]}))
    run = await service.create_run(project_id, user_id, RunCreate(
        name="r1", variants=[VariantInput(adapter="docling", config={})],
        eval_case_ids=[case.id]))
    await service.execute_run(run.id)

    results = await service.get_results(run.id)
    assert len(results) == 1
    assert results[0].metrics["similarity"] == 1.0
    assert results[0].primary_metric == "similarity"


@pytest.mark.asyncio
async def test_run_from_dataset_snapshots_cases(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    service = _service(test_db)
    case = await service.create_case(project_id, user_id, CaseCreate(
        source_document_id=source_id, dimension="text", expected={"pages": ["hi"]}))
    ds = await service.create_dataset(project_id, user_id, DatasetCreate(name="smoke"))
    await service.add_case_to_dataset(ds.id, case.id)

    run = await service.create_run(project_id, user_id, RunCreate(
        variants=[VariantInput(adapter="docling", config={})], dataset_id=ds.id))
    stored = await service.repo.get_run(run.id)
    # Snapshot resolved from dataset membership at creation time.
    assert [str(c) for c in stored.eval_case_ids] == [str(case.id)]
    assert stored.dataset_id == ds.id
