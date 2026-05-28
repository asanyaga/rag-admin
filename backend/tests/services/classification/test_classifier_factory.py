from unittest.mock import patch
import pytest
from app.services.classification.classifier_factory import (
    _resolve_byok_provider,
    build_classifier,
)
from app.services.classification.llm_classifier import LLMClassifier
from app.services.classification.llamaindex_split_classifier import LlamaIndexSplitClassifier


def test_resolve_byok_groq():
    assert _resolve_byok_provider("llm", {"provider": "groq"}) == "groq"


def test_resolve_byok_ollama_cloud():
    assert _resolve_byok_provider("llm", {"provider": "ollama_cloud"}) == "ollama_cloud"


def test_resolve_byok_anthropic():
    assert _resolve_byok_provider("llm", {"provider": "anthropic"}) == "anthropic"


def test_resolve_byok_openai():
    assert _resolve_byok_provider("llm", {"provider": "openai"}) == "openai"


def test_resolve_byok_ollama_local_returns_none():
    assert _resolve_byok_provider("llm", {"provider": "ollama_local"}) is None


def test_resolve_byok_non_llm_returns_none():
    assert _resolve_byok_provider("llamaindex_split", {}) is None


def test_build_classifier_llm_returns_llm_classifier():
    with patch("app.services.classification.classifier_factory.settings") as mock:
        mock.OLLAMA_LOCAL_BASE_URL = "http://localhost:11434/v1"
        mock.OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"
        classifier = build_classifier(
            "llm",
            {"provider": "ollama_local", "model": "qwen2.5:7b",
             "batch_size": 10, "batch_overlap": 3},
            api_key=None,
        )
    assert isinstance(classifier, LLMClassifier)
    assert classifier.provider == "ollama_local"
    assert classifier.model == "qwen2.5:7b"
    assert classifier.batch_size == 10
    assert classifier.batch_overlap == 3


def test_build_classifier_llm_threads_llm_config():
    with patch("app.services.classification.classifier_factory.settings") as mock:
        mock.OLLAMA_LOCAL_BASE_URL = "http://localhost:11434/v1"
        mock.OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"
        classifier = build_classifier(
            "llm",
            {
                "provider": "ollama_local",
                "model": "qwen2.5:7b",
                "llm_config": {"system_prompt": "Custom", "temperature": 0.5, "max_tokens": 2048},
            },
            api_key=None,
        )
    assert isinstance(classifier, LLMClassifier)
    assert classifier.system_prompt == "Custom"
    assert classifier.temperature == 0.5
    assert classifier.max_tokens == 2048


def test_build_classifier_llamaindex_split():
    classifier = build_classifier("llamaindex_split", {"chunk_size": 512}, api_key=None)
    assert isinstance(classifier, LlamaIndexSplitClassifier)


def test_build_classifier_unknown_raises():
    with pytest.raises(ValueError, match="Unknown classifier type"):
        build_classifier("nonexistent", {}, api_key=None)
