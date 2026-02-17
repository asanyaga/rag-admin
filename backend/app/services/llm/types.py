"""Data types for the LLM abstraction layer."""

from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuration for an LLM completion request."""

    provider: str  # "openai" for Phase 1
    model: str  # e.g. "gpt-4o"
    temperature: float = 0.0
    max_tokens: int = 1024
    json_mode: bool = False


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
