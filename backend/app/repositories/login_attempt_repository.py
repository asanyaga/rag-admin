from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LoginAttempt


class LoginAttemptRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, attempt: LoginAttempt) -> LoginAttempt:
        self.session.add(attempt)
        await self.session.commit()
        await self.session.refresh(attempt)
        return attempt

    async def count_recent_failures(
        self,
        user_id: UUID,
        minutes: int = 15
    ) -> int:
        """Count failed attempts in last N minutes."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        result = await self.session.execute(
            select(func.count(LoginAttempt.id))
            .where(
                LoginAttempt.user_id == user_id,
                LoginAttempt.success == False,
                LoginAttempt.attempted_at > cutoff_time
            )
        )
        return result.scalar_one()

    async def delete_old(self, older_than_days: int = 90) -> int:
        """Delete attempts older than N days."""
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        result = await self.session.execute(
            select(LoginAttempt).where(LoginAttempt.attempted_at < cutoff_date)
        )
        attempts = result.scalars().all()

        for attempt in attempts:
            await self.session.delete(attempt)

        await self.session.commit()
        return len(attempts)
