"""Factory for constructing per-request LLM adapters from a provider name + API key."""
from typing import Callable

from app.config import settings
from app.services.llm.port import LLMPort
from app.services.llm.openai_adapter import OpenAIAdapter
from app.services.llm.anthropic_adapter import AnthropicAdapter
from app.services.llm.ollama_adapter import OllamaAdapter

# Each value is a callable (api_key: str) -> LLMPort.
# Use a lambda when the adapter needs extra constructor args (e.g. base_url).
# To add a new provider: one line here, nothing else changes.
_ADAPTER_FACTORIES: dict[str, Callable[[str], LLMPort]] = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "ollama_cloud": lambda api_key: OllamaAdapter(
        base_url=settings.OLLAMA_CLOUD_BASE_URL, api_key=api_key
    ),
    "ollama_local": lambda api_key: OllamaAdapter(
        base_url=settings.OLLAMA_LOCAL_BASE_URL, api_key=api_key
    ),
}


def create_adapter(provider: str, api_key: str) -> LLMPort:
    """Return the right LLM adapter for the given provider and API key."""
    factory = _ADAPTER_FACTORIES.get(provider)
    if factory is None:
        raise ValueError(
            f"Unsupported LLM provider: '{provider}'. "
            f"Supported: {sorted(_ADAPTER_FACTORIES)}"
        )
    return factory(api_key)
