"""Anthropic LLM adapter."""

import time
import json
import logging
from typing import AsyncIterator

from anthropic import AsyncAnthropic

from app.services.llm.types import LLMConfig, TokenUsage, CompletionResult

logger = logging.getLogger(__name__)


class AnthropicAdapter:
    """Thin wrapper around the Anthropic messages API."""

    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)

    async def stream_completion(
        self,
        messages: list[dict],
        config: LLMConfig,
    ) -> AsyncIterator[str]:
        """Stream content tokens from Anthropic."""
        system_msg, user_messages = self._split_system(messages)

        async with self.client.messages.stream(
            model=config.model,
            messages=user_messages,
            system=system_msg or "",
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                yield text

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

        # For JSON mode, use the prefill trick: add an assistant message starting with {
        if config.json_mode:
            user_messages = list(user_messages)
            user_messages.append({"role": "assistant", "content": "{"})

            kwargs["messages"] = user_messages

        response = await self.client.messages.create(**kwargs)
        latency = (time.monotonic() - start) * 1000

        content = response.content[0].text if response.content else ""

        # If we used the prefill trick, prepend the { back
        if config.json_mode:
            content = "{" + content

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
