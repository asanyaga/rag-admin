"""Unit tests for LLMExtractor."""
import json
import pytest
from unittest.mock import AsyncMock, patch
from uuid import UUID

PARSE_RUN_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _make_parsed_doc():
    from app.cdm.models import ParsedDocument, Page
    pages = [Page(index=0, block_ids=[])]
    return ParsedDocument(
        id="doc-1",
        source_document_id="src-1",
        parse_run_id=PARSE_RUN_ID,
        page_count=1,
        pages=pages,
        blocks=[],
    )


class TestLLMExtractorProperties:
    def test_extractor_type(self):
        from app.adapters.extraction.llm import LLMExtractor
        assert LLMExtractor().extractor_type == "llm"

    def test_display_name(self):
        from app.adapters.extraction.llm import LLMExtractor
        assert LLMExtractor().display_name == "LLM"


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

    def test_document_context_interpolated(self, extractor):
        msgs = extractor._build_messages({"type": "object"}, "the document", {})
        assert "the document" in msgs[1]["content"]

    def test_no_unresolved_format_placeholders(self, extractor):
        msgs = extractor._build_messages({"type": "object"}, "ctx", {})
        user_content = msgs[1]["content"]
        assert "{schema_json}" not in user_content
        assert "{document_context}" not in user_content

    def test_custom_user_prompt_template(self, extractor):
        msgs = extractor._build_messages(
            {"type": "object"},
            "ctx",
            {"user_prompt_template": "Schema: {schema_json} | Doc: {document_context}"},
        )
        assert msgs[1]["content"].startswith("Schema:")
        assert "ctx" in msgs[1]["content"]

    def test_two_messages_system_then_user(self, extractor):
        msgs = extractor._build_messages({"type": "object"}, "ctx", {})
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"


class TestLLMExtractorExtract:
    @pytest.fixture
    def extractor(self):
        from app.adapters.extraction.llm import LLMExtractor
        return LLMExtractor(default_endpoint="http://localhost:11434/v1")

    @pytest.fixture
    def parsed_doc(self):
        return _make_parsed_doc()

    async def test_returns_structured_data_without_source_fields(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {"total": {"type": "number"}}}
        raw = {"total": 500, "total__source": {"page_index": 1}}
        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value=raw):
            output = await extractor.extract(parsed_doc, schema, {"model": "llama3.2:8b"})
        assert output.structured_data == {"total": 500}
        assert output.source_parse_run_id == UUID(PARSE_RUN_ID)

    async def test_llm_config_dict_sets_model_and_temperature(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        llm_config_dict = {
            "provider": "ollama_local",
            "model": "mistral:7b",
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}) as mock_call:
            await extractor.extract(parsed_doc, schema, {"llm_config": llm_config_dict})
        _, _, passed_cfg = mock_call.call_args.args
        assert passed_cfg["model"] == "mistral:7b"
        assert passed_cfg["temperature"] == 0.3
        assert passed_cfg["max_tokens"] == 2048

    async def test_llm_config_system_prompt_overrides_default(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        llm_config_dict = {"system_prompt": "Custom override.", "model": "m"}
        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}) as mock_call:
            await extractor.extract(parsed_doc, schema, {"llm_config": llm_config_dict})
        messages, _, _ = mock_call.call_args.args
        assert messages[0]["content"] == "Custom override."

    async def test_no_llm_config_uses_default_model(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}) as mock_call:
            await extractor.extract(parsed_doc, schema, {})
        _, _, passed_cfg = mock_call.call_args.args
        assert passed_cfg["model"] == "llama3.2:8b"

    async def test_inject_block_ids_false_by_default(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}), \
             patch("app.adapters.extraction.llm.build_extraction_context") as mock_ctx:
            mock_ctx.return_value = "ctx"
            await extractor.extract(parsed_doc, schema, {})
        mock_ctx.assert_called_once_with(parsed_doc, False)

    async def test_inject_block_ids_true_when_set(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}), \
             patch("app.adapters.extraction.llm.build_extraction_context") as mock_ctx:
            mock_ctx.return_value = "ctx"
            await extractor.extract(parsed_doc, schema, {"inject_block_ids": True})
        mock_ctx.assert_called_once_with(parsed_doc, True)

    async def test_citations_populated_from_source_fields(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {"vendor": {"type": "string"}}}
        raw = {"vendor": "Acme", "vendor__source": {"page_index": 2, "block_id": "blk-1"}}
        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value=raw):
            output = await extractor.extract(parsed_doc, schema, {"model": "m"})
        assert len(output.citations) == 1
        assert output.citations[0].field_path == "vendor"

    async def test_default_endpoint_applied_when_not_in_config(self, parsed_doc):
        from app.adapters.extraction.llm import LLMExtractor
        extractor = LLMExtractor(default_endpoint="http://myhost:11434/v1", default_api_key="key")
        schema = {"type": "object", "properties": {}}
        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}) as mock_call:
            await extractor.extract(parsed_doc, schema, {})
        _, _, passed_cfg = mock_call.call_args.args
        assert passed_cfg["endpoint"] == "http://myhost:11434/v1"
        assert passed_cfg["api_key"] == "key"

    async def test_per_run_endpoint_overrides_default(self, parsed_doc):
        from app.adapters.extraction.llm import LLMExtractor
        extractor = LLMExtractor(default_endpoint="http://default:11434/v1")
        schema = {"type": "object", "properties": {}}
        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}) as mock_call:
            await extractor.extract(parsed_doc, schema, {"endpoint": "http://override:11434/v1"})
        _, _, passed_cfg = mock_call.call_args.args
        assert passed_cfg["endpoint"] == "http://override:11434/v1"
