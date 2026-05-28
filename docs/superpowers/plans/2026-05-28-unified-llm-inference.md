# Unified LLM Inference Abstraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace two divergent LLM inference paths with a single `LLMPort`-based abstraction used consistently by every feature, fixing all provider-routing bugs in the process.

**Architecture:** `LLMConfig` carries structured-output intent; each adapter fulfils it in a provider-appropriate way. A single `resolve_provider_credentials()` function handles all key/URL lookup. `create_adapter()` is the only way to instantiate an adapter — no feature imports a concrete adapter class directly.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, `openai` SDK, `anthropic` SDK, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-05-28-unified-llm-inference-design.md`

---

## Task 1: Foundation — LLMConfig, StreamResponse, LLMConnectionError, LLMPort

**Files:**
- Modify: `backend/app/services/llm/types.py`
- Modify: `backend/app/services/llm/port.py`
- Create: `backend/tests/services/llm/test_types.py`

- [ ] **Write the failing tests**

```python
# backend/tests/services/llm/test_types.py
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
```

- [ ] **Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/services/llm/test_types.py -v
```

Expected: multiple failures (ImportError or AttributeError).

- [ ] **Implement: rewrite `types.py`**

```python
# backend/app/services/llm/types.py
"""Data types for the LLM abstraction layer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Literal


@dataclass
class LLMConfig:
    """Configuration for an LLM completion request."""
    provider: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 1024
    structured_output_mode: Literal["json_schema", "json_mode", "prompt_only"] | None = None
    structured_output_schema: dict | None = None  # only used when mode == "json_schema"


@dataclass
class TokenUsage:
    """Token usage statistics from a completion."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class CompletionResult:
    """Full result from a non-streaming completion."""
    content: str
    usage: TokenUsage
    latency_ms: float
    model: str
    provider: str


class StreamResponse:
    """Token stream with usage metadata available after exhaustion.

    Adapters set ``_source`` to an async generator that yields str tokens.
    The generator populates ``usage`` as a side-effect when it processes the
    final provider chunk.  Callers iterate normally then read ``.usage``.
    """

    def __init__(self) -> None:
        self.usage: TokenUsage | None = None
        self._source: AsyncIterator[str] | None = None

    def __aiter__(self) -> AsyncIterator[str]:
        if self._source is None:
            raise RuntimeError("StreamResponse has no token source")
        return self._source.__aiter__()


class LLMConnectionError(Exception):
    """Raised when an LLM provider endpoint cannot be reached."""
```

- [ ] **Implement: update `port.py`**

```python
# backend/app/services/llm/port.py
"""Protocol definition for LLM providers."""
from typing import Protocol

from app.services.llm.types import LLMConfig, CompletionResult, StreamResponse


class LLMPort(Protocol):
    """Interface that all LLM adapters must implement."""

    async def stream_completion(
        self,
        messages: list[dict],
        config: LLMConfig,
    ) -> StreamResponse:
        """Return a StreamResponse whose async iteration yields content tokens."""
        ...

    async def complete(
        self,
        messages: list[dict],
        config: LLMConfig,
    ) -> CompletionResult:
        """Non-streaming completion with full result metadata."""
        ...
```

- [ ] **Run tests — expect all green**

```
uv run --directory backend python -m pytest tests/services/llm/test_types.py -v
```

- [ ] **Commit**

```
git add backend/app/services/llm/types.py backend/app/services/llm/port.py backend/tests/services/llm/test_types.py
git commit -m "feat(llm): add StreamResponse, LLMConnectionError; replace json_mode with structured_output_mode"
```

---

## Task 2: OpenAI adapter — structured output, streaming usage, connection errors

**Files:**
- Modify: `backend/app/services/llm/openai_adapter.py`
- Create: `backend/tests/services/llm/test_openai_adapter.py`

- [ ] **Write the failing tests**

```python
# backend/tests/services/llm/test_openai_adapter.py
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
```

- [ ] **Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/services/llm/test_openai_adapter.py -v
```

- [ ] **Implement: rewrite `openai_adapter.py`**

```python
# backend/app/services/llm/openai_adapter.py
"""OpenAI LLM adapter."""
import time
import logging
from typing import AsyncIterator, AsyncGenerator

import openai
from openai import AsyncOpenAI

from app.services.llm.types import (
    LLMConfig, TokenUsage, CompletionResult, StreamResponse, LLMConnectionError,
)

logger = logging.getLogger(__name__)


class OpenAIAdapter:
    """Thin wrapper around the OpenAI chat completions API."""

    _provider_name: str = "openai"

    def __init__(self, api_key: str, base_url: str | None = None):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def complete(
        self,
        messages: list[dict],
        config: LLMConfig,
    ) -> CompletionResult:
        """Non-streaming completion with usage metadata."""
        start = time.monotonic()
        kwargs: dict = dict(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        mode = config.structured_output_mode
        if mode == "json_schema":
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "strict": True,
                    "schema": config.structured_output_schema or {},
                },
            }
        elif mode == "json_mode":
            kwargs["response_format"] = {"type": "json_object"}
        # prompt_only / None: no response_format key

        try:
            response = await self.client.chat.completions.create(**kwargs)
        except openai.APIConnectionError as exc:
            raise LLMConnectionError(str(exc)) from exc

        latency = (time.monotonic() - start) * 1000
        return CompletionResult(
            content=response.choices[0].message.content or "",
            usage=TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ),
            latency_ms=latency,
            model=config.model,
            provider=self._provider_name,
        )

    async def stream_completion(
        self,
        messages: list[dict],
        config: LLMConfig,
    ) -> StreamResponse:
        """Return a StreamResponse. Iterate it for tokens; read .usage after."""
        sr = StreamResponse()
        sr._source = self._stream_tokens(messages, config, sr)
        return sr

    async def _stream_tokens(
        self,
        messages: list[dict],
        config: LLMConfig,
        sr: StreamResponse,
    ) -> AsyncGenerator[str, None]:
        try:
            stream = await self.client.chat.completions.create(
                model=config.model,
                messages=messages,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
        except openai.APIConnectionError as exc:
            raise LLMConnectionError(str(exc)) from exc

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            elif chunk.usage:  # final usage-only chunk (choices=[])
                sr.usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                )
