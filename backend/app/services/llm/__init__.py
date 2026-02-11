"""LLM abstraction layer for answer generation.

Provides a thin adapter pattern over LLM providers with a simple protocol
that can be replaced by a mature framework later.
"""

from app.services.llm.types import LLMConfig, TokenUsage, CompletionResult
from app.services.llm.port import LLMPort
from app.services.llm.registry import LLMRegistry
from app.services.llm.openai_adapter import OpenAIAdapter
from app.services.llm.prompt import build_rag_prompt

__all__ = [
    "LLMConfig",
    "TokenUsage",
    "CompletionResult",
    "LLMPort",
    "LLMRegistry",
    "OpenAIAdapter",
    "build_rag_prompt",
]
