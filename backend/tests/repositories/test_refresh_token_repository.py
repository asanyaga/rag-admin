from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthProvider, RefreshToken, User
from app.repositories import RefreshTokenRepository, UserRepository


@pytest.fixture
async def user(test_db: AsyncSession) -> User:
    user_repo = UserRepository(test_db)
    user = User(
        email="tokenuser@example.com",
        password_hash="hash",
        auth_provider=AuthProvider.email
    )
    return await user_repo.create(user)


@pytest.fixture
def token_repo(test_db: AsyncSession) -> RefreshTokenRepository:
    return RefreshTokenRepository(test_db)


@pytest.mark.asyncio
async def test_create_token(token_repo: RefreshTokenRepository, user: User):
    token = RefreshToken(
        user_id=user.id,
        token_hash="hash123",
        expires_at=datetime.utcnow() + timedelta(days=7)
    )

    created_token = await token_repo.create(token)

    assert created_token.id is not None
    assert created_token.user_id == user.id
    assert created_token.token_hash == "hash123"
    assert created_token.revoked_at is None


@pytest.mark.asyncio
async def test_get_valid_token(token_repo: RefreshTokenRepository, user: User):
    token = RefreshToken(
        user_id=user.id,
        token_hash="validtoken",
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    await token_repo.create(token)

    found_token = await token_repo.get_valid_by_token_hash("validtoken")

    assert found_token is not None
    assert found_token.token_hash == "validtoken"
    assert found_token.is_valid is True


@pytest.mark.asyncio
async def test_get_expired_token_returns_none(token_repo: RefreshTokenRepository, user: User):
    token = RefreshToken(
        user_id=user.id,
        token_hash="expiredtoken",
        expires_at=datetime.utcnow() - timedelta(days=1)
    )
    await token_repo.create(token)

    found_token = await token_repo.get_valid_by_token_hash("expiredtoken")

    assert found_token is None


@pytest.mark.asyncio
async def test_get_revoked_token_returns_none(token_repo: RefreshTokenRepository, user: User):
    token = RefreshToken(
        user_id=user.id,
        token_hash="revokedtoken",
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    created_token = await token_repo.create(token)

    await token_repo.revoke(created_token)

    found_token = await token_repo.get_valid_by_token_hash("revokedtoken")

    assert found_token is None


@pytest.mark.asyncio
async def test_revoke_token(token_repo: RefreshTokenRepository, user: User):
    token = RefreshToken(
        user_id=user.id,
        token_hash="torevoke",
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    created_token = await token_repo.create(token)

    assert created_token.revoked_at is None

    revoked_token = await token_repo.revoke(created_token)

    assert revoked_token.revoked_at is not None
    assert revoked_token.is_valid is False


@pytest.mark.asyncio
async def test_revoke_all_for_user(token_repo: RefreshTokenRepository, user: User):
    token1 = RefreshToken(
        user_id=user.id,
        token_hash="token1",
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    token2 = RefreshToken(
        user_id=user.id,
        token_hash="token2",
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    await token_repo.create(token1)
    await token_repo.create(token2)

    count = await token_repo.revoke_all_for_user(user.id)

    assert count == 2

    found_token1 = await token_repo.get_valid_by_token_hash("token1")
    found_token2 = await token_repo.get_valid_by_token_hash("token2")

    assert found_token1 is None
    assert found_token2 is None


@pytest.mark.asyncio
async def test_delete_expired(token_repo: RefreshTokenRepository, user: User):
    old_token = RefreshToken(
        user_id=user.id,
        token_hash="oldtoken",
        expires_at=datetime.utcnow() - timedelta(days=10)
    )
    recent_token = RefreshToken(
        user_id=user.id,
        token_hash="recenttoken",
        expires_at=datetime.utcnow() - timedelta(days=3)
    )
    await token_repo.create(old_token)
    await token_repo.create(recent_token)

    count = await token_repo.delete_expired(older_than_days=7)

    assert count == 1

    found_old = await token_repo.get_by_token_hash("oldtoken")
    found_recent = await token_repo.get_by_token_hash("recenttoken")

    assert found_old is None
    assert found_recent is not None


@pytest.mark.asyncio
async def test_is_valid_property(user: User):
    valid_token = RefreshToken(
        user_id=user.id,
        token_hash="valid",
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    expired_token = RefreshToken(
        user_id=user.id,
        token_hash="expired",
        expires_at=datetime.utcnow() - timedelta(days=1)
    )
    revoked_token = RefreshToken(
        user_id=user.id,
        token_hash="revoked",
        expires_at=datetime.utcnow() + timedelta(days=7),
        revoked_at=datetime.utcnow()
    )

    assert valid_token.is_valid is True
    assert expired_token.is_valid is False
    assert revoked_token.is_valid is False
