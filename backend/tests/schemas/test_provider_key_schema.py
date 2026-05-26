"""Tests for provider key schema."""
from app.schemas.provider_key import SUPPORTED_PROVIDERS, PROVIDER_MODELS


def test_new_providers_in_supported_list():
    for p in ("groq", "llama_cloud", "landing_ai", "ollama_cloud"):
        assert p in SUPPORTED_PROVIDERS, f"{p} missing from SUPPORTED_PROVIDERS"


def test_new_providers_in_models_dict():
    for p in ("groq", "llama_cloud", "landing_ai", "ollama_cloud"):
        assert p in PROVIDER_MODELS, f"{p} missing from PROVIDER_MODELS"
        assert PROVIDER_MODELS[p]["requires_key"] is True
