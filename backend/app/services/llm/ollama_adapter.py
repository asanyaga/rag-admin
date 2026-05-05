# backend/app/services/llm/ollama_adapter.py
import time

from app.services.llm.openai_adapter import OpenAIAdapter
from app.services.llm.types import CompletionResult, LLMConfig, TokenUsage


class OllamaAdapter(OpenAIAdapter):
    """OpenAI-compatible adapter for Ollama (local or cloud).

    Local:  base_url="http://localhost:11434/v1", api_key="ollama" (dummy)
    Cloud:  base_url="https://ollama.com/v1",    api_key=<real key>

    Ollama does not reliably support response_format=json_object — many models
    return empty content when it is set. JSON output is requested via the system
    prompt instead.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        api_key: str = "ollama",
    ):
        super().__init__(api_key=api_key, base_url=base_url)

    async def complete(self, messages: list[dict], config: LLMConfig) -> CompletionResult:
        """Complete without response_format — Ollama ignores or mishandles it."""
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
            provider=self._provider_name,
        )
