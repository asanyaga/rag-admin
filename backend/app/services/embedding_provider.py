"""Embedding provider abstraction for generating vector embeddings.

Provides a pluggable interface for different embedding providers (OpenAI, Voyage, local).
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Protocol
import logging

from openai import AsyncOpenAI

from app.schemas.provider_key import PROVIDER_MODELS, get_model_dimensions

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts. Returns list of embedding vectors."""
        ...

    def get_dimensions(self, model: str) -> int:
        """Return the output dimensions for a given model."""
        ...

    def list_models(self) -> list[str]:
        """Return available models for this provider."""
        ...


class OpenAIEmbeddingProvider:
    """OpenAI embedding provider using text-embedding-3-* models."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self._batch_size = 100  # OpenAI recommends batches of 100

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using OpenAI API.

        Handles batching automatically for large text lists.
        """
        if not texts:
            return []

        all_embeddings = []

        # Process in batches
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i:i + self._batch_size]

            try:
                response = await self.client.embeddings.create(
                    input=batch,
                    model=self.model
                )

                # Extract embeddings in order
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)

                logger.debug(
                    f"Embedded batch {i // self._batch_size + 1}, "
                    f"texts: {len(batch)}, total so far: {len(all_embeddings)}"
                )

            except Exception as e:
                logger.error(f"OpenAI embedding error: {e}")
                raise

        return all_embeddings

    def get_dimensions(self, model: str | None = None) -> int:
        """Get embedding dimensions for the model."""
        model = model or self.model
        return get_model_dimensions("openai", model)

    def list_models(self) -> list[str]:
        """List available OpenAI embedding models."""
        return PROVIDER_MODELS["openai"]["models"]


class VoyageEmbeddingProvider:
    """Voyage AI embedding provider (placeholder for future implementation)."""

    def __init__(self, api_key: str, model: str = "voyage-large-2"):
        self.api_key = api_key
        self.model = model
        self._batch_size = 128

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using Voyage AI API."""
        # TODO: Implement Voyage AI integration
        raise NotImplementedError("Voyage AI provider not yet implemented")

    def get_dimensions(self, model: str | None = None) -> int:
        """Get embedding dimensions for the model."""
        model = model or self.model
        return get_model_dimensions("voyage", model)

    def list_models(self) -> list[str]:
        """List available Voyage embedding models."""
        return PROVIDER_MODELS["voyage"]["models"]


class LocalEmbeddingProvider:
    """Local embedding provider using Ollama (placeholder for future implementation)."""

    def __init__(self, model: str = "nomic-embed-text", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using local Ollama server."""
        # TODO: Implement Ollama integration
        raise NotImplementedError("Local embedding provider not yet implemented")

    def get_dimensions(self, model: str | None = None) -> int:
        """Get embedding dimensions for the model."""
        model = model or self.model
        return get_model_dimensions("local", model)

    def list_models(self) -> list[str]:
        """List available local embedding models."""
        return PROVIDER_MODELS["local"]["models"]


class EmbeddingProviderRegistry:
    """Registry for embedding providers."""

    _providers: dict[str, type] = {
        "openai": OpenAIEmbeddingProvider,
        "voyage": VoyageEmbeddingProvider,
        "local": LocalEmbeddingProvider,
    }

    @classmethod
    def get_provider(
        cls,
        provider_name: str,
        api_key: str | None = None,
        model: str | None = None
    ) -> EmbeddingProvider:
        """Get an embedding provider instance.

        Args:
            provider_name: Name of the provider (openai, voyage, local)
            api_key: API key for the provider (required for openai, voyage)
            model: Optional model name to use

        Returns:
            Configured embedding provider instance

        Raises:
            ValueError: Unknown provider or missing API key
        """
        if provider_name not in cls._providers:
            raise ValueError(f"Unknown embedding provider: {provider_name}")

        provider_class = cls._providers[provider_name]

        # Build kwargs based on provider requirements
        kwargs = {}
        if model:
            kwargs["model"] = model

        if provider_name in ["openai", "voyage"]:
            if not api_key:
                raise ValueError(f"API key required for {provider_name} provider")
            kwargs["api_key"] = api_key

        return provider_class(**kwargs)

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names."""
        return list(cls._providers.keys())

    @classmethod
    def register(cls, name: str, provider_class: type) -> None:
        """Register a new provider class."""
        cls._providers[name] = provider_class
