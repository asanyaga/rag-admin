import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthProvider, User
from app.repositories import ProjectRepository, RefreshTokenRepository, UserRepository
from app.services.exceptions import ConflictError
from app.services.oauth_service import OAuthService


@pytest.fixture
def oauth_service(test_db: AsyncSession) -> OAuthService:
    user_repo = UserRepository(test_db)
    token_repo = RefreshTokenRepository(test_db)
    project_repo = ProjectRepository(test_db)
    return OAuthService(user_repo, token_repo, project_repo)


@pytest.mark.asyncio
async def test_create_new_google_user(oauth_service: OAuthService):
    """Should create new user from Google account."""
    user, access_token, refresh_token, is_new = await oauth_service.get_or_create_google_user(
        google_id="google-123",
        email="newgoogleuser@gmail.com",
        full_name="Google User",
        ip_address="127.0.0.1",
        user_agent="Test Browser"
    )

    assert is_new is True
    assert user.email == "newgoogleuser@gmail.com"
    assert user.full_name == "Google User"
    assert user.auth_provider == AuthProvider.google
    assert user.google_id == "google-123"
    assert user.password_hash is None
    assert len(access_token) > 0
    assert len(refresh_token) > 0


@pytest.mark.asyncio
async def test_find_existing_google_user(oauth_service: OAuthService, test_db: AsyncSession):
    """Should find existing Google user and not create duplicate."""
    user_repo = UserRepository(test_db)

    # Create existing Google user
    existing_user = User(
        email="existing@gmail.com",
        full_name="Existing User",
        auth_provider=AuthProvider.google,
        google_id="google-456"
    )
    existing_user = await user_repo.create(existing_user)

    # Call service with same google_id
    user, access_token, refresh_token, is_new = await oauth_service.get_or_create_google_user(
        google_id="google-456",
        email="existing@gmail.com",
        full_name="Existing User",
        ip_address="127.0.0.1",
        user_agent="Test Browser"
    )

    assert is_new is False
    assert user.id == existing_user.id
    assert user.email == "existing@gmail.com"
    assert user.google_id == "google-456"
    assert len(access_token) > 0
    assert len(refresh_token) > 0


@pytest.mark.asyncio
async def test_email_collision_with_password_user(oauth_service: OAuthService, test_db: AsyncSession):
    """Should raise ConflictError when Google email matches existing password user."""
    user_repo = UserRepository(test_db)

    # Create existing user with email auth
    existing_user = User(
        email="collision@example.com",
        password_hash="hashed_password",
        auth_provider=AuthProvider.email
    )
    await user_repo.create(existing_user)

    # Try to create Google user with same email
    with pytest.raises(ConflictError) as exc_info:
        await oauth_service.get_or_create_google_user(
            google_id="google-789",
            email="collision@example.com",
            full_name="Google User",
            ip_address="127.0.0.1",
            user_agent="Test Browser"
        )

    assert exc_info.value.code == "EMAIL_EXISTS_DIFFERENT_PROVIDER"
    assert "password" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_create_google_user_with_minimal_info(oauth_service: OAuthService):
    """Should create user even without full_name."""
    user, access_token, refresh_token, is_new = await oauth_service.get_or_create_google_user(
        google_id="google-minimal",
        email="minimal@gmail.com",
        full_name=None,
        ip_address="127.0.0.1",
        user_agent="Test Browser"
    )

    assert is_new is True
    assert user.email == "minimal@gmail.com"
    assert user.full_name is None
    assert user.google_id == "google-minimal"
    assert len(access_token) > 0
    assert len(refresh_token) > 0


@pytest.mark.asyncio
async def test_tokens_stored_with_metadata(oauth_service: OAuthService, test_db: AsyncSession):
    """Should store refresh token with IP and user agent."""
    token_repo = RefreshTokenRepository(test_db)

    user, access_token, refresh_token, is_new = await oauth_service.get_or_create_google_user(
        google_id="google-metadata",
        email="metadata@gmail.com",
        full_name="Metadata User",
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0"
    )

    # Verify refresh token was stored with metadata
    from app.utils.jwt import hash_refresh_token
    token_hash = hash_refresh_token(refresh_token)
    stored_token = await token_repo.get_by_token_hash(token_hash)

    assert stored_token is not None
    assert stored_token.user_id == user.id
    assert stored_token.ip_address == "192.168.1.1"
    assert stored_token.user_agent == "Mozilla/5.0"
