# backend/app/dependencies/llm.py
from functools import lru_cache

from app.config import settings
from app.services.llm.ollama_adapter import OllamaAdapter
from app.services.llm.groq_adapter import GroqAdapter
from app.services.llm.registry import LLMRegistry


@lru_cache(maxsize=1)
def get_llm_registry() -> LLMRegistry:
    """Build and cache the LLM adapter registry from env config.

    Provider names are the routing keys clients pass in requests:
      ollama_local  — local Ollama instance (always registered)
      ollama_cloud  — Ollama Cloud (registered only if OLLAMA_CLOUD_API_KEY is set)
      groq          — Groq hosted inference (registered only if GROQ_API_KEY is set)
    """
    registry = LLMRegistry()
    registry.register(
        "ollama_local",
        OllamaAdapter(base_url=settings.OLLAMA_LOCAL_BASE_URL, api_key="ollama"),
    )
    if settings.OLLAMA_CLOUD_API_KEY:
        registry.register(
            "ollama_cloud",
            OllamaAdapter(
                base_url=settings.OLLAMA_CLOUD_BASE_URL,
                api_key=settings.OLLAMA_CLOUD_API_KEY,
            ),
        )
    if settings.GROQ_API_KEY:
        registry.register("groq", GroqAdapter(api_key=settings.GROQ_API_KEY))
    return registry
