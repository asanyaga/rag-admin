"""Anthropic LLM adapter."""

import re
import time
import logging
from typing import AsyncIterator

from anthropic import AsyncAnthropic, BadRequestError

from app.services.llm.types import LLMConfig, TokenUsage, CompletionResult

logger = logging.getLogger(__name__)

# Matches Anthropic's deprecation message: "`param_name` is deprecated for this model."
_DEPRECATED_PARAM_RE = re.compile(r"`(\w+)`\s+is deprecated")


def _strip_deprecated(kwargs: dict, error_msg: str) -> dict | None:
    """Return a copy of kwargs with the deprecated param removed.

    Parses the param name directly from Anthropic's error message so any
    future deprecations are handled automatically without code changes.
    Returns None if the error doesn't name a param we can safely remove.
    """
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

    async def stream_completion(
        self,
        messages: list[dict],
        config: LLMConfig,
    ) -> AsyncIterator[str]:
        """Stream content tokens from Anthropic.

        Retries once without the offending parameter if Anthropic returns a
        deprecation error (e.g. temperature not supported on newer models).
        """
        system_msg, user_messages = self._split_system(messages)
        kwargs: dict = dict(
            model=config.model,
            messages=user_messages,
            system=system_msg or "",
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
        async for token in self._stream(kwargs):
            yield token

    async def _stream(self, kwargs: dict) -> AsyncIterator[str]:
        try:
            async with self.client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except BadRequestError as e:
            retried = _strip_deprecated(kwargs, str(e))
            if retried is not None:
                logger.warning("Anthropic deprecated param stripped, retrying: %s", e)
                async with self.client.messages.stream(**retried) as stream:
                    async for text in stream.text_stream:
                        yield text
            else:
                raise

    async def complete(
        self,
        messages: list[dict],
        config: LLMConfig,
    ) -> CompletionResult:
        """Non-streaming completion with usage metadata."""
        start = time.monotonic()
        system_msg, user_messages = self._split_system(messages)

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

    @staticmethod
    def _split_system(messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Extract system message from the messages list.

        Anthropic API takes system as a separate parameter, not in messages.
        """
        system = None
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)
        return system, user_messages
