from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_valid_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        """Get token only if not expired and not revoked."""
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.utcnow()
            )
        )
        return result.scalar_one_or_none()

    async def create(self, token: RefreshToken) -> RefreshToken:
        self.session.add(token)
        await self.session.commit()
        await self.session.refresh(token)
        return token

    async def revoke(self, token: RefreshToken) -> RefreshToken:
        """Set revoked_at to now."""
        token.revoked_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(token)
        return token

    async def revoke_all_for_user(self, user_id: UUID) -> int:
        """Revoke all tokens for user, return count revoked."""
        result = await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None)
            )
            .values(revoked_at=datetime.utcnow())
        )
        await self.session.commit()
        return result.rowcount

    async def delete_expired(self, older_than_days: int = 7) -> int:
        """Delete tokens expired more than N days ago."""
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.expires_at < cutoff_date)
        )
        tokens = result.scalars().all()

        for token in tokens:
            await self.session.delete(token)

        await self.session.commit()
        return len(tokens)
