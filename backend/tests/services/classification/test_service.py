# backend/tests/services/classification/test_service.py
from unittest.mock import ANY, AsyncMock, MagicMock, patch
from uuid import uuid4
import pytest
from app.cdm.models import Block, BlockRole, Page, ParsedDocument
from app.cdm.classification import ClassifiedRegion
from app.services.classification.service import ClassificationService
from app.services.llm.types import CompletionResult, TokenUsage


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
    repo = MagicMock()
    repo.update_status = AsyncMock()
    repo.update_completed = AsyncMock()
    repo.save_regions = AsyncMock()

    llm_adapter = MagicMock()
    llm_adapter.complete = AsyncMock(return_value=CompletionResult(
        content='{"pages": [{"page": 0, "labels": {"x": "none"}}, {"page": 1, "labels": {"x": "start"}}, {"page": 2, "labels": {"x": "continue"}}]}',
        usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        latency_ms=200.0,
        model="qwen2.5:7b",
        provider="ollama",
    ))

    registry = MagicMock()
    registry.get.return_value = llm_adapter

    service = ClassificationService(repo=repo, llm_registry=registry)
    doc = _make_doc()

    await service.execute(
        run_id=uuid4(),
        doc=doc,
        labels=["x"],
        llm_provider="ollama_local",
        llm_model="qwen2.5:7b",
        batch_size=10,
        batch_overlap=3,
    )

    repo.update_status.assert_any_call(run_id=ANY, status="running")
    repo.save_regions.assert_called_once()
    saved_regions = repo.save_regions.call_args[1]["regions"]
    assert len(saved_regions) == 1
    assert saved_regions[0].label == "x"
    assert saved_regions[0].page_start == 1
    assert saved_regions[0].page_end == 2
    repo.update_completed.assert_called_once()
