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
