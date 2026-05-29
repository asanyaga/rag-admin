"""Tests for OpenAI-compatible adapters (Ollama, Groq)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.llm.ollama_adapter import OllamaAdapter
from app.services.llm.groq_adapter import GroqAdapter
from app.services.llm.types import LLMConfig, TokenUsage, CompletionResult


def test_ollama_adapter_init():
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1")
    assert str(adapter.client.base_url) == "http://localhost:11434/v1/"


def test_ollama_adapter_default_base_url():
    adapter = OllamaAdapter()
    assert "11434" in str(adapter.client.base_url)


def test_groq_adapter_init():
    adapter = GroqAdapter(api_key="test-key")
    assert "groq.com" in str(adapter.client.base_url)


def _make_completion_response(content="{}"):
    resp = MagicMock()
    resp.choices[0].message.content = content
    resp.usage.prompt_tokens = 5
    resp.usage.completion_tokens = 10
    resp.usage.total_tokens = 15
    return resp


@pytest.mark.asyncio
async def test_ollama_complete_json_schema_sends_no_response_format():
    """json_schema degrades to prompt_only — Ollama mishandles response_format."""
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1")
    adapter.client = MagicMock()
    adapter.client.chat.completions.create = AsyncMock(
        return_value=_make_completion_response()
    )
    config = LLMConfig(
        provider="ollama_local", model="llama3.2:8b",
        structured_output_mode="json_schema",
        structured_output_schema={"type": "object"},
    )
    await adapter.complete([{"role": "user", "content": "hi"}], config)
    kwargs = adapter.client.chat.completions.create.call_args.kwargs
    assert "response_format" not in kwargs


@pytest.mark.asyncio
async def test_ollama_complete_json_mode_sends_json_object():
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1")
    adapter.client = MagicMock()
    adapter.client.chat.completions.create = AsyncMock(
        return_value=_make_completion_response()
    )
    config = LLMConfig(
        provider="ollama_local", model="llama3.2:8b",
        structured_output_mode="json_mode",
    )
    await adapter.complete([{"role": "user", "content": "hi"}], config)
    kwargs = adapter.client.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_ollama_complete_none_mode_sends_no_response_format():
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1")
    adapter.client = MagicMock()
    adapter.client.chat.completions.create = AsyncMock(
        return_value=_make_completion_response()
    )
    config = LLMConfig(provider="ollama_local", model="llama3.2:8b")
    await adapter.complete([{"role": "user", "content": "hi"}], config)
    kwargs = adapter.client.chat.completions.create.call_args.kwargs
    assert "response_format" not in kwargs
