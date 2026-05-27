"""Factory for constructing per-request LLM adapters from a provider name + API key."""
from app.services.llm.port import LLMPort
from app.services.llm.openai_adapter import OpenAIAdapter
from app.services.llm.anthropic_adapter import AnthropicAdapter

_ADAPTER_CLASSES: dict[str, type] = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
}


def create_adapter(provider: str, api_key: str) -> LLMPort:
    """Return the right LLM adapter for the given provider.

    To add a new provider: import its adapter class and add one entry to
    _ADAPTER_CLASSES above. No other files need to change.
    """
    cls = _ADAPTER_CLASSES.get(provider)
    if cls is None:
        raise ValueError(
            f"Unsupported LLM provider: '{provider}'. "
            f"Supported: {sorted(_ADAPTER_CLASSES)}"
        )
    return cls(api_key=api_key)
