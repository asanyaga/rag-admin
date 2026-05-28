from unittest.mock import ANY, AsyncMock, MagicMock
from uuid import uuid4
import pytest
from app.cdm.classification import ClassifiedRegion
from app.cdm.models import Block, BlockRole, Page, ParsedDocument
from app.services.classification.port import ClassificationResult


def _make_doc() -> ParsedDocument:
    pages = [Page(index=i, block_ids=[f"b{i}"]) for i in range(3)]
    blocks = [
        Block(id=f"b{i}", role=BlockRole.PARAGRAPH, native_type="p",
              text=f"page {i}", page_index=i, reading_order=0)
        for i in range(3)
    ]
    return ParsedDocument(
        id="doc-1", source_document_id="s", parse_run_id="r",
        page_count=3, pages=pages, blocks=blocks,
    )


@pytest.mark.asyncio
async def test_service_execute_saves_regions():
    from app.services.classification.service import ClassificationService

    repo = MagicMock()
    repo.update_status = AsyncMock()
    repo.update_completed = AsyncMock()
    repo.save_regions = AsyncMock()

    regions = [ClassifiedRegion(label="x", page_start=1, page_end=2, block_ids=["b1"])]
    classifier = MagicMock()
    classifier.classify = AsyncMock(return_value=ClassificationResult(
        regions=regions, input_tokens=100, output_tokens=50,
    ))

    service = ClassificationService(repo=repo, classifier=classifier)
    await service.execute(run_id=uuid4(), doc=_make_doc(), labels=["x"])

    repo.update_status.assert_any_call(run_id=ANY, status="running")
    repo.save_regions.assert_called_once()
    assert repo.save_regions.call_args[1]["regions"][0].label == "x"
    call_kwargs = repo.update_completed.call_args[1]
    assert call_kwargs["input_tokens"] == 100
    assert call_kwargs["output_tokens"] == 50


@pytest.mark.asyncio
async def test_service_execute_marks_failed_on_error():
    from app.services.classification.service import ClassificationService

    repo = MagicMock()
    repo.update_status = AsyncMock()
    repo.update_completed = AsyncMock()
    repo.save_regions = AsyncMock()

    classifier = MagicMock()
    classifier.classify = AsyncMock(side_effect=RuntimeError("boom"))

    service = ClassificationService(repo=repo, classifier=classifier)
    with pytest.raises(RuntimeError):
        await service.execute(run_id=uuid4(), doc=_make_doc(), labels=["x"])

    repo.update_status.assert_any_call(run_id=ANY, status="failed", error="boom")