```

- [ ] **Run tests — expect all green**

```
uv run --directory backend python -m pytest tests/services/llm/test_openai_adapter.py -v
```

- [ ] **Commit**

```
git add backend/app/services/llm/openai_adapter.py backend/tests/services/llm/test_openai_adapter.py
git commit -m "feat(llm): OpenAI adapter — structured output modes, StreamResponse, LLMConnectionError"
```

---

## Task 3: Anthropic adapter — structured output, streaming usage, connection errors

**Files:**
- Modify: `backend/app/services/llm/anthropic_adapter.py`
- Create: `backend/tests/services/llm/test_anthropic_adapter.py`

- [ ] **Write the failing tests**

```python
# backend/tests/services/llm/test_anthropic_adapter.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.llm.types import LLMConfig, TokenUsage


def _make_response(text="ok"):
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.usage.input_tokens = 10
    resp.usage.output_tokens = 20
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
```

- [ ] **Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/services/llm/test_anthropic_adapter.py -v
```

- [ ] **Implement: rewrite `anthropic_adapter.py`**

```python
# backend/app/services/llm/anthropic_adapter.py
"""Anthropic LLM adapter."""
import re
import time
import logging
from typing import AsyncGenerator

from anthropic import AsyncAnthropic, BadRequestError, APIConnectionError

from app.services.llm.types import (
    LLMConfig, TokenUsage, CompletionResult, StreamResponse, LLMConnectionError,
)

logger = logging.getLogger(__name__)

_DEPRECATED_PARAM_RE = re.compile(r"`(\w+)`\s+is deprecated")
_JSON_INSTRUCTION = "\n\nRespond with valid JSON only. No markdown, no explanation."


def _strip_deprecated(kwargs: dict, error_msg: str) -> dict | None:
    match = _DEPRECATED_PARAM_RE.search(error_msg)
    if match:
        param = match.group(1)
        if param in kwargs:
            return {k: v for k, v in kwargs.items() if k != param}
    return None


class AnthropicAdapter:
    """Thin wrapper around the Anthropic messages API."""

    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)

    async def complete(
        self,
        messages: list[dict],
        config: LLMConfig,
    ) -> CompletionResult:
        """Non-streaming completion with usage metadata."""
        if config.structured_output_mode == "json_schema":
            raise NotImplementedError(
                "Anthropic does not support json_schema structured output mode. "
                "Use 'json_mode' or 'prompt_only' instead."
            )

        start = time.monotonic()
        system_msg, user_messages = self._split_system(messages)

        if config.structured_output_mode == "json_mode":
            system_msg = (system_msg or "") + _JSON_INSTRUCTION

        kwargs: dict = dict(
            model=config.model,
            messages=user_messages,
            system=system_msg or "",
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

        try:
            response = await self.client.messages.create(**kwargs)
        except BadRequestError as e:
            retried = _strip_deprecated(kwargs, str(e))
            if retried is not None:
                logger.warning("Anthropic deprecated param stripped, retrying: %s", e)
                response = await self.client.messages.create(**retried)
            else:
                raise
        except APIConnectionError as exc:
            raise LLMConnectionError(str(exc)) from exc

        latency = (time.monotonic() - start) * 1000
        content = response.content[0].text if response.content else ""
        return CompletionResult(
            content=content,
            usage=TokenUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            ),
            latency_ms=latency,
            model=config.model,
            provider="anthropic",
        )

    async def stream_completion(
        self,
        messages: list[dict],
        config: LLMConfig,
    ) -> StreamResponse:
        """Return a StreamResponse. Iterate it for tokens; read .usage after."""
        if config.structured_output_mode == "json_schema":
            raise NotImplementedError(
                "Anthropic does not support json_schema structured output mode."
            )

        system_msg, user_messages = self._split_system(messages)
        if config.structured_output_mode == "json_mode":
            system_msg = (system_msg or "") + _JSON_INSTRUCTION

        kwargs: dict = dict(
            model=config.model,
            messages=user_messages,
            system=system_msg or "",
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        sr = StreamResponse()
        sr._source = self._stream_tokens(kwargs, sr)
        return sr

    async def _stream_tokens(
        self, kwargs: dict, sr: StreamResponse
    ) -> AsyncGenerator[str, None]:
        try:
            async with self.client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
                final_msg = await stream.get_final_message()
                sr.usage = TokenUsage(
                    prompt_tokens=final_msg.usage.input_tokens,
                    completion_tokens=final_msg.usage.output_tokens,
                    total_tokens=final_msg.usage.input_tokens + final_msg.usage.output_tokens,
                )
        except BadRequestError as e:
            retried = _strip_deprecated(kwargs, str(e))
            if retried is not None:
                logger.warning("Anthropic deprecated param stripped, retrying: %s", e)
                async with self.client.messages.stream(**retried) as stream:
                    async for text in stream.text_stream:
                        yield text
                    final_msg = await stream.get_final_message()
                    sr.usage = TokenUsage(
                        prompt_tokens=final_msg.usage.input_tokens,
                        completion_tokens=final_msg.usage.output_tokens,
                        total_tokens=final_msg.usage.input_tokens + final_msg.usage.output_tokens,
                    )
        except APIConnectionError as exc:
            raise LLMConnectionError(str(exc)) from exc

    @staticmethod
    def _split_system(messages: list[dict]) -> tuple[str | None, list[dict]]:
        system = None
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)
        return system, user_messages
```

- [ ] **Run tests — expect all green**

```
uv run --directory backend python -m pytest tests/services/llm/test_anthropic_adapter.py -v
```

- [ ] **Commit**

```
git add backend/app/services/llm/anthropic_adapter.py backend/tests/services/llm/test_anthropic_adapter.py
git commit -m "feat(llm): Anthropic adapter — structured output modes, StreamResponse, LLMConnectionError"
```

---

## Task 4: Ollama adapter — structured output modes

**Files:**
- Modify: `backend/app/services/llm/ollama_adapter.py`
- Modify: `backend/tests/services/llm/test_openai_compatible_adapters.py`

- [ ] **Add failing tests to the existing file**

Append to `backend/tests/services/llm/test_openai_compatible_adapters.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.llm.types import LLMConfig, TokenUsage, CompletionResult


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
    from app.services.llm.ollama_adapter import OllamaAdapter
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
    from app.services.llm.ollama_adapter import OllamaAdapter
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
    from app.services.llm.ollama_adapter import OllamaAdapter
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1")
    adapter.client = MagicMock()
    adapter.client.chat.completions.create = AsyncMock(
        return_value=_make_completion_response()
    )
    config = LLMConfig(provider="ollama_local", model="llama3.2:8b")
    await adapter.complete([{"role": "user", "content": "hi"}], config)
    kwargs = adapter.client.chat.completions.create.call_args.kwargs
    assert "response_format" not in kwargs
```

