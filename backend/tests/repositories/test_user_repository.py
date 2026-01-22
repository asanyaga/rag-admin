import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthProvider, User
from app.repositories import UserRepository


@pytest.fixture
def user_repo(test_db: AsyncSession) -> UserRepository:
    return UserRepository(test_db)


@pytest.mark.asyncio
async def test_create_user_with_email_auth(user_repo: UserRepository):
    user = User(
        email="test@example.com",
        full_name="Test User",
        password_hash="hashed_password",
        auth_provider=AuthProvider.email
    )

    created_user = await user_repo.create(user)

    assert created_user.id is not None
    assert created_user.email == "test@example.com"
    assert created_user.full_name == "Test User"
    assert created_user.password_hash == "hashed_password"
    assert created_user.auth_provider == AuthProvider.email
    assert created_user.is_active is True


@pytest.mark.asyncio
async def test_create_user_with_google_auth(user_repo: UserRepository):
    user = User(
        email="google@example.com",
        full_name="Google User",
        auth_provider=AuthProvider.google,
        google_id="google123"
    )

    created_user = await user_repo.create(user)

    assert created_user.id is not None
    assert created_user.email == "google@example.com"
    assert created_user.auth_provider == AuthProvider.google
    assert created_user.google_id == "google123"
    assert created_user.password_hash is None


@pytest.mark.asyncio
async def test_get_by_email_found(user_repo: UserRepository):
    user = User(
        email="findme@example.com",
        password_hash="hash",
        auth_provider=AuthProvider.email
    )
    await user_repo.create(user)

    found_user = await user_repo.get_by_email("findme@example.com")

    assert found_user is not None
    assert found_user.email == "findme@example.com"


@pytest.mark.asyncio
async def test_get_by_email_not_found(user_repo: UserRepository):
    found_user = await user_repo.get_by_email("notfound@example.com")

    assert found_user is None


@pytest.mark.asyncio
async def test_get_by_google_id_found(user_repo: UserRepository):
    user = User(
        email="google@example.com",
        auth_provider=AuthProvider.google,
        google_id="google456"
    )
    await user_repo.create(user)

    found_user = await user_repo.get_by_google_id("google456")

    assert found_user is not None
    assert found_user.google_id == "google456"


@pytest.mark.asyncio
async def test_get_by_google_id_not_found(user_repo: UserRepository):
    found_user = await user_repo.get_by_google_id("notfound")

    assert found_user is None


@pytest.mark.asyncio
async def test_email_uniqueness_constraint(user_repo: UserRepository):
    user1 = User(
        email="duplicate@example.com",
        password_hash="hash1",
        auth_provider=AuthProvider.email
    )
    await user_repo.create(user1)

    user2 = User(
        email="duplicate@example.com",
        password_hash="hash2",
        auth_provider=AuthProvider.email
    )

    with pytest.raises(IntegrityError):
        await user_repo.create(user2)


@pytest.mark.asyncio
async def test_google_id_uniqueness_constraint(user_repo: UserRepository):
    user1 = User(
        email="user1@example.com",
        auth_provider=AuthProvider.google,
        google_id="google789"
    )
    await user_repo.create(user1)

    user2 = User(
        email="user2@example.com",
        auth_provider=AuthProvider.google,
        google_id="google789"
    )

    with pytest.raises(IntegrityError):
        await user_repo.create(user2)


@pytest.mark.asyncio
async def test_get_by_id(user_repo: UserRepository):
    user = User(
        email="byid@example.com",
        password_hash="hash",
        auth_provider=AuthProvider.email
    )
    created_user = await user_repo.create(user)

    found_user = await user_repo.get_by_id(created_user.id)

    assert found_user is not None
    assert found_user.id == created_user.id
    assert found_user.email == "byid@example.com"


@pytest.mark.asyncio
async def test_update_user(user_repo: UserRepository):
    user = User(
        email="update@example.com",
        full_name="Original Name",
        password_hash="hash",
        auth_provider=AuthProvider.email
    )
    created_user = await user_repo.create(user)

    created_user.full_name = "Updated Name"
    updated_user = await user_repo.update(created_user)

    assert updated_user.full_name == "Updated Name"
    assert updated_user.email == "update@example.com"
