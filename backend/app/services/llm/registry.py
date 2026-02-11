"""LLM provider registry."""

from app.services.llm.port import LLMPort


class LLMRegistry:
    """Simple registry mapping provider names to adapter instances.

    No magic — easy to replace with a framework later.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, LLMPort] = {}

    def register(self, provider: str, adapter: LLMPort) -> None:
        self._adapters[provider] = adapter

    def get(self, provider: str) -> LLMPort:
        if provider not in self._adapters:
            raise ValueError(f"LLM provider '{provider}' not configured")
        return self._adapters[provider]

    def has(self, provider: str) -> bool:
        return provider in self._adapters
