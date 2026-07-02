# backend/tests/repositories/test_classification_run_repository.py
import pytest
from uuid import uuid4
from app.cdm.classification import ClassifiedRegion
from app.repositories.classification_run_repository import (
    ClassificationRunCreate,
    ClassificationRunRepository,
)

_LLM_CONFIG = {
    "provider": "ollama_local",
    "model": "qwen2.5:7b",
    "batch_size": 10,
    "batch_overlap": 3,
    "llm_config": {},
}


@pytest.mark.asyncio
async def test_create_and_get_run(test_db):
    repo = ClassificationRunRepository(test_db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=uuid4(), document_id=uuid4(),
        labels_requested=["balance_sheet"],
        classifier_type="llm", classifier_config=_LLM_CONFIG,
    ))
    assert run.id is not None
    assert run.status == "pending"
    fetched = await repo.get(run.id)
    assert fetched.classifier_type == "llm"
    assert fetched.classifier_config["provider"] == "ollama_local"


@pytest.mark.asyncio
async def test_update_status(test_db):
    repo = ClassificationRunRepository(test_db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=uuid4(), document_id=uuid4(), labels_requested=["x"],
        classifier_type="llm", classifier_config=_LLM_CONFIG,
    ))
    await repo.update_status(run.id, "running")
    assert (await repo.get(run.id)).status == "running"


@pytest.mark.asyncio
async def test_save_and_get_regions(test_db):
    repo = ClassificationRunRepository(test_db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=uuid4(), document_id=uuid4(), labels_requested=["balance_sheet"],
        classifier_type="llm", classifier_config=_LLM_CONFIG,
    ))
    await repo.save_regions(run.id, [
        ClassifiedRegion(label="balance_sheet", page_start=5, page_end=8, block_ids=["b1", "b2"]),
    ])
    fetched = await repo.get_regions(run.id)
    assert len(fetched) == 1
    assert fetched[0].label == "balance_sheet"
    assert fetched[0].page_start == 5
    assert fetched[0].block_ids == ["b1", "b2"]


@pytest.mark.asyncio
async def test_get_annotated_blocks(test_db):
    from app.models.parsed_document import ParsedDocument as ParsedDocumentORM

    parse_run_id = uuid4()
    source_doc_id = uuid4()
    pd = ParsedDocumentORM(
        parse_run_id=parse_run_id, source_document_id=source_doc_id,
        full_text=None, full_markdown=None, page_count=2, block_count=3,
        content={
            "id": "doc-1", "source_document_id": str(source_doc_id),
            "parse_run_id": str(parse_run_id), "page_count": 2,
            "pages": [{"index": 0}, {"index": 1}],
            "blocks": [
                {"id": "b-1", "role": "heading", "native_type": "heading",
                 "text": "Balance Sheet", "page_index": 0},
                {"id": "b-2", "role": "text", "native_type": "paragraph",
                 "text": "Assets data", "page_index": 0},
                {"id": "b-3", "role": "text", "native_type": "paragraph",
                 "text": "Notes", "page_index": 1},
            ],
        },
    )
    test_db.add(pd)
    await test_db.commit()

    repo = ClassificationRunRepository(test_db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=parse_run_id, document_id=uuid4(), labels_requested=["balance_sheet"],
        classifier_type="llm", classifier_config=_LLM_CONFIG,
    ))
    await repo.save_regions(run.id, [
        ClassifiedRegion(label="balance_sheet", page_start=0, page_end=0, block_ids=["b-1", "b-2"]),
    ])
    blocks = await repo.get_annotated_blocks(run.id)
    assert len(blocks) == 3
    assert blocks[0].block_id == "b-1"
    assert blocks[0].label == "balance_sheet"
    assert blocks[2].label is None


@pytest.mark.asyncio
async def test_get_annotated_blocks_no_parsed_doc(test_db):
    repo = ClassificationRunRepository(test_db)
    run = await repo.create(ClassificationRunCreate(
        parse_run_id=uuid4(), document_id=uuid4(), labels_requested=["x"],
        classifier_type="llm", classifier_config=_LLM_CONFIG,
    ))
    assert await repo.get_annotated_blocks(run.id) == []
