"""Unit tests for LLMExtractor (post-rewrite: uses LLMPort, not OpenAICompatMixin)."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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


def _make_adapter(content: str) -> MagicMock:
    adapter = MagicMock()
    adapter.complete = AsyncMock(return_value=CompletionResult(
        content=content,
        usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        latency_ms=100.0, model="llama3.2:8b", provider="ollama_local",
    ))
    return adapter


class TestLLMExtractorProperties:
    def test_extractor_type(self):
        from app.adapters.extraction.llm import LLMExtractor
        assert LLMExtractor().extractor_type == "llm"

    def test_display_name(self):
        from app.adapters.extraction.llm import LLMExtractor
        assert LLMExtractor().display_name == "LLM"

    def test_default_provider_is_ollama_local(self):
        from app.adapters.extraction.llm import LLMExtractor
        e = LLMExtractor()
        assert e._default_provider == "ollama_local"


class TestLLMExtractorBuildMessages:
    @pytest.fixture
    def extractor(self):
        from app.adapters.extraction.llm import LLMExtractor
        return LLMExtractor()

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


class TestLLMExtractorExtract:
    @pytest.fixture
    def extractor(self):
        from app.adapters.extraction.llm import LLMExtractor
        return LLMExtractor()

    @pytest.fixture
    def parsed_doc(self):
        return _make_parsed_doc()

    async def test_uses_create_adapter_with_resolved_provider(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        adapter = _make_adapter("{}")
        with patch("app.adapters.extraction.llm.create_adapter", return_value=adapter) as mock_ca:
            await extractor.extract(parsed_doc, schema, {"provider": "anthropic", "api_key": "key"})
        mock_ca.assert_called_once_with("anthropic", "key", None)

    async def test_uses_default_provider_when_not_in_config(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        adapter = _make_adapter("{}")
        with patch("app.adapters.extraction.llm.create_adapter", return_value=adapter) as mock_ca:
            await extractor.extract(parsed_doc, schema, {})
        provider_arg = mock_ca.call_args.args[0]
        assert provider_arg == "ollama_local"

    async def test_passes_base_url_to_create_adapter(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        adapter = _make_adapter("{}")
        with patch("app.adapters.extraction.llm.create_adapter", return_value=adapter) as mock_ca:
            await extractor.extract(
                parsed_doc, schema,
                {"provider": "openai", "api_key": "k", "base_url": "https://custom.host/v1"},
            )
        assert mock_ca.call_args.args[2] == "https://custom.host/v1"

    async def test_max_tokens_forwarded_via_llm_config(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        adapter = _make_adapter("{}")
        llm_cfg_dict = {"provider": "ollama_local", "model": "llama3.2:8b", "max_tokens": 8192}
        with patch("app.adapters.extraction.llm.create_adapter", return_value=adapter):
            await extractor.extract(parsed_doc, schema, {"llm_config": llm_cfg_dict})
        llm_config_arg = adapter.complete.call_args.args[1]
        assert llm_config_arg.max_tokens == 8192

    async def test_structured_output_schema_passed_for_json_schema_mode(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {"total": {"type": "number"}}}
        adapter = _make_adapter('{"total": 99}')
        with patch("app.adapters.extraction.llm.create_adapter", return_value=adapter):
            await extractor.extract(parsed_doc, schema, {})
        llm_config_arg = adapter.complete.call_args.args[1]
        assert llm_config_arg.structured_output_mode == "json_schema"
        assert llm_config_arg.structured_output_schema is not None

    async def test_returns_structured_data_without_source_fields(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {"total": {"type": "number"}}}
        raw = {"total": 500, "total__source": {"page_index": 1}}
        adapter = _make_adapter(json.dumps(raw))
        with patch("app.adapters.extraction.llm.create_adapter", return_value=adapter):
            output = await extractor.extract(parsed_doc, schema, {})
        assert output.structured_data == {"total": 500}
        assert output.source_parse_run_id == UUID(PARSE_RUN_ID)

    async def test_usage_recorded_in_extraction_metadata(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        adapter = _make_adapter("{}")
        with patch("app.adapters.extraction.llm.create_adapter", return_value=adapter):
            output = await extractor.extract(parsed_doc, schema, {})
        assert output.extraction_metadata["usage"]["prompt_tokens"] == 10
        assert output.extraction_metadata["usage"]["completion_tokens"] == 20

    async def test_raises_extraction_error_on_non_json_response(self, extractor, parsed_doc):
        from app.ports.data_extraction import ExtractionError
        schema = {"type": "object", "properties": {}}
        adapter = _make_adapter("not valid json at all")
        with patch("app.adapters.extraction.llm.create_adapter", return_value=adapter):
            with pytest.raises(ExtractionError, match="non-JSON"):
                await extractor.extract(parsed_doc, schema, {})

    async def test_citations_populated_from_source_fields(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {"vendor": {"type": "string"}}}
        raw = {"vendor": "Acme", "vendor__source": {"page_index": 2, "block_id": "blk-1"}}
        adapter = _make_adapter(json.dumps(raw))
        with patch("app.adapters.extraction.llm.create_adapter", return_value=adapter):
            output = await extractor.extract(parsed_doc, schema, {})
        assert len(output.citations) == 1
        assert output.citations[0].field_path == "vendor"


class TestRegistryLLM:
    def test_get_extractor_returns_llm_extractor(self):
        from app.adapters.extraction.llm import LLMExtractor
        from app.adapters.extraction.registry import get_extractor
        extractor = get_extractor("llm", {})
        assert isinstance(extractor, LLMExtractor)

    def test_llm_method_in_catalogue(self):
        from app.adapters.extraction.registry import get_known_extractors
        methods = {e["extraction_method"] for e in get_known_extractors()}
        assert "llm" in methods