- [ ] **Run tests to confirm new tests fail**

```
uv run --directory backend python -m pytest tests/services/llm/test_openai_compatible_adapters.py -v
```

- [ ] **Implement: rewrite `ollama_adapter.py`**

```python
# backend/app/services/llm/ollama_adapter.py
import time
import logging

import openai

from app.services.llm.openai_adapter import OpenAIAdapter
from app.services.llm.types import CompletionResult, LLMConfig, LLMConnectionError, TokenUsage

logger = logging.getLogger(__name__)


class OllamaAdapter(OpenAIAdapter):
    """OpenAI-compatible adapter for Ollama (local or cloud).

    Local:  base_url="http://localhost:11434/v1", api_key="ollama" (dummy)
    Cloud:  base_url="https://ollama.com/v1",    api_key=<real key>

    json_schema response_format is unreliable on most Ollama models and is
    degraded to prompt_only. json_mode (json_object) is passed through as
    many models do support it.  stream_completion is inherited from
    OpenAIAdapter and works unchanged.
    """

    _provider_name = "ollama"

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
    ):
        super().__init__(api_key=api_key, base_url=base_url)

    async def complete(self, messages: list[dict], config: LLMConfig) -> CompletionResult:
        """Complete, degrading json_schema to prompt_only."""
        start = time.monotonic()
        kwargs: dict = dict(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        # json_schema is unreliable — silently degrade to prompt_only
        # json_mode (json_object) is supported by many Ollama models
        if config.structured_output_mode == "json_mode":
            kwargs["response_format"] = {"type": "json_object"}
        # json_schema / prompt_only / None: no response_format

        try:
            response = await self.client.chat.completions.create(**kwargs)
        except openai.APIConnectionError as exc:
            raise LLMConnectionError(str(exc)) from exc

        latency = (time.monotonic() - start) * 1000
        return CompletionResult(
            content=response.choices[0].message.content or "",
            usage=TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            ),
            latency_ms=latency,
            model=config.model,
            provider=self._provider_name,
        )
```

- [ ] **Run tests — expect all green**

```
uv run --directory backend python -m pytest tests/services/llm/test_openai_compatible_adapters.py -v
```

- [ ] **Commit**

```
git add backend/app/services/llm/ollama_adapter.py backend/tests/services/llm/test_openai_compatible_adapters.py
git commit -m "feat(llm): Ollama adapter — degrade json_schema to prompt_only, support json_mode"
```

---

## Task 5: Factory — add Groq, add base_url parameter

**Files:**
- Modify: `backend/app/services/llm/factory.py`
- Create: `backend/tests/services/llm/test_factory.py`

- [ ] **Write the failing tests**

```python
# backend/tests/services/llm/test_factory.py
import pytest
from unittest.mock import patch


def _patched_settings():
    s = patch("app.services.llm.factory.settings")
    mock = s.start()
    mock.OLLAMA_LOCAL_BASE_URL = "http://localhost:11434/v1"
    mock.OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"
    return s


def test_create_adapter_openai():
    from app.services.llm.openai_adapter import OpenAIAdapter
    from app.services.llm.factory import create_adapter
    p = _patched_settings()
    adapter = create_adapter("openai", "sk-test")
    assert isinstance(adapter, OpenAIAdapter)
    p.stop()


def test_create_adapter_anthropic():
    from app.services.llm.anthropic_adapter import AnthropicAdapter
    from app.services.llm.factory import create_adapter
    p = _patched_settings()
    adapter = create_adapter("anthropic", "sk-ant-test")
    assert isinstance(adapter, AnthropicAdapter)
    p.stop()


def test_create_adapter_groq():
    from app.services.llm.groq_adapter import GroqAdapter
    from app.services.llm.factory import create_adapter
    p = _patched_settings()
    adapter = create_adapter("groq", "gsk-test")
    assert isinstance(adapter, GroqAdapter)
    p.stop()


def test_create_adapter_ollama_local():
    from app.services.llm.ollama_adapter import OllamaAdapter
    from app.services.llm.factory import create_adapter
    p = _patched_settings()
    adapter = create_adapter("ollama_local", "ollama")
    assert isinstance(adapter, OllamaAdapter)
    p.stop()


def test_create_adapter_ollama_cloud():
    from app.services.llm.ollama_adapter import OllamaAdapter
    from app.services.llm.factory import create_adapter
    p = _patched_settings()
    adapter = create_adapter("ollama_cloud", "key")
    assert isinstance(adapter, OllamaAdapter)
    p.stop()


def test_create_adapter_openai_with_custom_base_url():
    from app.services.llm.openai_adapter import OpenAIAdapter
    from app.services.llm.factory import create_adapter
    p = _patched_settings()
    adapter = create_adapter("openai", "sk-test", base_url="https://my-vllm.example.com/v1")
    assert isinstance(adapter, OpenAIAdapter)
    assert "my-vllm" in str(adapter.client.base_url)
    p.stop()


def test_create_adapter_unknown_raises_value_error():
    from app.services.llm.factory import create_adapter
    p = _patched_settings()
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        create_adapter("mistral", "key")
    p.stop()
```

- [ ] **Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/services/llm/test_factory.py -v
```

- [ ] **Implement: rewrite `factory.py`**

```python
# backend/app/services/llm/factory.py
"""Factory for constructing per-request LLM adapters from a provider name + API key."""
from typing import Callable

from app.config import settings
from app.services.llm.port import LLMPort
from app.services.llm.openai_adapter import OpenAIAdapter
from app.services.llm.anthropic_adapter import AnthropicAdapter
from app.services.llm.ollama_adapter import OllamaAdapter
from app.services.llm.groq_adapter import GroqAdapter

# Each value is callable (api_key: str, base_url: str | None) -> LLMPort.
# To add a new provider: one line here, nothing else changes.
_ADAPTER_FACTORIES: dict[str, Callable[[str, str | None], LLMPort]] = {
    "openai": lambda api_key, base_url: OpenAIAdapter(api_key=api_key, base_url=base_url),
    "anthropic": lambda api_key, base_url: AnthropicAdapter(api_key=api_key),
    "groq": lambda api_key, base_url: GroqAdapter(api_key=api_key),
    "ollama_cloud": lambda api_key, base_url: OllamaAdapter(
        base_url=base_url or settings.OLLAMA_CLOUD_BASE_URL, api_key=api_key
    ),
    "ollama_local": lambda api_key, base_url: OllamaAdapter(
        base_url=base_url or settings.OLLAMA_LOCAL_BASE_URL, api_key=api_key
    ),
}


