"""Repository for provider key data access."""
from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProviderKey


class ProviderKeyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: UUID,
        provider: str,
        api_key_encrypted: str,
        project_id: UUID | None = None
    ) -> ProviderKey:
        """Create a new provider key."""
        key = ProviderKey(
            user_id=user_id,
            project_id=project_id,
            provider=provider,
            api_key_encrypted=api_key_encrypted
        )
        self.session.add(key)
        await self.session.commit()
        await self.session.refresh(key)
        return key

    async def get_by_id(self, key_id: UUID, user_id: UUID) -> ProviderKey | None:
        """Get a provider key by ID, scoped to the user."""
        result = await self.session.execute(
            select(ProviderKey).where(
                ProviderKey.id == key_id,
                ProviderKey.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def get_for_provider(
        self,
        user_id: UUID,
        provider: str,
        project_id: UUID | None = None
    ) -> ProviderKey | None:
        """Get a provider key for a specific provider.

        Resolution order: project-level key → account-level key
        """
        # First, try project-level key if project_id is provided
        if project_id:
            result = await self.session.execute(
                select(ProviderKey).where(
                    ProviderKey.user_id == user_id,
                    ProviderKey.project_id == project_id,
                    ProviderKey.provider == provider
                )
            )
            key = result.scalar_one_or_none()
            if key:
                return key

        # Fall back to account-level key (project_id is NULL)
        result = await self.session.execute(
            select(ProviderKey).where(
                ProviderKey.user_id == user_id,
                ProviderKey.project_id.is_(None),
                ProviderKey.provider == provider
            )
        )
        return result.scalar_one_or_none()

    async def get_account_key(
        self,
        user_id: UUID,
        provider: str
    ) -> ProviderKey | None:
        """Get account-level key for a provider (project_id is NULL)."""
        result = await self.session.execute(
            select(ProviderKey).where(
                ProviderKey.user_id == user_id,
                ProviderKey.project_id.is_(None),
                ProviderKey.provider == provider
            )
        )
        return result.scalar_one_or_none()

    async def get_project_key(
        self,
        user_id: UUID,
        project_id: UUID,
        provider: str
    ) -> ProviderKey | None:
        """Get project-level key for a provider."""
        result = await self.session.execute(
            select(ProviderKey).where(
                ProviderKey.user_id == user_id,
                ProviderKey.project_id == project_id,
                ProviderKey.provider == provider
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: UUID) -> list[ProviderKey]:
        """List all provider keys for a user (account and project level)."""
        result = await self.session.execute(
            select(ProviderKey)
            .where(ProviderKey.user_id == user_id)
            .order_by(ProviderKey.provider, ProviderKey.project_id)
        )
        return list(result.scalars().all())

    async def list_account_keys(self, user_id: UUID) -> list[ProviderKey]:
        """List account-level keys for a user."""
        result = await self.session.execute(
            select(ProviderKey)
            .where(
                ProviderKey.user_id == user_id,
                ProviderKey.project_id.is_(None)
            )
            .order_by(ProviderKey.provider)
        )
        return list(result.scalars().all())

    async def list_project_keys(self, user_id: UUID, project_id: UUID) -> list[ProviderKey]:
        """List project-level keys for a specific project."""
        result = await self.session.execute(
            select(ProviderKey)
            .where(
                ProviderKey.user_id == user_id,
                ProviderKey.project_id == project_id
            )
            .order_by(ProviderKey.provider)
        )
        return list(result.scalars().all())

    async def update(
        self,
        key_id: UUID,
        user_id: UUID,
        api_key_encrypted: str
    ) -> ProviderKey | None:
        """Update a provider key's encrypted value."""
        key = await self.get_by_id(key_id, user_id)
        if not key:
            return None

        key.api_key_encrypted = api_key_encrypted
        await self.session.commit()
        await self.session.refresh(key)
        return key

    async def upsert(
        self,
        user_id: UUID,
        provider: str,
        api_key_encrypted: str,
        project_id: UUID | None = None
    ) -> ProviderKey:
        """Create or update a provider key."""
        if project_id:
            existing = await self.get_project_key(user_id, project_id, provider)
        else:
            existing = await self.get_account_key(user_id, provider)

        if existing:
            existing.api_key_encrypted = api_key_encrypted
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        return await self.create(user_id, provider, api_key_encrypted, project_id)

    async def delete_account_key(self, user_id: UUID, provider: str) -> bool:
        """Delete an account-level key. Returns True if deleted."""
        result = await self.session.execute(
            delete(ProviderKey).where(
                ProviderKey.user_id == user_id,
                ProviderKey.project_id.is_(None),
                ProviderKey.provider == provider
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def delete_project_key(
        self,
        user_id: UUID,
        project_id: UUID,
        provider: str
    ) -> bool:
        """Delete a project-level key. Returns True if deleted."""
        result = await self.session.execute(
            delete(ProviderKey).where(
                ProviderKey.user_id == user_id,
                ProviderKey.project_id == project_id,
                ProviderKey.provider == provider
            )
        )
        await self.session.commit()
        return result.rowcount > 0
