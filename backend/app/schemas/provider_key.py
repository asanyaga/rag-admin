"""Pydantic schemas for provider key management (BYOK)."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Supported embedding providers
SUPPORTED_PROVIDERS = [
    "openai", "voyage", "local", "anthropic",
    "groq", "llama_cloud", "landing_ai", "ollama_cloud",
]


class ProviderKeyCreate(BaseModel):
    """Schema for creating/updating a provider key."""
    provider: str = Field(..., min_length=1, max_length=50)
    api_key: str = Field(..., min_length=1, alias="apiKey")

    model_config = ConfigDict(populate_by_name=True)


class ProviderKeyResponse(BaseModel):
    """Schema for provider key API responses.

    Note: The actual API key is never returned, only a masked version.
    """
    id: UUID
    user_id: UUID = Field(..., alias="userId")
    project_id: UUID | None = Field(None, alias="projectId")
    provider: str
    api_key_masked: str = Field(..., alias="apiKeyMasked")  # e.g., "sk-****abcd"
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class ProviderKeyListResponse(BaseModel):
    """List of configured provider keys."""
    keys: list[ProviderKeyResponse]


class ProviderInfo(BaseModel):
    """Information about a supported provider."""
    name: str
    display_name: str = Field(..., alias="displayName")
    models: list[str]
    requires_key: bool = Field(..., alias="requiresKey")

    model_config = ConfigDict(populate_by_name=True)


class ProviderListResponse(BaseModel):
    """List of supported providers with their available models."""
    providers: list[ProviderInfo]


# Provider model configurations
PROVIDER_MODELS = {
    "openai": {
        "display_name": "OpenAI",
        "requires_key": True,
        "models": [
            "text-embedding-3-small",
            "text-embedding-3-large",
            "text-embedding-ada-002",
        ],
        "dimensions": {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
    },
    "voyage": {
        "display_name": "Voyage AI",
        "requires_key": True,
        "models": [
            "voyage-large-2",
            "voyage-code-2",
            "voyage-2",
        ],
        "dimensions": {
            "voyage-large-2": 1536,
            "voyage-code-2": 1536,
            "voyage-2": 1024,
        }
    },
    "local": {
        "display_name": "Local (Ollama)",
        "requires_key": False,
        "models": [
            "nomic-embed-text",
            "mxbai-embed-large",
        ],
        "dimensions": {
            "nomic-embed-text": 768,
            "mxbai-embed-large": 1024,
        }
    },
    "anthropic": {
        "display_name": "Anthropic",
        "requires_key": True,
        "models": [],
        "dimensions": {}
    },
    "groq": {
        "display_name": "Groq",
        "requires_key": True,
        "models": [],
        "dimensions": {},
    },
    "llama_cloud": {
        "display_name": "LlamaIndex Cloud",
        "requires_key": True,
        "models": [],
        "dimensions": {},
    },
    "landing_ai": {
        "display_name": "Landing AI",
        "requires_key": True,
        "models": [],
        "dimensions": {},
    },
    "ollama_cloud": {
        "display_name": "Ollama Cloud",
        "requires_key": True,
        "models": [],
        "dimensions": {},
    },
}


def get_model_dimensions(provider: str, model: str) -> int:
    """Get the embedding dimensions for a specific provider/model combination."""
    if provider not in PROVIDER_MODELS:
        raise ValueError(f"Unknown provider: {provider}")

    provider_config = PROVIDER_MODELS[provider]
    if model not in provider_config["dimensions"]:
        raise ValueError(f"Unknown model '{model}' for provider '{provider}'")

    return provider_config["dimensions"][model]


def get_available_models(provider: str) -> list[str]:
    """Get available models for a provider."""
    if provider not in PROVIDER_MODELS:
        return []
    return PROVIDER_MODELS[provider]["models"]
