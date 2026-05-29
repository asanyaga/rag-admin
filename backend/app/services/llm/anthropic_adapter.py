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
