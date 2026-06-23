import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.llm.types import LLMConfig, TokenUsage


def _make_response(text="ok", stop_reason="end_turn"):
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.usage.input_tokens = 10
    resp.usage.output_tokens = 20
    resp.stop_reason = stop_reason
    return resp


def _make_adapter():
    from app.services.llm.anthropic_adapter import AnthropicAdapter
    adapter = AnthropicAdapter(api_key="test")
    adapter.client = MagicMock()
    return adapter


@pytest.mark.asyncio
async def test_complete_json_mode_appends_json_instruction_to_system():
    adapter = _make_adapter()
    adapter.client.messages.create = AsyncMock(return_value=_make_response("{}"))
    config = LLMConfig(
        provider="anthropic", model="claude-3-5-sonnet-20241022",
        structured_output_mode="json_mode",
    )
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Extract data."},
    ]
    await adapter.complete(messages, config)
    kwargs = adapter.client.messages.create.call_args.kwargs
    assert "json" in kwargs["system"].lower()
    assert "JSON" in kwargs["system"] or "json" in kwargs["system"]


@pytest.mark.asyncio
async def test_complete_json_schema_raises_not_implemented():
    adapter = _make_adapter()
    config = LLMConfig(
        provider="anthropic", model="claude-3-5-sonnet-20241022",
        structured_output_mode="json_schema",
        structured_output_schema={"type": "object"},
    )
    with pytest.raises(NotImplementedError, match="json_schema"):
        await adapter.complete([{"role": "user", "content": "hi"}], config)


@pytest.mark.asyncio
async def test_complete_prompt_only_no_extra_system_content():
    adapter = _make_adapter()
    adapter.client.messages.create = AsyncMock(return_value=_make_response("hello"))
    config = LLMConfig(
        provider="anthropic", model="claude-3-5-sonnet-20241022",
        structured_output_mode="prompt_only",
    )
    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "Hi"},
    ]
    await adapter.complete(messages, config)
    kwargs = adapter.client.messages.create.call_args.kwargs
    assert kwargs["system"] == "Be concise."


@pytest.mark.asyncio
async def test_complete_raises_llm_connection_error():
    import anthropic
    from app.services.llm.types import LLMConnectionError
    adapter = _make_adapter()
    adapter.client.messages.create = AsyncMock(
        side_effect=anthropic.APIConnectionError(request=MagicMock())
    )
    config = LLMConfig(provider="anthropic", model="claude-3-5-sonnet-20241022")
    with pytest.raises(LLMConnectionError):
        await adapter.complete([{"role": "user", "content": "hi"}], config)


@pytest.mark.asyncio
async def test_complete_threads_stop_reason():
    adapter = _make_adapter()
    adapter.client.messages.create = AsyncMock(
        return_value=_make_response("{}", stop_reason="max_tokens")
    )
    config = LLMConfig(
        provider="anthropic", model="claude-3-5-sonnet-20241022",
        structured_output_mode="json_mode",
    )
    result = await adapter.complete([{"role": "user", "content": "hi"}], config)
    assert result.stop_reason == "max_tokens"


@pytest.mark.asyncio
async def test_complete_translates_429_to_rate_limit_error():
    import anthropic
    from app.services.llm.types import LLMRateLimitError
    adapter = _make_adapter()
    resp = MagicMock()
    resp.headers = {"retry-after": "3"}
    err = anthropic.RateLimitError("rate", response=resp, body=None)
    adapter.client.messages.create = AsyncMock(side_effect=err)
    config = LLMConfig(
        provider="anthropic", model="claude-3-5-sonnet-20241022",
        structured_output_mode="json_mode",
    )
    with pytest.raises(LLMRateLimitError) as exc:
        await adapter.complete([{"role": "user", "content": "hi"}], config)
    assert exc.value.retry_after == 3.0


@pytest.mark.asyncio
async def test_stream_completion_returns_stream_response():
    from app.services.llm.types import StreamResponse
    adapter = _make_adapter()

    mock_stream_ctx = MagicMock()
    final_msg = MagicMock()
    final_msg.usage.input_tokens = 5
    final_msg.usage.output_tokens = 10

    async def _text_stream():
        yield "hello"

    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_ctx)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_stream_ctx.text_stream = _text_stream()
    mock_stream_ctx.get_final_message = AsyncMock(return_value=final_msg)
    adapter.client.messages.stream = MagicMock(return_value=mock_stream_ctx)

    config = LLMConfig(provider="anthropic", model="claude-3-5-sonnet-20241022")
    result = await adapter.stream_completion([{"role": "user", "content": "hi"}], config)
    assert isinstance(result, StreamResponse)
    tokens = [t async for t in result]
    assert tokens == ["hello"]
    assert result.usage is not None
    assert result.usage.prompt_tokens == 5
    assert result.usage.completion_tokens == 10
