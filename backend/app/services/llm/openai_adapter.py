"""OpenAI LLM adapter."""
import time
import logging
from typing import AsyncGenerator

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
