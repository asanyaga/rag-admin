"""Translates user-expressed PromptConfig into adapter-ready LLMConfig."""
from app.schemas.prompt_config import PromptConfig
from app.services.llm.types import LLMConfig


def resolve_llm_config(
    config: PromptConfig | None,
    default_provider: str = "openai",
    default_model: str = "gpt-4o",
    default_temperature: float = 0.0,
    default_max_tokens: int = 1024,
) -> LLMConfig:
    """Convert a PromptConfig into an adapter-ready LLMConfig.

    Falls back to supplied defaults for any field that is None.
    thinking/tools/top_p are stored on PromptConfig but not yet forwarded
    to adapters — add per-provider translation here when adapters support them.
    """
    if config is None:
        return LLMConfig(
            provider=default_provider,
            model=default_model,
            temperature=default_temperature,
            max_tokens=default_max_tokens,
        )

    return LLMConfig(
        provider=config.provider or default_provider,
        model=config.model or default_model,
        temperature=config.temperature if config.temperature is not None else default_temperature,
        max_tokens=config.max_tokens if config.max_tokens is not None else default_max_tokens,
        json_mode=bool(config.structured_output) or config.json_mode,
    )
