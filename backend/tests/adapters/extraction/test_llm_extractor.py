"""Unit tests for LLMExtractor — adapter injected at construction, no internal create_adapter."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

from app.services.llm.types import CompletionResult, TokenUsage

PARSE_RUN_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _make_parsed_doc():
    from app.cdm.models import ParsedDocument, Page
    pages = [Page(index=0, block_ids=[])]
    return ParsedDocument(
        id="doc-1", source_document_id="src-1", parse_run_id=PARSE_RUN_ID,
        page_count=1, pages=pages, blocks=[],
    )


def _make_adapter(content: str = "{}") -> MagicMock:
    adapter = MagicMock()
    adapter.complete = AsyncMock(return_value=CompletionResult(
        content=content,
        usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        latency_ms=100.0, model="llama3.2:8b", provider="ollama_local",
    ))
    return adapter


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class TestLLMExtractorProperties:
    def test_extractor_type(self):
        from app.adapters.extraction.llm import LLMExtractor
        assert LLMExtractor(adapter=_make_adapter(), provider="ollama_local").extractor_type == "llm"

    def test_display_name(self):
        from app.adapters.extraction.llm import LLMExtractor
        assert LLMExtractor(adapter=_make_adapter(), provider="ollama_local").display_name == "LLM"

    def test_provider_stored(self):
        from app.adapters.extraction.llm import LLMExtractor
        e = LLMExtractor(adapter=_make_adapter(), provider="anthropic")
        assert e._provider == "anthropic"

    def test_adapter_stored(self):
        from app.adapters.extraction.llm import LLMExtractor
        adapter = _make_adapter()
        e = LLMExtractor(adapter=adapter, provider="openai")
        assert e._adapter is adapter


# ---------------------------------------------------------------------------
# _build_messages (no dependency on provider/adapter)
# ---------------------------------------------------------------------------

class TestLLMExtractorBuildMessages:
    @pytest.fixture
    def extractor(self):
        from app.adapters.extraction.llm import LLMExtractor
        return LLMExtractor(adapter=_make_adapter(), provider="ollama_local")

    def test_uses_default_system_prompt(self, extractor):
        from app.adapters.extraction.llm import DEFAULT_EXTRACTION_SYSTEM_PROMPT
        msgs = extractor._build_messages({"type": "object"}, "ctx", {})
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == DEFAULT_EXTRACTION_SYSTEM_PROMPT

    def test_uses_custom_system_prompt_from_cfg(self, extractor):
        msgs = extractor._build_messages(
            {"type": "object"}, "ctx", {"system_prompt": "Be precise."}
        )
        assert msgs[0]["content"] == "Be precise."

    def test_schema_json_interpolated(self, extractor):
        aug_schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        msgs = extractor._build_messages(aug_schema, "doc text", {})
        assert json.dumps(aug_schema, indent=2) in msgs[1]["content"]

    def test_two_messages_system_then_user(self, extractor):
        msgs = extractor._build_messages({"type": "object"}, "ctx", {})
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"


# ---------------------------------------------------------------------------
# extract() — injected adapter is used directly, no create_adapter() call
# ---------------------------------------------------------------------------

class TestLLMExtractorExtract:
    @pytest.fixture
    def adapter(self):
        return _make_adapter("{}")

    @pytest.fixture
    def extractor(self, adapter):
        from app.adapters.extraction.llm import LLMExtractor
        return LLMExtractor(adapter=adapter, provider="ollama_local")

    @pytest.fixture
    def parsed_doc(self):
        return _make_parsed_doc()

    async def test_injected_adapter_complete_is_called(self, extractor, adapter, parsed_doc):
        """extract() calls self._adapter.complete — never create_adapter()."""
        schema = {"type": "object", "properties": {}}
        await extractor.extract(parsed_doc, schema, {})
        adapter.complete.assert_called_once()

    async def test_provider_flows_into_llm_config(self, parsed_doc):
        """The provider passed to __init__ ends up in LLMConfig.provider."""
        from app.adapters.extraction.llm import LLMExtractor
        adapter = _make_adapter("{}")
        e = LLMExtractor(adapter=adapter, provider="anthropic")
        schema = {"type": "object", "properties": {}}
        await e.extract(parsed_doc, schema, {})
        llm_config_arg = adapter.complete.call_args.args[1]
        assert llm_config_arg.provider == "anthropic"

    async def test_prompt_config_model_forwarded(self, extractor, adapter, parsed_doc):
        schema = {"type": "object", "properties": {}}
        llm_cfg_dict = {"provider": "ollama_local", "model": "llama3.2:8b", "maxTokens": 8192}
        await extractor.extract(parsed_doc, schema, {"llm_config": llm_cfg_dict})
        llm_config_arg = adapter.complete.call_args.args[1]
        assert llm_config_arg.max_tokens == 8192

    async def test_structured_output_schema_passed_for_json_schema_mode(self, parsed_doc):
        from app.adapters.extraction.llm import LLMExtractor
        adapter = _make_adapter('{"total": 99}')
        e = LLMExtractor(adapter=adapter, provider="openai")
        schema = {"type": "object", "properties": {"total": {"type": "number"}}}
        await e.extract(parsed_doc, schema, {})
        llm_config_arg = adapter.complete.call_args.args[1]
        assert llm_config_arg.structured_output_mode == "json_schema"
        assert llm_config_arg.structured_output_schema is not None

    async def test_returns_structured_data_without_source_fields(self, extractor, adapter, parsed_doc):
        schema = {"type": "object", "properties": {"total": {"type": "number"}}}
        raw = {"total": 500, "total__source": {"page_index": 1}}
        adapter.complete = AsyncMock(return_value=CompletionResult(
            content=json.dumps(raw),
            usage=TokenUsage(10, 20, 30), latency_ms=50, model="m", provider="p",
        ))
        output = await extractor.extract(parsed_doc, schema, {})
        assert output.structured_data == {"total": 500}
        assert output.source_parse_run_id == UUID(PARSE_RUN_ID)

    async def test_usage_recorded_in_extraction_metadata(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        output = await extractor.extract(parsed_doc, schema, {})
        assert output.extraction_metadata["usage"]["prompt_tokens"] == 10
        assert output.extraction_metadata["usage"]["completion_tokens"] == 20

    async def test_raises_extraction_error_on_non_json_response(self, parsed_doc):
        from app.adapters.extraction.llm import LLMExtractor
        from app.ports.data_extraction import ExtractionError
        adapter = _make_adapter("not valid json at all")
        e = LLMExtractor(adapter=adapter, provider="openai")
        schema = {"type": "object", "properties": {}}
        with pytest.raises(ExtractionError, match="non-JSON"):
            await e.extract(parsed_doc, schema, {})

    async def test_strips_json_code_fence_from_response(self, parsed_doc):
        from app.adapters.extraction.llm import LLMExtractor
        raw = {"vendor": "Acme", "vendor__source": {"page_index": 0}}
        fenced = f"```json\n{json.dumps(raw)}\n```"
        adapter = _make_adapter(fenced)
        e = LLMExtractor(adapter=adapter, provider="ollama_local")
        schema = {"type": "object", "properties": {"vendor": {"type": "string"}}}
        output = await e.extract(parsed_doc, schema, {})
        assert output.structured_data == {"vendor": "Acme"}

    async def test_strips_plain_code_fence_from_response(self, parsed_doc):
        from app.adapters.extraction.llm import LLMExtractor
        raw = {"total": 42}
        fenced = f"```\n{json.dumps(raw)}\n```"
        adapter = _make_adapter(fenced)
        e = LLMExtractor(adapter=adapter, provider="ollama_local")
        schema = {"type": "object", "properties": {"total": {"type": "number"}}}
        output = await e.extract(parsed_doc, schema, {})
        assert output.structured_data == {"total": 42}

    async def test_strips_code_fence_when_model_adds_preamble_text(self, parsed_doc):
        from app.adapters.extraction.llm import LLMExtractor
        raw = {"vendor": "Acme", "vendor__source": {"page_index": 0}}
        preamble = f"Here is the extracted JSON:\n```json\n{json.dumps(raw)}\n```"
        adapter = _make_adapter(preamble)
        e = LLMExtractor(adapter=adapter, provider="ollama_local")
        schema = {"type": "object", "properties": {"vendor": {"type": "string"}}}
        output = await e.extract(parsed_doc, schema, {})
        assert output.structured_data == {"vendor": "Acme"}

    async def test_strips_code_fence_when_model_adds_trailing_text(self, parsed_doc):
        from app.adapters.extraction.llm import LLMExtractor
        raw = {"total": 99}
        with_trailing = f"```json\n{json.dumps(raw)}\n```\n\nNote: field was found on page 1."
        adapter = _make_adapter(with_trailing)
        e = LLMExtractor(adapter=adapter, provider="ollama_local")
        schema = {"type": "object", "properties": {"total": {"type": "number"}}}
        output = await e.extract(parsed_doc, schema, {})
        assert output.structured_data == {"total": 99}

    async def test_citations_populated_from_source_fields(self, parsed_doc):
        from app.adapters.extraction.llm import LLMExtractor
        schema = {"type": "object", "properties": {"vendor": {"type": "string"}}}
        raw = {"vendor": "Acme", "vendor__source": {"page_index": 2, "block_id": "blk-1"}}
        adapter = _make_adapter(json.dumps(raw))
        e = LLMExtractor(adapter=adapter, provider="openai")
        output = await e.extract(parsed_doc, schema, {})
        assert len(output.citations) == 1
        assert output.citations[0].field_path == "vendor"


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestRegistryLLM:
    def test_get_extractor_returns_llm_extractor(self):
        from app.adapters.extraction.llm import LLMExtractor
        from app.adapters.extraction.registry import get_extractor
        extractor = get_extractor("llm", {}, {"adapter": _make_adapter(), "provider": "openai"})
        assert isinstance(extractor, LLMExtractor)

    def test_get_extractor_llm_raises_without_adapter(self):
        from app.adapters.extraction.registry import get_extractor
        with pytest.raises(ValueError, match="adapter"):
            get_extractor("llm", {}, {})

    def test_llm_method_in_catalogue(self):
        from app.adapters.extraction.registry import get_known_extractors
        methods = {e["extraction_method"] for e in get_known_extractors()}
        assert "llm" in methods
