# backend/tests/services/classification/test_llm_classifier.py
from unittest.mock import AsyncMock, MagicMock
import pytest
from app.cdm.models import Block, BlockRole, Page, ParsedDocument
from app.services.llm.types import CompletionResult, TokenUsage


def _make_doc() -> ParsedDocument:
    pages = [Page(index=i, block_ids=[f"b{i}"]) for i in range(3)]
    blocks = [
        Block(id=f"b{i}", role=BlockRole.TEXT, native_type="p",
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
        latency_ms=200.0, model="qwen2.5:7b", provider="ollama_local",
    ))
    return adapter


_RESPONSE_3_PAGES = (
    '{"pages":['
    '{"page":0,"labels":{"x":"none"}},'
    '{"page":1,"labels":{"x":"start"}},'
    '{"page":2,"labels":{"x":"continue"}}'
    ']}'
)
_RESPONSE_ALL_NONE = (
    '{"pages":['
    '{"page":0,"labels":{"x":"none"}},'
    '{"page":1,"labels":{"x":"none"}},'
    '{"page":2,"labels":{"x":"none"}}'
    ']}'
)


@pytest.mark.asyncio
async def test_llm_classifier_takes_adapter_directly():
    """Constructor accepts adapter: LLMPort, not llm_registry."""
    from app.services.classification.llm_classifier import LLMClassifier
    adapter = _make_adapter(_RESPONSE_3_PAGES)
    # Must not require llm_registry kwarg
    classifier = LLMClassifier(
        adapter=adapter, provider="ollama_local", model="qwen2.5:7b",
        batch_size=10, batch_overlap=3,
    )
    assert classifier.adapter is adapter


@pytest.mark.asyncio
async def test_llm_classifier_returns_regions_and_tokens():
    from app.services.classification.llm_classifier import LLMClassifier
    adapter = _make_adapter(_RESPONSE_3_PAGES)
    classifier = LLMClassifier(
        adapter=adapter, provider="ollama_local", model="qwen2.5:7b",
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
async def test_llm_classifier_passes_json_mode_to_config():
    from app.services.classification.llm_classifier import LLMClassifier
    adapter = _make_adapter(_RESPONSE_ALL_NONE)
    classifier = LLMClassifier(
        adapter=adapter, provider="ollama_local", model="qwen2.5:7b",
        batch_size=10, batch_overlap=3,
    )
    await classifier.classify(_make_doc(), ["x"])
    config = adapter.complete.call_args[0][1]
    assert config.structured_output_mode == "json_mode"


@pytest.mark.asyncio
async def test_llm_classifier_uses_custom_system_prompt():
    from app.services.classification.llm_classifier import LLMClassifier
    from app.services.classification.prompt_constants import _REQUIRED_FORMAT
    adapter = _make_adapter(_RESPONSE_ALL_NONE)
    classifier = LLMClassifier(
        adapter=adapter, provider="ollama_local", model="qwen2.5:7b",
        batch_size=10, batch_overlap=3, system_prompt="Custom prompt",
    )
    await classifier.classify(_make_doc(), ["x"])
    messages = adapter.complete.call_args[0][0]
    # Custom instruction is prepended; required format is always appended
    assert messages[0]["content"].startswith("Custom prompt")
    assert _REQUIRED_FORMAT in messages[0]["content"]


def test_prompt_assembly_default_uses_full_default_prompt():
    from app.services.classification.llm_classifier import LLMClassifier
    from app.services.classification.prompt_constants import DEFAULT_SYSTEM_PROMPT
    classifier = LLMClassifier(adapter=None, provider="ollama_local", model="test")
    assert classifier.system_prompt == DEFAULT_SYSTEM_PROMPT


def test_prompt_assembly_custom_instruction_appends_required_format():
    from app.services.classification.llm_classifier import LLMClassifier
    from app.services.classification.prompt_constants import _REQUIRED_FORMAT
    custom = "You are a specialized classifier."
    classifier = LLMClassifier(adapter=None, provider="ollama_local", model="test",
                               system_prompt=custom)
    assert classifier.system_prompt == custom + "\n\n" + _REQUIRED_FORMAT


def test_prompt_assembly_required_format_not_duplicated_in_default():
    from app.services.classification.llm_classifier import LLMClassifier
    classifier = LLMClassifier(adapter=None, provider="ollama_local", model="test")
    assert classifier.system_prompt.count("Return ONLY valid JSON") == 1


@pytest.mark.asyncio
async def test_llm_classifier_threads_temperature_and_max_tokens():
    from app.services.classification.llm_classifier import LLMClassifier
    adapter = _make_adapter(_RESPONSE_ALL_NONE)
    classifier = LLMClassifier(
        adapter=adapter, provider="ollama_local", model="qwen2.5:7b",
        batch_size=10, batch_overlap=3, temperature=0.7, max_tokens=2048,
    )
    await classifier.classify(_make_doc(), ["x"])
    config = adapter.complete.call_args[0][1]
    assert config.temperature == 0.7
    assert config.max_tokens == 2048
