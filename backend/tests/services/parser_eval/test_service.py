import pytest
from app.cdm.models import Block, BlockRole, ParsedDocument, Page, Table
from app.repositories.parser_eval_repository import ParserEvalRepository
from app.repositories.source_document_repository import SourceDocumentRepository
from app.schemas.parser_eval import (
    BootstrapTableRequest, CaseCreate, DatasetCreate, RunCreate, VariantInput,
)
from app.services.exceptions import ConflictError, NotFoundError
from app.services.parser_eval import engine as engine_mod
from app.services.parser_eval import service as service_mod
from app.services.parser_eval.service import ParserEvalService


def _service(db):
    return ParserEvalService(ParserEvalRepository(db), SourceDocumentRepository(db),
                             parsing_service=object(), storage=object())


def _cdm_with_one_table():
    html = "<table><tr><td>a</td></tr></table>"
    return ParsedDocument(
        id="d", source_document_id="s", parse_run_id="r", page_count=1,
        pages=[Page(index=0)],
        blocks=[Block(id="b0", role=BlockRole.TABLE, native_type="table",
                      page_index=0, reading_order=0,
                      table=Table(rows=1, cols=1, cells=[], html=html))])


def _patch_capture(monkeypatch):
    async def fake_capture(*a, **k):
        return _cdm_with_one_table(), {}, 100
    monkeypatch.setattr(service_mod, "capture", fake_capture)


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


@pytest.mark.asyncio
async def test_bootstrap_table_case_creates_draft(test_db, seed_project_user_source, monkeypatch):
    project_id, user_id, source_id = seed_project_user_source
    _patch_capture(monkeypatch)
    service = _service(test_db)
    req = BootstrapTableRequest.model_validate(
        {"sourceDocumentId": str(source_id), "adapter": "docling", "config": {}})
    detail = await service.bootstrap_table_case(project_id, user_id, req)
    assert detail.dimension == "table"
    assert detail.source_method == "bootstrapped"
    assert detail.review_status == "draft"
    assert detail.expected["tables"][0]["html"] == "<table><tr><td>a</td></tr></table>"
    assert detail.expected["tables"][0]["page"] == 1


@pytest.mark.asyncio
async def test_bootstrap_duplicate_raises_conflict(test_db, seed_project_user_source, monkeypatch):
    project_id, user_id, source_id = seed_project_user_source
    _patch_capture(monkeypatch)
    service = _service(test_db)
    req = BootstrapTableRequest.model_validate(
        {"sourceDocumentId": str(source_id), "adapter": "docling", "config": {}})
    await service.bootstrap_table_case(project_id, user_id, req)
    with pytest.raises(ConflictError):
        await service.bootstrap_table_case(project_id, user_id, req)


@pytest.mark.asyncio
async def test_set_case_review_and_delete(test_db, seed_project_user_source, monkeypatch):
    project_id, user_id, source_id = seed_project_user_source
    _patch_capture(monkeypatch)
    service = _service(test_db)
    req = BootstrapTableRequest.model_validate(
        {"sourceDocumentId": str(source_id), "adapter": "docling", "config": {}})
    detail = await service.bootstrap_table_case(project_id, user_id, req)
    verified = await service.set_case_review(detail.id, "verified")
    assert verified.review_status == "verified"
    await service.delete_case(detail.id)
    with pytest.raises(NotFoundError):
        await service.get_case(detail.id)
