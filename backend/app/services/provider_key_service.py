"""Service for provider key management (BYOK)."""
from uuid import UUID

from app.config import settings
from app.repositories.provider_key_repository import ProviderKeyRepository
from app.schemas.provider_key import (
    ProviderKeyCreate,
    ProviderKeyResponse,
    ProviderKeyListResponse,
    ProviderInfo,
    ProviderListResponse,
    PROVIDER_MODELS,
    SUPPORTED_PROVIDERS,
)
from app.services.exceptions import NotFoundError, ValidationError
from app.utils.encryption import encrypt, decrypt, mask_key


class ProviderKeyService:
    def __init__(self, provider_key_repo: ProviderKeyRepository):
        self.provider_key_repo = provider_key_repo

    def _to_response(self, key) -> ProviderKeyResponse:
        """Convert a ProviderKey model to a response with masked key."""
        decrypted = decrypt(key.api_key_encrypted)
        return ProviderKeyResponse(
            id=key.id,
            user_id=key.user_id,
            project_id=key.project_id,
            provider=key.provider,
            api_key_masked=mask_key(decrypted),
            created_at=key.created_at,
            updated_at=key.updated_at,
        )

    async def set_account_key(
        self,
        user_id: UUID,
        data: ProviderKeyCreate
    ) -> ProviderKeyResponse:
        """Set an account-level provider key.

        This key will be used for all projects unless overridden at project level.

        Raises:
        - ValidationError: Provider is not supported
        """
        if data.provider not in SUPPORTED_PROVIDERS:
            raise ValidationError(f"Unsupported provider: {data.provider}")

        encrypted = encrypt(data.api_key)
        key = await self.provider_key_repo.upsert(
            user_id=user_id,
            provider=data.provider,
            api_key_encrypted=encrypted,
            project_id=None
        )
        return self._to_response(key)

    async def set_project_key(
        self,
        user_id: UUID,
        project_id: UUID,
        data: ProviderKeyCreate
    ) -> ProviderKeyResponse:
        """Set a project-level provider key.

        This key will override any account-level key for this project.

        Raises:
        - ValidationError: Provider is not supported
        """
        if data.provider not in SUPPORTED_PROVIDERS:
            raise ValidationError(f"Unsupported provider: {data.provider}")

        encrypted = encrypt(data.api_key)
        key = await self.provider_key_repo.upsert(
            user_id=user_id,
            provider=data.provider,
            api_key_encrypted=encrypted,
            project_id=project_id
        )
        return self._to_response(key)

    async def get_key_for_provider(
        self,
        user_id: UUID,
        provider: str,
        project_id: UUID | None = None
    ) -> str:
        """Get the decrypted API key for a provider.

        Resolution order: project-level key → account-level key

        Raises:
        - NotFoundError: No API key configured for this provider
        """
        key = await self.provider_key_repo.get_for_provider(
            user_id=user_id,
            provider=provider,
            project_id=project_id
        )
        if not key:
            raise NotFoundError(f"No API key configured for provider '{provider}'")

        return decrypt(key.api_key_encrypted)

    async def list_account_keys(self, user_id: UUID) -> ProviderKeyListResponse:
        """List all account-level provider keys."""
        keys = await self.provider_key_repo.list_account_keys(user_id)
        return ProviderKeyListResponse(
            keys=[self._to_response(k) for k in keys]
        )

    async def list_project_keys(
        self,
        user_id: UUID,
        project_id: UUID
    ) -> ProviderKeyListResponse:
        """List all project-level provider keys."""
        keys = await self.provider_key_repo.list_project_keys(user_id, project_id)
        return ProviderKeyListResponse(
            keys=[self._to_response(k) for k in keys]
        )

    async def delete_account_key(self, user_id: UUID, provider: str) -> None:
        """Delete an account-level provider key.

        Raises:
        - NotFoundError: Key not found
        """
        deleted = await self.provider_key_repo.delete_account_key(user_id, provider)
        if not deleted:
            raise NotFoundError(f"No account-level key found for provider '{provider}'")

    async def delete_project_key(
        self,
        user_id: UUID,
        project_id: UUID,
        provider: str
    ) -> None:
        """Delete a project-level provider key.

        Raises:
        - NotFoundError: Key not found
        """
        deleted = await self.provider_key_repo.delete_project_key(
            user_id, project_id, provider
        )
        if not deleted:
            raise NotFoundError(f"No project-level key found for provider '{provider}'")

    def list_providers(self) -> ProviderListResponse:
        """List all supported providers with their available models."""
        providers = []
        for name, config in PROVIDER_MODELS.items():
            providers.append(ProviderInfo(
                name=name,
                display_name=config["display_name"],
                models=config["models"],
                requires_key=config["requires_key"],
            ))
        return ProviderListResponse(providers=providers)

    async def has_key_for_provider(
        self,
        user_id: UUID,
        provider: str,
        project_id: UUID | None = None
    ) -> bool:
        """Check if a key exists for a provider (without decrypting)."""
        key = await self.provider_key_repo.get_for_provider(
            user_id=user_id,
            provider=provider,
            project_id=project_id
        )
        return key is not None


async def resolve_api_key(
    repo: ProviderKeyRepository,
    user_id: UUID,
    provider: str,
    project_id: UUID | None = None,
) -> str | None:
    """Resolve an API key: DB first (project-level → account-level), then env-var fallback.

    Returns None if no key is found in either source.
    Empty string env vars are treated as not configured.
    """
    key_record = await repo.get_for_provider(
        user_id=user_id,
        provider=provider,
        project_id=project_id,
    )
    if key_record:
        return decrypt(key_record.api_key_encrypted)

    env_fallbacks: dict[str, str] = {
        "groq":         settings.GROQ_API_KEY,
        "llama_cloud":  settings.LLAMA_CLOUD_KEY,
        "landing_ai":   settings.VISION_AGENT_API_KEY,
        "ollama_cloud": settings.OLLAMA_CLOUD_API_KEY,
        "ollama_local": "ollama",  # local Ollama doesn't need a real key
    }
    value = env_fallbacks.get(provider, "")
    return value if value else None
