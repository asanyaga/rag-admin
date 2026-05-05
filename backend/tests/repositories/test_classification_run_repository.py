# backend/tests/repositories/test_classification_run_repository.py
import pytest
from uuid import uuid4
from app.cdm.classification import ClassifiedRegion
from app.repositories.classification_run_repository import (
    ClassificationRunCreate,
    ClassificationRunRepository,
)


@pytest.mark.asyncio
async def test_create_and_get_run(test_db):
    repo = ClassificationRunRepository(test_db)
    data = ClassificationRunCreate(
        parse_run_id=uuid4(),
        document_id=uuid4(),
        labels_requested=["balance_sheet"],
        llm_provider="ollama_local",
        llm_model="qwen2.5:7b",
        batch_size=10,
        batch_overlap=3,
    )
    run = await repo.create(data)
    assert run.id is not None
    assert run.status == "pending"
    assert run.labels_requested == ["balance_sheet"]

    fetched = await repo.get(run.id)
    assert fetched is not None
    assert fetched.llm_provider == "ollama_local"


@pytest.mark.asyncio
async def test_update_status(test_db):
    repo = ClassificationRunRepository(test_db)
    data = ClassificationRunCreate(
        parse_run_id=uuid4(),
        document_id=uuid4(),
        labels_requested=["x"],
        llm_provider="ollama_local",
        llm_model="qwen2.5:7b",
        batch_size=10,
        batch_overlap=3,
    )
    run = await repo.create(data)
    await repo.update_status(run.id, "running")
    fetched = await repo.get(run.id)
    assert fetched.status == "running"


@pytest.mark.asyncio
async def test_save_and_get_regions(test_db):
    repo = ClassificationRunRepository(test_db)
    data = ClassificationRunCreate(
        parse_run_id=uuid4(),
        document_id=uuid4(),
        labels_requested=["balance_sheet"],
        llm_provider="ollama_local",
        llm_model="qwen2.5:7b",
        batch_size=10,
        batch_overlap=3,
    )
    run = await repo.create(data)
    regions = [
        ClassifiedRegion(label="balance_sheet", page_start=5, page_end=8, block_ids=["b1", "b2"]),
    ]
    await repo.save_regions(run.id, regions)
    fetched = await repo.get_regions(run.id)
    assert len(fetched) == 1
    assert fetched[0].label == "balance_sheet"
    assert fetched[0].page_start == 5
    assert fetched[0].block_ids == ["b1", "b2"]
