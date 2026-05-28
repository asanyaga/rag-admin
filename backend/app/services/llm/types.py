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
