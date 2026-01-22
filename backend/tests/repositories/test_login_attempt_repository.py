from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthProvider, LoginAttempt, User
from app.repositories import LoginAttemptRepository, UserRepository


@pytest.fixture
async def user(test_db: AsyncSession) -> User:
    user_repo = UserRepository(test_db)
    user = User(
        email="attemptuser@example.com",
        password_hash="hash",
        auth_provider=AuthProvider.email
    )
    return await user_repo.create(user)


@pytest.fixture
def attempt_repo(test_db: AsyncSession) -> LoginAttemptRepository:
    return LoginAttemptRepository(test_db)


@pytest.mark.asyncio
async def test_create_attempt(attempt_repo: LoginAttemptRepository, user: User):
    attempt = LoginAttempt(
        user_id=user.id,
        email=user.email,
        ip_address="127.0.0.1",
        success=True
    )

    created_attempt = await attempt_repo.create(attempt)

    assert created_attempt.id is not None
    assert created_attempt.user_id == user.id
    assert created_attempt.email == user.email
    assert created_attempt.success is True


@pytest.mark.asyncio
async def test_count_recent_failures_with_failures(
    attempt_repo: LoginAttemptRepository,
    user: User
):
    for i in range(3):
        attempt = LoginAttempt(
            user_id=user.id,
            email=user.email,
            ip_address="127.0.0.1",
            success=False,
            attempted_at=datetime.utcnow() - timedelta(minutes=i)
        )
        await attempt_repo.create(attempt)

    count = await attempt_repo.count_recent_failures(user.id, minutes=15)

    assert count == 3


@pytest.mark.asyncio
async def test_count_recent_failures_without_failures(
    attempt_repo: LoginAttemptRepository,
    user: User
):
    count = await attempt_repo.count_recent_failures(user.id, minutes=15)

    assert count == 0


@pytest.mark.asyncio
async def test_count_doesnt_include_old_failures(
    attempt_repo: LoginAttemptRepository,
    user: User
):
    old_attempt = LoginAttempt(
        user_id=user.id,
        email=user.email,
        ip_address="127.0.0.1",
        success=False,
        attempted_at=datetime.utcnow() - timedelta(minutes=20)
    )
    recent_attempt = LoginAttempt(
        user_id=user.id,
        email=user.email,
        ip_address="127.0.0.1",
        success=False,
        attempted_at=datetime.utcnow() - timedelta(minutes=5)
    )
    await attempt_repo.create(old_attempt)
    await attempt_repo.create(recent_attempt)

    count = await attempt_repo.count_recent_failures(user.id, minutes=15)

    assert count == 1


@pytest.mark.asyncio
async def test_count_doesnt_include_successes(
    attempt_repo: LoginAttemptRepository,
    user: User
):
    success_attempt = LoginAttempt(
        user_id=user.id,
        email=user.email,
        ip_address="127.0.0.1",
        success=True,
        attempted_at=datetime.utcnow() - timedelta(minutes=5)
    )
    failure_attempt = LoginAttempt(
        user_id=user.id,
        email=user.email,
        ip_address="127.0.0.1",
        success=False,
        attempted_at=datetime.utcnow() - timedelta(minutes=3)
    )
    await attempt_repo.create(success_attempt)
    await attempt_repo.create(failure_attempt)

    count = await attempt_repo.count_recent_failures(user.id, minutes=15)

    assert count == 1


@pytest.mark.asyncio
async def test_delete_old(attempt_repo: LoginAttemptRepository, user: User):
    old_attempt = LoginAttempt(
        user_id=user.id,
        email=user.email,
        ip_address="127.0.0.1",
        success=True,
        attempted_at=datetime.utcnow() - timedelta(days=100)
    )
    recent_attempt = LoginAttempt(
        user_id=user.id,
        email=user.email,
        ip_address="127.0.0.1",
        success=True,
        attempted_at=datetime.utcnow() - timedelta(days=30)
    )
    await attempt_repo.create(old_attempt)
    await attempt_repo.create(recent_attempt)

    count = await attempt_repo.delete_old(older_than_days=90)

    assert count == 1
