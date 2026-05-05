"""Tests for OpenAI-compatible adapters (Ollama, Groq)."""

from unittest.mock import AsyncMock, patch
import pytest
from app.services.llm.ollama_adapter import OllamaAdapter
from app.services.llm.groq_adapter import GroqAdapter
from app.services.llm.types import LLMConfig


def test_ollama_adapter_init():
    adapter = OllamaAdapter(base_url="http://localhost:11434/v1")
    assert str(adapter.client.base_url) == "http://localhost:11434/v1/"


def test_ollama_adapter_default_base_url():
    adapter = OllamaAdapter()
    assert "11434" in str(adapter.client.base_url)


def test_groq_adapter_init():
    adapter = GroqAdapter(api_key="test-key")
    assert "groq.com" in str(adapter.client.base_url)