def create_adapter(provider: str, api_key: str, base_url: str | None = None) -> LLMPort:
    """Return the right LLM adapter for the given provider, API key, and optional base URL."""
    factory = _ADAPTER_FACTORIES.get(provider)
    if factory is None:
        raise ValueError(
            f"Unsupported LLM provider: '{provider}'. "
            f"Supported: {sorted(_ADAPTER_FACTORIES)}"
        )
    return factory(api_key, base_url)
```

- [ ] **Run tests — expect all green**

```
uv run --directory backend python -m pytest tests/services/llm/test_factory.py -v
```

- [ ] **Run the full LLM test suite to check nothing regressed**

```
uv run --directory backend python -m pytest tests/services/llm/ -v
```

- [ ] **Commit**

```
git add backend/app/services/llm/factory.py backend/tests/services/llm/test_factory.py
git commit -m "feat(llm): factory — add Groq, add base_url parameter"
```

---

## Task 6: ProviderKey base_url column + credential resolver

**Files:**
- Modify: `backend/app/models/provider_key.py`
- Create: `backend/alembic/versions/<rev>_add_provider_key_base_url.py` (generated)
- Create: `backend/app/services/llm/credentials.py`
- Create: `backend/tests/services/llm/test_credentials.py`

- [ ] **Write the failing tests**

```python
# backend/tests/services/llm/test_credentials.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.services.llm.credentials import ProviderCredentials


USER_ID = uuid4()
PROJECT_ID = uuid4()


def _make_db():
    return MagicMock()


def _make_repo(key_text: str | None, base_url: str | None = None):
    repo = MagicMock()
    if key_text is not None:
        from app.utils.encryption import encrypt
        record = MagicMock()
        record.api_key_encrypted = encrypt(key_text)
        record.base_url = base_url
        repo.get_for_provider = AsyncMock(return_value=record)
    else:
        repo.get_for_provider = AsyncMock(return_value=None)
    return repo


@pytest.mark.asyncio
async def test_ollama_local_returns_dummy_key_without_db():
    from app.services.llm.credentials import resolve_provider_credentials
    repo = MagicMock()
    repo.get_for_provider = AsyncMock()
    with pytest.MonkeyPatch().context() as mp:
        # Patch ProviderKeyRepository to return our mock
        import app.services.llm.credentials as creds_mod
        mp.setattr(creds_mod, "ProviderKeyRepository", lambda db: repo)
        result = await resolve_provider_credentials("ollama_local", USER_ID, PROJECT_ID, _make_db())
    repo.get_for_provider.assert_not_called()
    assert result.api_key == "ollama"
    assert result.base_url is None


@pytest.mark.asyncio
async def test_returns_decrypted_key_and_base_url():
    from app.services.llm.credentials import resolve_provider_credentials
    repo = _make_repo("sk-real-key", base_url="https://my-vllm.example.com/v1")
    import app.services.llm.credentials as creds_mod
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(creds_mod, "ProviderKeyRepository", lambda db: repo)
        result = await resolve_provider_credentials("openai", USER_ID, PROJECT_ID, _make_db())
    assert result.api_key == "sk-real-key"
    assert result.base_url == "https://my-vllm.example.com/v1"


@pytest.mark.asyncio
async def test_returns_none_base_url_when_not_set():
    from app.services.llm.credentials import resolve_provider_credentials
    repo = _make_repo("sk-real-key", base_url=None)
    import app.services.llm.credentials as creds_mod
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(creds_mod, "ProviderKeyRepository", lambda db: repo)
        result = await resolve_provider_credentials("openai", USER_ID, PROJECT_ID, _make_db())
    assert result.base_url is None


@pytest.mark.asyncio
async def test_raises_validation_error_when_no_key():
    from app.services.llm.credentials import resolve_provider_credentials
    from app.services.exceptions import ValidationError
    repo = _make_repo(None)
    import app.services.llm.credentials as creds_mod
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(creds_mod, "ProviderKeyRepository", lambda db: repo)
        with pytest.raises(ValidationError, match="No API key configured for provider 'anthropic'"):
            await resolve_provider_credentials("anthropic", USER_ID, PROJECT_ID, _make_db())
```

- [ ] **Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/services/llm/test_credentials.py -v
```

- [ ] **Add `base_url` column to `ProviderKey` model**

In `backend/app/models/provider_key.py`, add after the `api_key_encrypted` field:

```python
    # Optional base URL for self-hosted / custom inference endpoints
    base_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )
```

- [ ] **Generate Alembic migration**

```
uv run --directory backend alembic revision --autogenerate -m "add_provider_key_base_url"
```

Open the generated file in `backend/alembic/versions/`. Verify it contains exactly:

```python
def upgrade() -> None:
    op.add_column('provider_keys', sa.Column('base_url', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('provider_keys', 'base_url')
```

Remove any unrelated changes if present (autogenerate sometimes picks up stale diffs).

- [ ] **Create `credentials.py`**

```python
# backend/app/services/llm/credentials.py
"""LLM-specific credential resolution.

Single entry point for resolving a provider's API key and optional base URL
before constructing an adapter.  All LLM-calling features use this instead of
doing their own ProviderKeyRepository lookups.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.provider_key_repository import ProviderKeyRepository
from app.services.exceptions import ValidationError
from app.utils.encryption import decrypt

# Providers that require no user-supplied key (local instances).
_NO_KEY_PROVIDERS: frozenset[str] = frozenset({"ollama_local"})


@dataclass
class ProviderCredentials:
    """Resolved credentials for a single LLM provider call."""
    api_key: str
    base_url: str | None  # None = use the adapter's built-in default endpoint


async def resolve_provider_credentials(
    provider: str,
    user_id: UUID,
    project_id: UUID,
    db: AsyncSession,
) -> ProviderCredentials:
    """Return decrypted credentials for *provider*.

    - ``ollama_local``: returns a dummy key immediately, no DB call.
    - All other providers: fetch from ``ProviderKeyRepository``.
      Raises ``ValidationError`` if no key is found.
    """
    if provider in _NO_KEY_PROVIDERS:
        return ProviderCredentials(api_key="ollama", base_url=None)

    repo = ProviderKeyRepository(db)
    key_record = await repo.get_for_provider(user_id, provider, project_id)
    if not key_record:
        raise ValidationError(f"No API key configured for provider '{provider}'")

    return ProviderCredentials(
        api_key=decrypt(key_record.api_key_encrypted),
        base_url=key_record.base_url,
    )
```

- [ ] **Run tests — expect all green**

