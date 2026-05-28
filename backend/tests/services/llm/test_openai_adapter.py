import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from app.services.llm.types import LLMConfig, TokenUsage


def _make_response(content="ok"):
    resp = MagicMock()
    resp.choices[0].message.content = content
    resp.usage.prompt_tokens = 10
    resp.usage.completion_tokens = 20
    resp.usage.total_tokens = 30
    return resp


def _make_adapter(api_key="test"):
    from app.services.llm.openai_adapter import OpenAIAdapter
    adapter = OpenAIAdapter(api_key=api_key)
    adapter.client = MagicMock()
    return adapter


@pytest.mark.asyncio
async def test_complete_json_schema_sends_response_format():
    adapter = _make_adapter()
    adapter.client.chat.completions.create = AsyncMock(return_value=_make_response('{"x":1}'))
    schema = {"type": "object", "properties": {"x": {"type": "number"}}}
    config = LLMConfig(
        provider="openai", model="gpt-4o",
        structured_output_mode="json_schema",
        structured_output_schema=schema,
    )
    await adapter.complete([{"role": "user", "content": "hi"}], config)
    kwargs = adapter.client.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["response_format"]["json_schema"]["schema"] == schema
    assert kwargs["response_format"]["json_schema"]["strict"] is True


@pytest.mark.asyncio
async def test_complete_json_mode_sends_json_object():
    adapter = _make_adapter()
    adapter.client.chat.completions.create = AsyncMock(return_value=_make_response('{}'))
    config = LLMConfig(provider="openai", model="gpt-4o", structured_output_mode="json_mode")
    await adapter.complete([{"role": "user", "content": "hi"}], config)
    kwargs = adapter.client.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_complete_prompt_only_sends_no_response_format():
    adapter = _make_adapter()
    adapter.client.chat.completions.create = AsyncMock(return_value=_make_response("hello"))
    config = LLMConfig(provider="openai", model="gpt-4o", structured_output_mode="prompt_only")
    await adapter.complete([{"role": "user", "content": "hi"}], config)
    kwargs = adapter.client.chat.completions.create.call_args.kwargs
    assert "response_format" not in kwargs


@pytest.mark.asyncio
async def test_complete_none_mode_sends_no_response_format():
    adapter = _make_adapter()
    adapter.client.chat.completions.create = AsyncMock(return_value=_make_response("hello"))
    config = LLMConfig(provider="openai", model="gpt-4o")
    await adapter.complete([{"role": "user", "content": "hi"}], config)
    kwargs = adapter.client.chat.completions.create.call_args.kwargs
    assert "response_format" not in kwargs


@pytest.mark.asyncio
async def test_complete_raises_llm_connection_error_on_connection_failure():
    import openai
    from app.services.llm.types import LLMConnectionError
    adapter = _make_adapter()
    adapter.client.chat.completions.create = AsyncMock(
        side_effect=openai.APIConnectionError(request=MagicMock())
    )
    config = LLMConfig(provider="openai", model="gpt-4o")
    with pytest.raises(LLMConnectionError):
        await adapter.complete([{"role": "user", "content": "hi"}], config)


@pytest.mark.asyncio
async def test_stream_completion_returns_stream_response():
    from app.services.llm.types import StreamResponse
    adapter = _make_adapter()

    async def _fake_stream():
        chunk = MagicMock()
        chunk.choices = [MagicMock()]
        chunk.choices[0].delta.content = "hello"
        chunk.usage = None
        yield chunk
        # final usage chunk
        usage_chunk = MagicMock()
        usage_chunk.choices = []
        usage_chunk.usage = MagicMock(prompt_tokens=5, completion_tokens=10, total_tokens=15)
        yield usage_chunk

    adapter.client.chat.completions.create = AsyncMock(return_value=_fake_stream())
    config = LLMConfig(provider="openai", model="gpt-4o")
    result = await adapter.stream_completion([{"role": "user", "content": "hi"}], config)
    assert isinstance(result, StreamResponse)


@pytest.mark.asyncio
async def test_stream_completion_yields_tokens_and_captures_usage():
    from app.services.llm.types import StreamResponse
    adapter = _make_adapter()

    async def _fake_stream():
        for word in ["foo", " bar"]:
            chunk = MagicMock()
            chunk.choices = [MagicMock()]
            chunk.choices[0].delta.content = word
            chunk.usage = None
            yield chunk
        usage_chunk = MagicMock()
        usage_chunk.choices = []
        usage_chunk.usage = MagicMock(prompt_tokens=5, completion_tokens=2, total_tokens=7)
        yield usage_chunk

    adapter.client.chat.completions.create = AsyncMock(return_value=_fake_stream())
    config = LLMConfig(provider="openai", model="gpt-4o")
    sr = await adapter.stream_completion([{"role": "user", "content": "hi"}], config)
    tokens = [t async for t in sr]
    assert tokens == ["foo", " bar"]
    assert sr.usage is not None
    assert sr.usage.prompt_tokens == 5
    assert sr.usage.completion_tokens == 2
