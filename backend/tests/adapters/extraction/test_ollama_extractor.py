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