```
uv run --directory backend python -m pytest tests/services/llm/test_credentials.py -v
```

- [ ] **Commit**

```
git add backend/app/models/provider_key.py backend/app/services/llm/credentials.py backend/tests/services/llm/test_credentials.py
git add backend/alembic/versions/
git commit -m "feat(llm): ProviderCredentials resolver + ProviderKey.base_url migration"
```

---

## Task 7: Rewrite LLMExtractor — delete OpenAICompatMixin

**Files:**
- Modify: `backend/app/adapters/extraction/llm.py`
- Delete: `backend/app/adapters/extraction/openai_compat_mixin.py`
- Modify: `backend/tests/adapters/extraction/test_llm_extractor.py`

- [ ] **Write new/replacement tests (these replace the old `TestLLMExtractorExtract` class)**

Replace the full contents of `backend/tests/adapters/extraction/test_llm_extractor.py`:

```python
# backend/tests/adapters/extraction/test_llm_extractor.py
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
```

- [ ] **Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/adapters/extraction/test_llm_extractor.py -v
```

- [ ] **Rewrite `adapters/extraction/llm.py`**

```python
# backend/app/adapters/extraction/llm.py
"""Generic LLM extraction adapter.

Works with any provider supported by create_adapter(). Reads per-run LLM
config from the 'llm_config' key in the config dict (a serialized PromptConfig).
Caller is responsible for pre-resolving credentials (provider, api_key, base_url)
and placing them in the config dict before calling extract().
"""
import json
import time
from typing import Any
from uuid import UUID

from app.adapters.extraction.llm_context import (
    augment_schema_with_sources,
    build_extraction_context,
    strip_source_fields,
)
from app.cdm.models import ParsedDocument
from app.ports.data_extraction import DataExtractor, ExtractionError, ExtractionOutput
from app.schemas.prompt_config import PromptConfig
from app.services.llm.factory import create_adapter
from app.services.llm.prompt_config import resolve_llm_config
from app.services.llm.types import LLMConfig, LLMConnectionError

DEFAULT_EXTRACTION_SYSTEM_PROMPT = (
    "You are a structured data extraction assistant. Extract information from the provided "
    "document according to the given JSON schema. Be precise and faithful to the source text. "
    "Only extract values that are explicitly present in the document."
)

DEFAULT_USER_PROMPT_TEMPLATE = """\
Extract structured data from the following document according to this JSON schema:

<schema>
{schema_json}
</schema>

For each field you extract, include a corresponding `{{field_name}}__source` object \
with `page_index` (integer, required) and `block_id` (string, if available) indicating \
where in the document you found the value.

<document>
{document_context}
</document>

Return a single JSON object that conforms to the schema (including __source fields)."""


