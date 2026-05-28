from unittest.mock import AsyncMock, MagicMock
import pytest
from app.cdm.models import Block, BlockRole, Page, ParsedDocument
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


def _make_adapter(content: str) -> MagicMock:
    adapter = MagicMock()
    adapter.complete = AsyncMock(return_value=CompletionResult(
        content=content,
        usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        latency_ms=200.0, model="qwen2.5:7b", provider="ollama",
    ))
    return adapter


@pytest.mark.asyncio
async def test_llm_classifier_returns_regions_and_tokens():
    from app.services.classification.llm_classifier import LLMClassifier
    adapter = _make_adapter(
        '{"pages":['
        '{"page":0,"labels":{"x":"none"}},'
        '{"page":1,"labels":{"x":"start"}},'
        '{"page":2,"labels":{"x":"continue"}}'
        ']}'
    )
    registry = MagicMock()
    registry.get.return_value = adapter
    classifier = LLMClassifier(
        llm_registry=registry, provider="ollama_local", model="qwen2.5:7b",
        batch_size=10, batch_overlap=3,
    )
    result = await classifier.classify(_make_doc(), ["x"])
    assert len(result.regions) == 1
    assert result.regions[0].label == "x"
    assert result.regions[0].page_start == 1
    assert result.regions[0].page_end == 2
    assert result.input_tokens == 100
    assert result.output_tokens == 50


@pytest.mark.asyncio
async def test_llm_classifier_uses_custom_system_prompt():
    from app.services.classification.llm_classifier import LLMClassifier
    adapter = _make_adapter(
        '{"pages":[{"page":0,"labels":{"x":"none"}},{"page":1,"labels":{"x":"none"}},{"page":2,"labels":{"x":"none"}}]}'
    )
    registry = MagicMock()
    registry.get.return_value = adapter
    classifier = LLMClassifier(
        llm_registry=registry, provider="ollama_local", model="qwen2.5:7b",
        batch_size=10, batch_overlap=3, system_prompt="Custom prompt",
    )
    await classifier.classify(_make_doc(), ["x"])
    messages = adapter.complete.call_args[0][0]
    assert messages[0]["content"] == "Custom prompt"


@pytest.mark.asyncio
async def test_llm_classifier_threads_temperature_and_max_tokens():
    from app.services.classification.llm_classifier import LLMClassifier
    adapter = _make_adapter(
        '{"pages":[{"page":0,"labels":{"x":"none"}},{"page":1,"labels":{"x":"none"}},{"page":2,"labels":{"x":"none"}}]}'
    )
    registry = MagicMock()
    registry.get.return_value = adapter
    classifier = LLMClassifier(
        llm_registry=registry, provider="ollama_local", model="qwen2.5:7b",
        batch_size=10, batch_overlap=3, temperature=0.7, max_tokens=2048,
    )
    await classifier.classify(_make_doc(), ["x"])
    config = adapter.complete.call_args[0][1]
    assert config.temperature == 0.7
    assert config.max_tokens == 2048
