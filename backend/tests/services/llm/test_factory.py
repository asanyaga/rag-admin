import pytest
from unittest.mock import patch


def _patched_settings():
    s = patch("app.services.llm.factory.settings")
    mock = s.start()
    mock.OLLAMA_LOCAL_BASE_URL = "http://localhost:11434/v1"
    mock.OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"
    return s


def test_create_adapter_openai():
    from app.services.llm.openai_adapter import OpenAIAdapter
    from app.services.llm.factory import create_adapter
    p = _patched_settings()
    adapter = create_adapter("openai", "sk-test")
    assert isinstance(adapter, OpenAIAdapter)
    p.stop()


def test_create_adapter_anthropic():
    from app.services.llm.anthropic_adapter import AnthropicAdapter
    from app.services.llm.factory import create_adapter
    p = _patched_settings()
    adapter = create_adapter("anthropic", "sk-ant-test")
    assert isinstance(adapter, AnthropicAdapter)
    p.stop()


def test_create_adapter_groq():
    from app.services.llm.groq_adapter import GroqAdapter
    from app.services.llm.factory import create_adapter
    p = _patched_settings()
    adapter = create_adapter("groq", "gsk-test")
    assert isinstance(adapter, GroqAdapter)
    p.stop()


def test_create_adapter_ollama_local():
    from app.services.llm.ollama_adapter import OllamaAdapter
    from app.services.llm.factory import create_adapter
    p = _patched_settings()
    adapter = create_adapter("ollama_local", "ollama")
    assert isinstance(adapter, OllamaAdapter)
    p.stop()


def test_create_adapter_ollama_cloud():
    from app.services.llm.ollama_adapter import OllamaAdapter
    from app.services.llm.factory import create_adapter
    p = _patched_settings()
    adapter = create_adapter("ollama_cloud", "key")
    assert isinstance(adapter, OllamaAdapter)
    p.stop()


def test_create_adapter_openai_with_custom_base_url():
    from app.services.llm.openai_adapter import OpenAIAdapter
    from app.services.llm.factory import create_adapter
    p = _patched_settings()
    adapter = create_adapter("openai", "sk-test", base_url="https://my-vllm.example.com/v1")
    assert isinstance(adapter, OpenAIAdapter)
    assert "my-vllm" in str(adapter.client.base_url)
    p.stop()


def test_create_adapter_unknown_raises_value_error():
    from app.services.llm.factory import create_adapter
    p = _patched_settings()
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        create_adapter("mistral", "key")
    p.stop()