class LLMExtractor(DataExtractor):
    """Structured extraction via any LLM provider supported by create_adapter()."""

    extractor_type = "llm"
    display_name = "LLM"

    def __init__(
        self,
        default_provider: str = "ollama_local",
        default_api_key: str = "ollama",
    ) -> None:
        self._default_provider = default_provider
        self._default_api_key = default_api_key

    def _build_messages(
        self,
        aug_schema: dict[str, Any],
        context: str,
        cfg: dict[str, Any],
    ) -> list[dict[str, str]]:
        system_prompt = cfg.get("system_prompt") or DEFAULT_EXTRACTION_SYSTEM_PROMPT
        schema_json = json.dumps(aug_schema, indent=2)
        template = cfg.get("user_prompt_template") or DEFAULT_USER_PROMPT_TEMPLATE
        user_content = template.format(schema_json=schema_json, document_context=context)
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    async def extract(
        self,
        parsed_document: ParsedDocument,
        schema: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> ExtractionOutput:
        cfg = dict(config or {})

        # Resolve provider and credentials from cfg (pre-resolved by caller)
        provider = cfg.get("provider") or self._default_provider
        api_key = cfg.get("api_key") or self._default_api_key
        base_url: str | None = cfg.get("base_url")

        # Resolve LLM config from PromptConfig stored in config["llm_config"]
        prompt_config: PromptConfig | None = None
        if cfg.get("llm_config"):
            prompt_config = PromptConfig.model_validate(cfg["llm_config"])
        resolved = resolve_llm_config(
            prompt_config,
            default_provider=provider,
            default_model="llama3.2:8b",
        )
        if prompt_config and prompt_config.system_prompt:
            cfg["system_prompt"] = prompt_config.system_prompt

        structured_output_mode = cfg.get("structured_output_mode", "json_schema")
        context = build_extraction_context(parsed_document, cfg.get("inject_block_ids", False))
        aug_schema = augment_schema_with_sources(schema)
        messages = self._build_messages(aug_schema, context, cfg)

        llm_config = LLMConfig(
            provider=resolved.provider,
            model=resolved.model,
            temperature=resolved.temperature,
            max_tokens=resolved.max_tokens,
            structured_output_mode=structured_output_mode,
            structured_output_schema=aug_schema if structured_output_mode == "json_schema" else None,
        )

        adapter = create_adapter(provider, api_key, base_url)

        t0 = time.monotonic()
        try:
            result = await adapter.complete(messages, llm_config)
        except LLMConnectionError as exc:
            raise ExtractionError(f"Cannot connect to LLM provider '{provider}': {exc}") from exc
        latency_ms = int((time.monotonic() - t0) * 1000)

        try:
            raw = json.loads(result.content)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ExtractionError(
                f"Model returned non-JSON response: {result.content[:200]!r}"
            ) from exc

        structured_data, citations = strip_source_fields(raw, schema)

        return ExtractionOutput(
            structured_data=structured_data,
            source_parse_run_id=UUID(parsed_document.parse_run_id),
            citations=citations,
            provider_response_raw=raw,
            extraction_metadata={
                "model": llm_config.model,
                "provider": llm_config.provider,
                "latency_ms": latency_ms,
                "usage": {
                    "prompt_tokens": result.usage.prompt_tokens,
                    "completion_tokens": result.usage.completion_tokens,
                    "total_tokens": result.usage.total_tokens,
                } if result.usage else None,
            },
        )
```

- [ ] **Delete the mixin**

```
git rm backend/app/adapters/extraction/openai_compat_mixin.py
```

- [ ] **Run tests — expect all green**

```
uv run --directory backend python -m pytest tests/adapters/extraction/test_llm_extractor.py -v
```

- [ ] **Commit**

```
git add backend/app/adapters/extraction/llm.py backend/tests/adapters/extraction/test_llm_extractor.py
git commit -m "feat(extraction): rewrite LLMExtractor on LLMPort, delete OpenAICompatMixin"
```

---

## Task 8: LLMClassifier takes adapter directly, classifier_factory uses create_adapter

**Files:**
- Modify: `backend/app/services/classification/llm_classifier.py`
- Modify: `backend/app/services/classification/classifier_factory.py`
- Modify: `backend/tests/services/classification/test_llm_classifier.py`
- Modify: `backend/tests/services/classification/test_classifier_factory.py`

- [ ] **Update classifier tests**

Replace the full contents of `backend/tests/services/classification/test_llm_classifier.py`:

```python
# backend/tests/services/classification/test_llm_classifier.py
from unittest.mock import AsyncMock, MagicMock
import pytest
from app.cdm.models import Block, BlockRole, Page, ParsedDocument
from app.services.llm.types import CompletionResult, TokenUsage


def _make_doc() -> ParsedDocument:
    pages = [Page(index=i, block_ids=[f"b{i}"]) for i in range(3)]
    blocks = [
        Block(id=f"b{i}", role=BlockRole.PARAGRAPH, native_type="p",
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
    adapter = _make_adapter(_RESPONSE_ALL_NONE)
    classifier = LLMClassifier(
        adapter=adapter, provider="ollama_local", model="qwen2.5:7b",
        batch_size=10, batch_overlap=3, system_prompt="Custom prompt",
    )
    await classifier.classify(_make_doc(), ["x"])
    messages = adapter.complete.call_args[0][0]
    assert messages[0]["content"] == "Custom prompt"


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
```

- [ ] **Update factory tests**

Replace the full contents of `backend/tests/services/classification/test_classifier_factory.py`:

```python
# backend/tests/services/classification/test_classifier_factory.py
from unittest.mock import patch
import pytest
from app.services.classification.classifier_factory import (
    _resolve_byok_provider,
    build_classifier,
)
from app.services.classification.llm_classifier import LLMClassifier
from app.services.classification.llamaindex_split_classifier import LlamaIndexSplitClassifier


def _patch_settings():
    p = patch("app.services.classification.classifier_factory.settings")
    m = p.start()
    m.CLASSIFIER_LLM_PROVIDER = "ollama_local"
    m.CLASSIFIER_LLM_MODEL = "qwen2.5:7b"
    m.OLLAMA_LOCAL_BASE_URL = "http://localhost:11434/v1"
    m.OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"
    return p


def test_resolve_byok_groq():
    assert _resolve_byok_provider("llm", {"provider": "groq"}) == "groq"


def test_resolve_byok_ollama_cloud():
    assert _resolve_byok_provider("llm", {"provider": "ollama_cloud"}) == "ollama_cloud"


def test_resolve_byok_anthropic():
    assert _resolve_byok_provider("llm", {"provider": "anthropic"}) == "anthropic"


def test_resolve_byok_openai():
    assert _resolve_byok_provider("llm", {"provider": "openai"}) == "openai"


def test_resolve_byok_ollama_local_returns_none():
    assert _resolve_byok_provider("llm", {"provider": "ollama_local"}) is None


def test_resolve_byok_non_llm_returns_none():
    assert _resolve_byok_provider("llamaindex_split", {}) is None


def test_build_classifier_llm_returns_llm_classifier_with_adapter():
    p = _patch_settings()
    classifier = build_classifier(
        "llm",
        {"provider": "ollama_local", "model": "qwen2.5:7b",
         "batch_size": 10, "batch_overlap": 3},
        api_key=None,
    )
    p.stop()
    assert isinstance(classifier, LLMClassifier)
    assert classifier.provider == "ollama_local"
    assert classifier.model == "qwen2.5:7b"
    assert classifier.batch_size == 10
    # adapter is a real OllamaAdapter instance (not a registry)
    assert classifier.adapter is not None


def test_build_classifier_llm_threads_llm_config():
    p = _patch_settings()
    classifier = build_classifier(
        "llm",
        {
            "provider": "ollama_local",
            "model": "qwen2.5:7b",
            "llm_config": {"system_prompt": "Custom", "temperature": 0.5, "max_tokens": 2048},
        },
        api_key=None,
    )
    p.stop()
    assert isinstance(classifier, LLMClassifier)
    assert classifier.system_prompt == "Custom"
    assert classifier.temperature == 0.5
    assert classifier.max_tokens == 2048


def test_build_classifier_raises_for_unknown_provider():
    p = _patch_settings()
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        build_classifier("llm", {"provider": "nonexistent_provider"}, api_key="key")
    p.stop()


def test_build_classifier_llamaindex_split():
    classifier = build_classifier("llamaindex_split", {"chunk_size": 512}, api_key=None)
    assert isinstance(classifier, LlamaIndexSplitClassifier)


def test_build_classifier_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown classifier type"):
        build_classifier("nonexistent", {}, api_key=None)
```

- [ ] **Run tests to confirm they fail**

```
uv run --directory backend python -m pytest tests/services/classification/ -v
```

- [ ] **Implement: update `llm_classifier.py`**

```python
# backend/app/services/classification/llm_classifier.py
from __future__ import annotations
import logging

from pydantic import BaseModel

from app.cdm.models import ParsedDocument
from app.services.classification.assembler import (
    BatchPageResult, assemble_regions, resolve_page_statuses,
)
from app.services.classification.port import ClassificationPort, ClassificationResult
from app.services.classification.serializer import build_batches, serialize_pages
from app.services.llm.port import LLMPort
from app.services.llm.types import LLMConfig

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = """\
You are a document classifier. Analyze the document pages provided and determine which labels apply to each page.

For each label, classify each page as:
- "start": this page begins a section matching this label
- "continue": this page continues a section from a previous page
- "none": this page does not contain this label

Return ONLY valid JSON in this exact format:
{
  "pages": [
    {"page": <page_index>, "labels": {"<label>": "start"|"continue"|"none", ...}},
    ...
  ]
}

Include every page index present in the document content.\
"""


class _PageResult(BaseModel):
    page: int
    labels: dict[str, str]


class _BatchLLMResponse(BaseModel):
    pages: list[_PageResult]


class LLMClassifier:
    def __init__(
        self,
        adapter: LLMPort,
        provider: str,
        model: str,
        batch_size: int = 10,
        batch_overlap: int = 3,
        system_prompt: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> None:
        self.adapter = adapter
        self.provider = provider
        self.model = model
        self.batch_size = batch_size
        self.batch_overlap = batch_overlap
        self.system_prompt = system_prompt or _DEFAULT_SYSTEM_PROMPT
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def classify(
        self, doc: ParsedDocument, labels: list[str]
    ) -> ClassificationResult:
        config = LLMConfig(
            provider=self.provider,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            structured_output_mode="json_mode",
        )
        labels_str = ", ".join(labels)
        batches = build_batches(doc.page_count, self.batch_size, self.batch_overlap)
        all_batch_results: list[list[BatchPageResult]] = []
        total_input = 0
        total_output = 0

        for batch_start, batch_end in batches:
            serialized = serialize_pages(doc, batch_start, batch_end)
            messages = [
                {"role": "system", "content": self.system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Labels to identify: {labels_str}\n\n"
                        f"Document pages:\n{serialized}"
                    ),
                },
            ]
            result = await self.adapter.complete(messages, config)
            total_input += result.usage.prompt_tokens
            total_output += result.usage.completion_tokens

            parsed = _BatchLLMResponse.model_validate_json(result.content)
            batch_page_results = [
                BatchPageResult(
                    page=p.page,
                    label_statuses=p.labels,
                    batch_start=batch_start,
                    batch_end=batch_end,
                )
                for p in parsed.pages
            ]
            all_batch_results.append(batch_page_results)

        resolved = resolve_page_statuses(all_batch_results)
        regions = assemble_regions(resolved, labels, doc)
        return ClassificationResult(
            regions=regions, input_tokens=total_input, output_tokens=total_output,
        )
```

- [ ] **Implement: rewrite `classifier_factory.py`**

```python
# backend/app/services/classification/classifier_factory.py
from app.config import settings
from app.services.classification.llm_classifier import LLMClassifier
from app.services.classification.llamaindex_split_classifier import LlamaIndexSplitClassifier
from app.services.classification.port import ClassificationPort
from app.services.llm.factory import create_adapter

# Providers that require a user-supplied API key for classification.
# ollama_local is excluded — it uses a dummy key.
_LLM_BYOK_PROVIDERS = {"groq", "ollama_cloud", "anthropic", "openai"}


def _resolve_byok_provider(classifier_type: str, classifier_config: dict) -> str | None:
    """Return the BYOK provider ID if an API key is required, else None."""
    if classifier_type == "llm":
        provider = classifier_config.get("provider", "")
        return provider if provider in _LLM_BYOK_PROVIDERS else None
    return None


def build_classifier(
    classifier_type: str,
    classifier_config: dict,
    api_key: str | None,
    base_url: str | None = None,
) -> ClassificationPort:
    if classifier_type == "llm":
        provider = classifier_config.get("provider", settings.CLASSIFIER_LLM_PROVIDER)
        model = classifier_config.get("model", settings.CLASSIFIER_LLM_MODEL)
        batch_size = int(classifier_config.get("batch_size", 10))
        batch_overlap = int(classifier_config.get("batch_overlap", 3))
        llm_cfg = classifier_config.get("llm_config") or {}
        system_prompt: str | None = llm_cfg.get("system_prompt")
        temperature: float = float(llm_cfg.get("temperature", 0.0))
        max_tokens: int = int(llm_cfg.get("max_tokens", 4096))

        effective_key = api_key if api_key is not None else "ollama"
        # ValueError from create_adapter propagates immediately — no silent swallow
        adapter = create_adapter(provider, effective_key, base_url)

        return LLMClassifier(
            adapter=adapter,
            provider=provider,
            model=model,
            batch_size=batch_size,
            batch_overlap=batch_overlap,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif classifier_type == "llamaindex_split":
        return LlamaIndexSplitClassifier(classifier_config)
    else:
        raise ValueError(
            f"Unknown classifier type: {classifier_type!r}. "
            "Supported: 'llm', 'llamaindex_split'"
        )
```

- [ ] **Run tests — expect all green**

```
uv run --directory backend python -m pytest tests/services/classification/ -v
```

- [ ] **Commit**

```
git add backend/app/services/classification/llm_classifier.py backend/app/services/classification/classifier_factory.py backend/tests/services/classification/test_llm_classifier.py backend/tests/services/classification/test_classifier_factory.py
git commit -m "feat(classification): LLMClassifier takes adapter directly, factory uses create_adapter"
```

---

## Task 9: Fix `eval_runs.py` — remove local whitelist, use shared resolver

**Files:**
- Modify: `backend/app/routers/eval_runs.py`

- [ ] **Implement the changes**

At the top of `eval_runs.py`, remove:
```python
from app.services.llm.openai_adapter import OpenAIAdapter
from app.services.llm.anthropic_adapter import AnthropicAdapter
```

Add:
```python
from app.services.llm.credentials import resolve_provider_credentials
from app.services.llm.factory import create_adapter
```

Delete the entire `_resolve_adapter` function (lines 79–93).

Replace the adapter resolution in `execute_eval_run_background` — find this block:

```python
    if mode == "retrieval_and_answer":
        if generation_provider:
            generation_adapter = await _resolve_adapter(
                generation_provider, user_id, project_id, db
            )
        if judge_provider:
            judge_adapter = await _resolve_adapter(
                judge_provider, user_id, project_id, db
            )
```

Replace with:

```python
    if mode == "retrieval_and_answer":
        if generation_provider:
            creds = await resolve_provider_credentials(
                generation_provider, user_id, project_id, db
            )
            generation_adapter = create_adapter(
                generation_provider, creds.api_key, creds.base_url
            )
        if judge_provider:
            creds = await resolve_provider_credentials(
                judge_provider, user_id, project_id, db
            )
            judge_adapter = create_adapter(
                judge_provider, creds.api_key, creds.base_url
            )
```

- [ ] **Run existing eval router tests**

```
uv run --directory backend python -m pytest tests/routers/ -k "eval" -v
```

- [ ] **Verify Groq is now accepted by starting the app and checking the OpenAPI schema, OR check via import**

```
uv run --directory backend python -c "
from app.routers.eval_runs import execute_eval_run_background
from app.services.llm.factory import create_adapter
# groq must now be reachable — factory has it
adapter = create_adapter('groq', 'test-key')
print('groq adapter OK:', type(adapter).__name__)
"
```

Expected output: `groq adapter OK: GroqAdapter`

- [ ] **Commit**

```
git add backend/app/routers/eval_runs.py
git commit -m "fix(eval): remove _resolve_adapter whitelist, use resolve_provider_credentials + create_adapter"
```

---

## Task 10: Fix `golden_set_generation_service.py`

**Files:**
- Modify: `backend/app/services/golden_set_generation_service.py`

- [ ] **Implement the three targeted fixes**

**Fix 1** — change the import at the top. Remove:
```python
from app.services.llm.openai_adapter import OpenAIAdapter
```
Add:
```python
from app.services.llm.factory import create_adapter
from app.services.llm.port import LLMPort
```

**Fix 2** — in `execute_generation`, replace the adapter construction (line 113):
```python
            adapter = OpenAIAdapter(api_key=api_key)
```
With:
```python
            adapter = create_adapter(llm_provider, api_key, key_record.base_url)
```

**Fix 3** — in `_process_window`, fix the type hint and the hardcoded provider:

Change the signature from:
```python
    async def _process_window(
        self,
        gs_id: UUID,
        window: dict,
        adapter: OpenAIAdapter,
        llm_model: str,
        temperature: float,
        question_types: list[str],
    ) -> None:
```
To:
```python
    async def _process_window(
        self,
        gs_id: UUID,
        window: dict,
        adapter: LLMPort,
        llm_model: str,
        temperature: float,
        question_types: list[str],
        llm_provider: str = "openai",
    ) -> None:
```

Change the `LLMConfig` construction inside `_process_window` from:
```python
        config = LLMConfig(
            provider="openai",
            model=llm_model,
            temperature=temperature,
            max_tokens=4096,
            json_mode=True,
        )
```
To:
```python
        config = LLMConfig(
            provider=llm_provider,
            model=llm_model,
            temperature=temperature,
            max_tokens=4096,
            structured_output_mode="json_mode",
        )
```

Update the call to `_process_window` in `execute_generation` to pass `llm_provider`:
```python
                    await self._process_window(
                        gs_id=gs_id,
                        window=window,
                        adapter=adapter,
                        llm_model=llm_model,
                        temperature=temperature,
                        question_types=question_types,
                        llm_provider=llm_provider,
                    )
```

- [ ] **Verify by running the golden set tests**

```
uv run --directory backend python -m pytest tests/ -k "golden_set" -v
```

- [ ] **Quick smoke-check: confirm Anthropic key is now used with the right adapter**

```
uv run --directory backend python -c "
from app.services.llm.factory import create_adapter
from app.services.llm.anthropic_adapter import AnthropicAdapter
adapter = create_adapter('anthropic', 'sk-ant-test')
print('adapter type:', type(adapter).__name__)
assert isinstance(adapter, AnthropicAdapter)
print('OK — anthropic key now routes to AnthropicAdapter')
"
```

- [ ] **Commit**

```
git add backend/app/services/golden_set_generation_service.py
git commit -m "fix(golden-set): use create_adapter for provider routing, fix hardcoded provider=openai"
```

---

## Task 11: Fix `answer_service.py` — streaming usage

**Files:**
- Modify: `backend/app/services/answer_service.py`

- [ ] **Implement the changes**

In `stream_answer`, find the streaming block:

```python
            try:
                async for token in adapter.stream_completion(messages, llm_config):
                    token_count += 1
                    yield _sse_event("token", {"content": token})
            finally:
```

Replace with:

```python
            stream = await adapter.stream_completion(messages, llm_config)
            try:
                async for token in stream:
                    token_count += 1
                    yield _sse_event("token", {"content": token})
            finally:
```

In the `finally` block, find the span metrics section and update the token counts to use `stream.usage` where available:

```python
            finally:
                if llm_span is not None and llm_span_ctx is not None:
                    usage = stream.usage
                    llm_span.metrics.completion_tokens = (
                        usage.completion_tokens if usage else token_count
                    )
                    llm_span.metrics.total_tokens = (
                        usage.total_tokens if usage else token_count
                    )
                    llm_span.metrics.model = llm_config.model
                    llm_span.metrics.provider = llm_config.provider
                    llm_span.output = {
                        "completion_tokens": usage.completion_tokens if usage else token_count
                    }
                    llm_span_ctx.__exit__(None, None, None)
```

Find the `done` SSE event and fix the usage payload:

```python
            usage = stream.usage
            yield _sse_event("done", {
                "usage": {
                    "promptTokens": usage.prompt_tokens if usage else None,
                    "completionTokens": usage.completion_tokens if usage else None,
                    "totalTokens": usage.total_tokens if usage else None,
                },
                "latencyMs": round(latency_ms, 1),
            })
```

- [ ] **Run existing answer service tests**

```
uv run --directory backend python -m pytest tests/ -k "answer" -v
```

- [ ] **Commit**

```
git add backend/app/services/answer_service.py
git commit -m "fix(answer): consume StreamResponse.usage for accurate done event token counts"
```

---

## Task 12: Cleanup — delete dead code, full suite green

**Files:**
- Delete: `backend/app/dependencies/llm.py`
- Verify: no remaining imports of `LLMRegistry` or `get_llm_registry`

- [ ] **Check for remaining references**

```
uv run --directory backend python -c "
import subprocess, sys
result = subprocess.run(
    ['grep', '-r', 'get_llm_registry\|LLMRegistry\|openai_compat_mixin', 'app/', '--include=*.py'],
    capture_output=True, text=True
)
if result.stdout.strip():
    print('REMAINING REFERENCES:', result.stdout)
    sys.exit(1)
else:
    print('No stale references — safe to delete')
"
```

If any references are found, remove them before proceeding.

- [ ] **Delete `dependencies/llm.py`**

```
git rm backend/app/dependencies/llm.py
```

- [ ] **Run the complete test suite**

```
uv run --directory backend python -m pytest -o "addopts=" -v 2>&1 | tail -30
```

All tests must pass. If any fail, fix them before the final commit — they are likely caused by stale imports or tests that still reference `llm_registry=` kwarg.

- [ ] **Final commit**

```
git add -A
git commit -m "chore(llm): delete dependencies/llm.py and LLMRegistry — superseded by create_adapter"
```

---

## Verification checklist

After all tasks are complete, verify the end state against the spec:

| Requirement | Verify |
|---|---|
| `create_adapter("groq", ...)` works | Task 5 test |
| Extraction with `provider="anthropic"` routes to `AnthropicAdapter` | Task 7 test |
| `max_tokens` is forwarded during extraction | Task 7 test |
| Ollama `json_schema` → no `response_format` sent | Task 4 test |
| `done` event has real token counts from OpenAI | Task 11 |
| Eval runs accept Groq provider | Task 9 |
| Golden-set generation uses correct adapter per provider | Task 10 |
| `LLMClassifier` no longer imports `LLMRegistry` | Task 8 |
| Self-hosted `base_url` flows from DB → adapter | Task 6 test |
| New provider needs 1 adapter file + 1 factory line | `factory.py` structure |
