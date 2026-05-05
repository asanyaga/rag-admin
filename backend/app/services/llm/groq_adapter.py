"""Groq LLM adapter."""

from app.services.llm.openai_adapter import OpenAIAdapter


class GroqAdapter(OpenAIAdapter):
    """OpenAI-compatible adapter pointing at Groq's hosted inference."""

    _provider_name = "groq"

    def __init__(self, api_key: str):
        super().__init__(api_key=api_key, base_url="https://api.groq.com/openai/v1")
