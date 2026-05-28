import pytest
from typing import AsyncIterator


def test_llm_config_structured_output_mode_defaults_to_none():
    from app.services.llm.types import LLMConfig
    config = LLMConfig(provider="openai", model="gpt-4o")
    assert config.structured_output_mode is None
    assert config.structured_output_schema is None


def test_llm_config_structured_output_mode_json_schema():
    from app.services.llm.types import LLMConfig
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    config = LLMConfig(
        provider="openai",
        model="gpt-4o",
        structured_output_mode="json_schema",
        structured_output_schema=schema,
    )
    assert config.structured_output_mode == "json_schema"
    assert config.structured_output_schema == schema


def test_llm_config_json_mode_field_removed():
    """json_mode bool field must not exist — callers use structured_output_mode."""
    from app.services.llm.types import LLMConfig
    config = LLMConfig(provider="openai", model="gpt-4o")
    assert not hasattr(config, "json_mode")


def test_stream_response_usage_starts_none():
    from app.services.llm.types import StreamResponse
    sr = StreamResponse()
    assert sr.usage is None


def test_stream_response_is_async_iterable_after_source_set():
    from app.services.llm.types import StreamResponse

    async def _gen():
        yield "hello"
        yield " world"

    sr = StreamResponse()
    sr._source = _gen()
    assert hasattr(sr, "__aiter__")


def test_stream_response_raises_without_source():
    from app.services.llm.types import StreamResponse
    import pytest
    sr = StreamResponse()
    with pytest.raises(RuntimeError, match="no token source"):
        sr.__aiter__()


def test_llm_connection_error_is_exception():
    from app.services.llm.types import LLMConnectionError
    assert issubclass(LLMConnectionError, Exception)
    err = LLMConnectionError("host unreachable")
    assert "host unreachable" in str(err)
