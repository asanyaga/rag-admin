"""OpenAI LLM adapter."""

import time
import logging
from typing import AsyncIterator

from openai import AsyncOpenAI

from app.services.llm.types import LLMConfig, TokenUsage, CompletionResult

logger = logging.getLogger(__name__)


class OpenAIAdapter:
    """Thin wrapper around the OpenAI chat completions API."""

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def stream_completion(
        self,
        messages: list[dict],
        config: LLMConfig,
    ) -> AsyncIterator[str]:
        """Stream content tokens from OpenAI."""
        stream = await self.client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def complete(
        self,
        messages: list[dict],
        config: LLMConfig,
    ) -> CompletionResult:
        """Non-streaming completion with usage metadata."""
        start = time.monotonic()
        response = await self.client.chat.completions.create(
            model=config.model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )
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
            provider="openai",
        )
