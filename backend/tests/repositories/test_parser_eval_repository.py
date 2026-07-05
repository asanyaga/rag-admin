import pytest
from app.models.parser_eval import ParserEvalDimension, ParserEvalRunStatus
from app.repositories.parser_eval_repository import ParserEvalRepository


@pytest.mark.asyncio
async def test_create_case_with_target_and_fetch(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    repo = ParserEvalRepository(test_db)

    case = await repo.create_case(project_id, "acme_invoice", "invoice", source_id, "acme.pdf", user_id)
    await repo.add_target(case.id, ParserEvalDimension.text, {"pages": ["hello"]})

    fetched = await repo.get_case(case.id)
    assert fetched.name == "acme_invoice"
    assert len(fetched.targets) == 1
    assert fetched.targets[0].expected == {"pages": ["hello"]}


@pytest.mark.asyncio
async def test_run_and_result_upsert(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    repo = ParserEvalRepository(test_db)
    run = await repo.create_run(project_id, "run-1", ["docling", "simple"], [], user_id)

    case = await repo.create_case(project_id, "c", None, source_id, None, user_id)
    await repo.upsert_result(run.id, case.id, "docling", ParserEvalDimension.text, 0.9, {}, {}, 120)
    await repo.upsert_result(run.id, case.id, "docling", ParserEvalDimension.text, 0.95, {}, {}, 130)  # same key

    results = await repo.get_results(run.id)
    assert len(results) == 1              # upsert replaced, not duplicated
    assert results[0].score == 0.95

    await repo.set_run_status(run.id, ParserEvalRunStatus.completed)
    assert (await repo.get_run(run.id)).status == ParserEvalRunStatus.completed
