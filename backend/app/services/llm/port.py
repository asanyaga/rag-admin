"""Protocol definition for LLM providers."""

from typing import Protocol, AsyncIterator

from app.services.llm.types import LLMConfig, CompletionResult


class LLMPort(Protocol):
    """Interface that all LLM adapters must implement.

    Intentionally thin — no retry logic, rate limiting, or fallback chains.
    Those concerns belong in a mature framework adopted later.
    """

    async def stream_completion(
        self,
        messages: list[dict],
        config: LLMConfig,
    ) -> AsyncIterator[str]:
        """Yield content tokens as they arrive from the provider."""
        ...

    async def complete(
        self,
        messages: list[dict],
        config: LLMConfig,
    ) -> CompletionResult:
        """Non-streaming completion with full result metadata."""
        ...
