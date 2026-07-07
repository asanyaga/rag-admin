import pytest
from app.models.parser_eval import (
    ParserEvalDimension, ParserEvalReviewStatus, ParserEvalRunStatus,
)
from app.repositories.parser_eval_repository import ParserEvalRepository


@pytest.mark.asyncio
async def test_get_case_by_doc_dimension_and_review_and_delete(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    repo = ParserEvalRepository(test_db)
    case = await repo.create_case(project_id, source_id, ParserEvalDimension.table,
                                  {"tables": []}, user_id)

    found = await repo.get_case_by_doc_dimension(source_id, ParserEvalDimension.table)
    assert found is not None and found.id == case.id

    updated = await repo.update_case_review_status(case.id, ParserEvalReviewStatus.verified)
    assert updated.review_status == ParserEvalReviewStatus.verified

    assert await repo.delete_case(case.id) is True
    assert await repo.get_case(case.id) is None
    assert await repo.delete_case(case.id) is False


@pytest.mark.asyncio
async def test_create_case_and_fetch(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    repo = ParserEvalRepository(test_db)
    case = await repo.create_case(project_id, source_id, ParserEvalDimension.text,
                                  {"pages": ["hello"]}, user_id)
    fetched = await repo.get_case(case.id)
    assert fetched.expected == {"pages": ["hello"]}
    assert [c.id for c in await repo.list_cases(project_id)] == [case.id]


@pytest.mark.asyncio
async def test_dataset_membership_roundtrip(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    repo = ParserEvalRepository(test_db)
    case = await repo.create_case(project_id, source_id, ParserEvalDimension.text,
                                  {"pages": ["x"]}, user_id)
    ds = await repo.create_dataset(project_id, "smoke", None, user_id)
    await repo.add_case_to_dataset(ds.id, case.id)
    assert await repo.list_dataset_case_ids(ds.id) == [case.id]
    await repo.remove_case_from_dataset(ds.id, case.id)
    assert await repo.list_dataset_case_ids(ds.id) == []


@pytest.mark.asyncio
async def test_results_are_append_only(test_db, seed_project_user_source):
    project_id, user_id, source_id = seed_project_user_source
    repo = ParserEvalRepository(test_db)
    case = await repo.create_case(project_id, source_id, ParserEvalDimension.text,
                                  {"pages": ["x"]}, user_id)
    run = await repo.create_run(project_id, "r",
                                [{"adapter": "docling", "config": {}}], [str(case.id)], user_id)
    # Two distinct variants -> two immutable rows.
    await repo.insert_result(run.id, case.id, "docling", {}, "docling@aaa",
                             {"similarity": 0.9}, "similarity", {}, {}, 100)
    await repo.insert_result(run.id, case.id, "custom_pipeline", {"tool": "fitz"},
                             "custom_pipeline@bbb", {"similarity": 0.8}, "similarity", {}, {}, 40)
    assert len(await repo.get_results(run.id)) == 2

    await repo.set_run_status(run.id, ParserEvalRunStatus.completed)
    assert (await repo.get_run(run.id)).status == ParserEvalRunStatus.completed

    # Re-inserting the same (run, case, variant_key) is rejected — results are never
    # overwritten. This must be the last DB action: forcing the violation leaves the
    # single aiosqlite test connection unusable for further queries.
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        await repo.insert_result(run.id, case.id, "docling", {}, "docling@aaa",
                                 {"similarity": 0.95}, "similarity", {}, {}, 110)
    await test_db.rollback()
