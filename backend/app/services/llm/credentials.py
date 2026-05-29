"""LLM-specific credential resolution.

Single entry point for resolving a provider's API key and optional base URL
before constructing an adapter.  All LLM-calling features use this instead of
doing their own ProviderKeyRepository lookups.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.provider_key_repository import ProviderKeyRepository
from app.services.exceptions import ValidationError
from app.utils.encryption import decrypt

# Providers that require no user-supplied key (local instances).
_NO_KEY_PROVIDERS: frozenset[str] = frozenset({"ollama_local"})


@dataclass
class ProviderCredentials:
    """Resolved credentials for a single LLM provider call."""
    api_key: str
    base_url: str | None  # None = use the adapter's built-in default endpoint


async def resolve_provider_credentials(
    provider: str,
    user_id: UUID,
    project_id: UUID,
    db: AsyncSession,
) -> ProviderCredentials:
    """Return decrypted credentials for *provider*.

    - ``ollama_local``: returns a dummy key immediately, no DB call.
    - All other providers: fetch from ``ProviderKeyRepository``.
      Raises ``ValidationError`` if no key is found.
    """
    if provider in _NO_KEY_PROVIDERS:
        return ProviderCredentials(api_key="ollama", base_url=None)

    repo = ProviderKeyRepository(db)
    key_record = await repo.get_for_provider(user_id, provider, project_id)
    if not key_record:
        raise ValidationError(f"No API key configured for provider '{provider}'")

    return ProviderCredentials(
        api_key=decrypt(key_record.api_key_encrypted),
        base_url=key_record.base_url,
    )
