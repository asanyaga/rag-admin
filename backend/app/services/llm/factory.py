"""Factory for constructing per-request LLM adapters from a provider name + API key."""
from typing import Callable

from app.config import settings
from app.services.llm.port import LLMPort
from app.services.llm.openai_adapter import OpenAIAdapter
from app.services.llm.anthropic_adapter import AnthropicAdapter
from app.services.llm.ollama_adapter import OllamaAdapter
from app.services.llm.groq_adapter import GroqAdapter

# Each value is callable (api_key: str, base_url: str | None) -> LLMPort.
# To add a new provider: one line here, nothing else changes.
_ADAPTER_FACTORIES: dict[str, Callable[[str, str | None], LLMPort]] = {
    "openai": lambda api_key, base_url: OpenAIAdapter(api_key=api_key, base_url=base_url),
    "anthropic": lambda api_key, base_url: AnthropicAdapter(api_key=api_key),
    "groq": lambda api_key, base_url: GroqAdapter(api_key=api_key),
    "ollama_cloud": lambda api_key, base_url: OllamaAdapter(
        base_url=base_url or settings.OLLAMA_CLOUD_BASE_URL, api_key=api_key
    ),
    "ollama_local": lambda api_key, base_url: OllamaAdapter(
        base_url=base_url or settings.OLLAMA_LOCAL_BASE_URL, api_key=api_key
    ),
}


def create_adapter(provider: str, api_key: str, base_url: str | None = None) -> LLMPort:
    """Return the right LLM adapter for the given provider, API key, and optional base URL."""
    factory = _ADAPTER_FACTORIES.get(provider)
    if factory is None:
        raise ValueError(
            f"Unsupported LLM provider: '{provider}'. "
            f"Supported: {sorted(_ADAPTER_FACTORIES)}"
        )
    return factory(api_key, base_url)
