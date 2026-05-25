"""Unit tests for OpenAICompatMixin and OllamaExtractor."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.ports.data_extraction import ExtractionError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PARSE_RUN_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _make_parsed_doc(blocks=None):
    from app.cdm.models import ParsedDocument, Page
    blocks = blocks or []
    pages = [Page(index=0, block_ids=[])]
    return ParsedDocument(
        id="doc-1",
        source_document_id="src-1",
        parse_run_id=PARSE_RUN_ID,
        page_count=1,
        pages=pages,
        blocks=blocks,
    )


def _mock_response(content: str):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


# ---------------------------------------------------------------------------
# OpenAICompatMixin
# ---------------------------------------------------------------------------

class TestBuildClient:
    def test_sets_base_url_and_default_api_key(self):
        from app.adapters.extraction.openai_compat_mixin import OpenAICompatMixin

        class Concrete(OpenAICompatMixin):
            pass

        mixin = Concrete()
        client = mixin._build_client("http://localhost:11434/v1", None)
        assert "localhost:11434" in str(client.base_url)
        assert client.api_key == "ollama"

    def test_uses_provided_api_key(self):
        from app.adapters.extraction.openai_compat_mixin import OpenAICompatMixin

        class Concrete(OpenAICompatMixin):
            pass

        mixin = Concrete()
        client = mixin._build_client("http://localhost:11434/v1", "my-key")
        assert client.api_key == "my-key"


class TestCallModel:
    @pytest.fixture
    def mixin(self):
        from app.adapters.extraction.openai_compat_mixin import OpenAICompatMixin

        class Concrete(OpenAICompatMixin):
            pass

        return Concrete()

    async def test_json_schema_mode_sends_response_format(self, mixin):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_response('{"key": "val"}')
        )
        with patch.object(mixin, "_build_client", return_value=mock_client):
            result = await mixin._call_model(
                messages=[{"role": "user", "content": "x"}],
                augmented_schema={"type": "object", "properties": {}},
                config={
                    "model": "llama3.2:8b",
                    "endpoint": "http://localhost:11434/v1",
                    "structured_output_mode": "json_schema",
                },
            )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"]["type"] == "json_schema"
        assert call_kwargs["response_format"]["json_schema"]["name"] == "extraction_result"
        assert call_kwargs["response_format"]["json_schema"]["strict"] is True
        assert result == {"key": "val"}

    async def test_json_mode_sends_json_object_response_format(self, mixin):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_response('{"x": 1}')
        )
        with patch.object(mixin, "_build_client", return_value=mock_client):
            await mixin._call_model(
                messages=[],
                augmented_schema={},
                config={
                    "model": "m",
                    "endpoint": "http://localhost:11434/v1",
                    "structured_output_mode": "json_mode",
                },
            )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}

    async def test_prompt_only_mode_omits_response_format(self, mixin):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_response('{"x": 1}')
        )
        with patch.object(mixin, "_build_client", return_value=mock_client):
            await mixin._call_model(
                messages=[],
                augmented_schema={},
                config={
                    "model": "m",
                    "endpoint": "http://localhost:11434/v1",
                    "structured_output_mode": "prompt_only",
                },
            )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "response_format" not in call_kwargs

    async def test_non_json_response_raises_extraction_error(self, mixin):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_response("Sorry, I cannot extract this.")
        )
        with patch.object(mixin, "_build_client", return_value=mock_client):
            with pytest.raises(ExtractionError, match="non-JSON"):
                await mixin._call_model(
                    messages=[],
                    augmented_schema={},
                    config={
                        "model": "m",
                        "endpoint": "http://localhost:11434/v1",
                        "structured_output_mode": "prompt_only",
                    },
                )

    async def test_connection_error_raises_extraction_error(self, mixin):
        import openai

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=openai.APIConnectionError(request=MagicMock())
        )
        with patch.object(mixin, "_build_client", return_value=mock_client):
            with pytest.raises(ExtractionError, match="Cannot connect to Ollama"):
                await mixin._call_model(
                    messages=[],
                    augmented_schema={},
                    config={
                        "model": "m",
                        "endpoint": "http://localhost:11434/v1",
                        "structured_output_mode": "json_schema",
                    },
                )

    async def test_bad_request_error_logs_warning_and_reraises(self, mixin):
        import openai

        mock_client = AsyncMock()
        bad_request = openai.BadRequestError(
            message="unsupported",
            response=MagicMock(status_code=400, headers={}),
            body={"error": {"message": "unsupported"}},
        )
        mock_client.chat.completions.create = AsyncMock(side_effect=bad_request)
        with patch.object(mixin, "_build_client", return_value=mock_client):
            with pytest.raises(openai.BadRequestError):
                await mixin._call_model(
                    messages=[],
                    augmented_schema={},
                    config={
                        "model": "m",
                        "endpoint": "http://localhost:11434/v1",
                        "structured_output_mode": "json_schema",
                    },
                )

    async def test_temperature_passed_to_api(self, mixin):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_response('{}')
        )
        with patch.object(mixin, "_build_client", return_value=mock_client):
            await mixin._call_model(
                messages=[],
                augmented_schema={},
                config={
                    "model": "m",
                    "endpoint": "http://localhost:11434/v1",
                    "temperature": 0.7,
                    "structured_output_mode": "prompt_only",
                },
            )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.7

    async def test_default_temperature_is_zero(self, mixin):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_response('{}')
        )
        with patch.object(mixin, "_build_client", return_value=mock_client):
            await mixin._call_model(
                messages=[],
                augmented_schema={},
                config={
                    "model": "m",
                    "endpoint": "http://localhost:11434/v1",
                    "structured_output_mode": "prompt_only",
                },
            )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.0


# ---------------------------------------------------------------------------
# OllamaExtractor
# ---------------------------------------------------------------------------

class TestOllamaExtractorProperties:
    def test_extractor_type(self):
        from app.adapters.extraction.ollama import OllamaExtractor
        assert OllamaExtractor().extractor_type == "ollama"

    def test_display_name(self):
        from app.adapters.extraction.ollama import OllamaExtractor
        assert OllamaExtractor().display_name == "Ollama"


class TestBuildMessages:
    @pytest.fixture
    def extractor(self):
        from app.adapters.extraction.ollama import OllamaExtractor
        return OllamaExtractor()

    def test_uses_default_system_prompt(self, extractor):
        from app.adapters.extraction.ollama import DEFAULT_SYSTEM_PROMPT
        msgs = extractor._build_messages({"type": "object"}, "ctx", {})
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == DEFAULT_SYSTEM_PROMPT

    def test_uses_custom_system_prompt(self, extractor):
        msgs = extractor._build_messages(
            {"type": "object"}, "ctx", {"system_prompt": "Custom system"}
        )
        assert msgs[0]["content"] == "Custom system"

    def test_schema_json_interpolated_in_user_message(self, extractor):
        aug_schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        msgs = extractor._build_messages(aug_schema, "doc text", {})
        user_content = msgs[1]["content"]
        assert json.dumps(aug_schema, indent=2) in user_content

    def test_document_context_interpolated_in_user_message(self, extractor):
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

    def test_messages_have_two_items(self, extractor):
        msgs = extractor._build_messages({"type": "object"}, "ctx", {})
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"


class TestOllamaExtractorExtract:
    @pytest.fixture
    def extractor(self):
        from app.adapters.extraction.ollama import OllamaExtractor
        return OllamaExtractor()

    @pytest.fixture
    def parsed_doc(self):
        return _make_parsed_doc()

    async def test_returns_correct_extraction_output(self, extractor, parsed_doc):
        from uuid import UUID
        schema = {"type": "object", "properties": {"total": {"type": "number"}}}
        raw_response = {"total": 500, "total__source": {"page_index": 1}}

        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value=raw_response):
            output = await extractor.extract(parsed_doc, schema, {"model": "llama3.2:8b"})

        assert output.structured_data == {"total": 500}
        assert output.source_parse_run_id == UUID(PARSE_RUN_ID)
        assert output.provider_response_raw is None
        assert output.extraction_metadata["model"] == "llama3.2:8b"
        assert "latency_ms" in output.extraction_metadata
        assert isinstance(output.extraction_metadata["latency_ms"], int)

    async def test_citations_populated_from_source_fields(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {"vendor": {"type": "string"}}}
        raw_response = {
            "vendor": "Acme Corp",
            "vendor__source": {"page_index": 2, "block_id": "blk-1"},
        }

        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value=raw_response):
            output = await extractor.extract(parsed_doc, schema, {"model": "m"})

        assert len(output.citations) == 1
        assert output.citations[0].field_path == "vendor"
        assert output.citations[0].page_index == 2
        assert output.citations[0].block_ids == ["blk-1"]

    async def test_inject_block_ids_false_by_default(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}), \
             patch("app.adapters.extraction.ollama.build_extraction_context") as mock_ctx:
            mock_ctx.return_value = "ctx"
            await extractor.extract(parsed_doc, schema, {"model": "m"})

        mock_ctx.assert_called_once_with(parsed_doc, False)

    async def test_inject_block_ids_true_when_configured(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}), \
             patch("app.adapters.extraction.ollama.build_extraction_context") as mock_ctx:
            mock_ctx.return_value = "ctx"
            await extractor.extract(parsed_doc, schema, {"model": "m", "inject_block_ids": True})

        mock_ctx.assert_called_once_with(parsed_doc, True)

    async def test_call_model_receives_augmented_schema(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}) as mock_call:
            await extractor.extract(parsed_doc, schema, {"model": "m"})

        _, augmented_schema, _ = mock_call.call_args.args
        assert "x__source" in augmented_schema["properties"]

    async def test_call_model_receives_cfg(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        cfg = {"model": "llama3.2:8b", "structured_output_mode": "json_mode"}
        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}) as mock_call:
            await extractor.extract(parsed_doc, schema, cfg)

        _, _, passed_cfg = mock_call.call_args.args
        assert passed_cfg["structured_output_mode"] == "json_mode"

    async def test_empty_config_uses_defaults(self, extractor, parsed_doc):
        schema = {"type": "object", "properties": {}}
        with patch.object(extractor, "_call_model", new_callable=AsyncMock, return_value={}):
            output = await extractor.extract(parsed_doc, schema)  # config=None

        assert output.structured_data == {}
        assert output.citations == []


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class TestRegistryOllama:
    def test_get_extractor_returns_ollama_extractor(self):
        from app.adapters.extraction.ollama import OllamaExtractor
        from app.adapters.extraction.registry import get_extractor

        extractor = get_extractor("ollama", {})
        assert isinstance(extractor, OllamaExtractor)
        assert extractor.extractor_type == "ollama"

    def test_ollama_extractor_needs_no_credentials(self):
        from app.adapters.extraction.registry import get_extractor

        # No credentials, no dependencies — should construct fine
        extractor = get_extractor("ollama", {})
        assert extractor is not None
