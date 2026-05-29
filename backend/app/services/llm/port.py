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
