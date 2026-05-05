"""Ollama LLM adapter."""

from app.services.llm.openai_adapter import OpenAIAdapter


class OllamaAdapter(OpenAIAdapter):
    """OpenAI-compatible adapter pointing at a local Ollama instance."""

    _provider_name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434/v1"):
        super().__init__(api_key="ollama", base_url=base_url)
