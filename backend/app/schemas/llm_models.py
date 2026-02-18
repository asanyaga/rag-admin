"""Chat model registry for generation and judge model selectors."""

from pydantic import BaseModel, ConfigDict, Field


# -------------------------------------------------------------------------
# Registry of available LLM chat models
# -------------------------------------------------------------------------

LLM_CHAT_MODELS: dict[str, list[dict]] = {
    "openai": [
        {"id": "gpt-4o", "label": "GPT-4o", "tier": "strong"},
        {"id": "gpt-4o-mini", "label": "GPT-4o Mini", "tier": "standard"},
    ],
    "anthropic": [
        {"id": "claude-sonnet-4-20250514", "label": "Claude Sonnet 4", "tier": "strong"},
        {"id": "claude-haiku-3-5-20241022", "label": "Claude 3.5 Haiku", "tier": "standard"},
    ],
}


# -------------------------------------------------------------------------
# Response schemas
# -------------------------------------------------------------------------

class LlmModelOption(BaseModel):
    """A single chat model option."""
    id: str
    label: str
    provider: str
    tier: str

    model_config = ConfigDict(populate_by_name=True)


class LlmModelsResponse(BaseModel):
    """Response for GET /settings/llm-models."""
    models: list[LlmModelOption]

    model_config = ConfigDict(populate_by_name=True)


def get_available_chat_models(configured_providers: set[str]) -> list[LlmModelOption]:
    """Return chat models filtered by which providers have API keys configured."""
    result = []
    for provider, models in LLM_CHAT_MODELS.items():
        if provider in configured_providers:
            for m in models:
                result.append(LlmModelOption(
                    id=m["id"],
                    label=m["label"],
                    provider=provider,
                    tier=m["tier"],
                ))
    return result
