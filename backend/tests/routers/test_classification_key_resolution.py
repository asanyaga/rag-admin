from unittest.mock import patch

from app.routers.classification import _classification_provider_to_byok, _build_llm_registry


def test_provider_mapping_groq():
    assert _classification_provider_to_byok("groq") == "groq"


def test_provider_mapping_ollama_cloud():
    assert _classification_provider_to_byok("ollama_cloud") == "ollama_cloud"


def test_provider_mapping_ollama_local_returns_none():
    assert _classification_provider_to_byok("ollama_local") is None


def test_provider_mapping_unknown_returns_none():
    assert _classification_provider_to_byok("some_unknown_provider") is None


def test_build_registry_groq_with_key():
    registry = _build_llm_registry("groq", "my-groq-key")
    assert registry.has("groq")


def test_build_registry_groq_without_key_not_registered():
    registry = _build_llm_registry("groq", None)
    assert not registry.has("groq")


def test_build_registry_ollama_local_always_registered():
    with patch("app.routers.classification.settings") as mock_settings:
        mock_settings.OLLAMA_LOCAL_BASE_URL = "http://localhost:11434/v1"
        registry = _build_llm_registry("ollama_local", None)
    assert registry.has("ollama_local")


def test_build_registry_ollama_cloud_with_key():
    with patch("app.routers.classification.settings") as mock_settings:
        mock_settings.OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"
        registry = _build_llm_registry("ollama_cloud", "cloud-key-abc")
    assert registry.has("ollama_cloud")
