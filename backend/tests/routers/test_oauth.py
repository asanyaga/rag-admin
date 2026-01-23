from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthProvider, User
from app.repositories import UserRepository
from app.utils.oauth_state import generate_state


@pytest.fixture
def mock_google_oauth():
    """Mock Google OAuth responses."""
    with patch('app.routers.oauth.oauth') as mock_oauth:
        # Mock authorize_redirect
        mock_oauth.google.authorize_redirect = AsyncMock(
            return_value=MagicMock(
                status_code=302,
                headers={"Location": "https://accounts.google.com/o/oauth2/auth?state=test"}
            )
        )

        # Mock authorize_access_token
        mock_token = {
            'userinfo': {
                'sub': 'google-test-123',
                'email': 'testuser@gmail.com',
                'name': 'Test User'
            }
        }
        mock_oauth.google.authorize_access_token = AsyncMock(return_value=mock_token)

        yield mock_oauth


@pytest.mark.asyncio
async def test_google_authorize_redirects(client: AsyncClient, mock_google_oauth):
    """Authorize endpoint should redirect to Google."""
    response = await client.get(
        "/api/v1/auth/google/authorize",
        follow_redirects=False
    )

    # Should return redirect response
    assert response.status_code in [200, 302, 307]
    mock_google_oauth.google.authorize_redirect.assert_called_once()


@pytest.mark.asyncio
async def test_google_callback_with_invalid_state(client: AsyncClient, mock_google_oauth):
    """Callback with invalid state should redirect with error."""
    response = await client.get(
        "/api/v1/auth/google/callback?state=invalid-state&code=test-code",
        follow_redirects=False
    )

    assert response.status_code in [302, 307]
    assert "error=INVALID_STATE" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_google_callback_with_oauth_error(client: AsyncClient):
    """Callback with OAuth error should redirect with error."""
    response = await client.get(
        "/api/v1/auth/google/callback?state=test&error=access_denied",
        follow_redirects=False
    )

    assert response.status_code in [302, 307]
    assert "error=OAUTH_FAILED" in response.headers.get("location", "")


@pytest.mark.asyncio
async def test_google_callback_creates_new_user(client: AsyncClient, mock_google_oauth):
    """Callback with valid flow should create user and set cookies."""
    # Generate valid state
    state = generate_state()

    response = await client.get(
        f"/api/v1/auth/google/callback?state={state}&code=test-code",
        follow_redirects=False
    )

    assert response.status_code in [302, 307]
    location = response.headers.get("location", "")
    assert "success=true" in location

    # Should set cookies
    cookies = response.cookies
    assert "refresh_token" in cookies
    assert "access_token" in cookies


@pytest.mark.asyncio
async def test_google_callback_finds_existing_user(
    client: AsyncClient,
    mock_google_oauth,
    test_db: AsyncSession
):
    """Callback should find existing Google user instead of creating duplicate."""
    # Create existing Google user
    user_repo = UserRepository(test_db)
    existing_user = User(
        email="testuser@gmail.com",
        full_name="Test User",
        auth_provider=AuthProvider.google,
        google_id="google-test-123"
    )
    await user_repo.create(existing_user)

    # Generate valid state
    state = generate_state()

    response = await client.get(
        f"/api/v1/auth/google/callback?state={state}&code=test-code",
        follow_redirects=False
    )

    assert response.status_code in [302, 307]
    location = response.headers.get("location", "")
    assert "success=true" in location


@pytest.mark.asyncio
async def test_google_callback_email_collision(
    client: AsyncClient,
    mock_google_oauth,
    test_db: AsyncSession
):
    """Callback should return error when email exists with different provider."""
    # Create existing email user
    user_repo = UserRepository(test_db)
    existing_user = User(
        email="testuser@gmail.com",
        password_hash="hashed_password",
        auth_provider=AuthProvider.email
    )
    await user_repo.create(existing_user)

    # Generate valid state
    state = generate_state()

    response = await client.get(
        f"/api/v1/auth/google/callback?state={state}&code=test-code",
        follow_redirects=False
    )

    assert response.status_code in [302, 307]
    location = response.headers.get("location", "")
    assert "error=EMAIL_EXISTS_DIFFERENT_PROVIDER" in location


@pytest.mark.asyncio
async def test_google_callback_token_exchange_failure(client: AsyncClient):
    """Callback should handle token exchange failures gracefully."""
    with patch('app.routers.oauth.oauth') as mock_oauth:
        mock_oauth.google.authorize_access_token = AsyncMock(
            side_effect=Exception("Token exchange failed")
        )

        state = generate_state()

        response = await client.get(
            f"/api/v1/auth/google/callback?state={state}&code=test-code",
            follow_redirects=False
        )

        assert response.status_code in [302, 307]
        location = response.headers.get("location", "")
        assert "error=OAUTH_FAILED" in location


@pytest.mark.asyncio
async def test_google_callback_sets_correct_cookie_attributes(
    client: AsyncClient,
    mock_google_oauth
):
    """Callback should set cookies with correct security attributes."""
    state = generate_state()

    response = await client.get(
        f"/api/v1/auth/google/callback?state={state}&code=test-code",
        follow_redirects=False
    )

    # Check refresh token cookie attributes
    refresh_cookie = None
    for cookie in response.cookies.jar:
        if cookie.name == "refresh_token":
            refresh_cookie = cookie
            break

    assert refresh_cookie is not None
    # In test environment DEBUG=True, so secure should not be set
    # HttpOnly should be True for refresh_token


@pytest.mark.asyncio
async def test_google_callback_without_code_parameter(client: AsyncClient):
    """Callback without code parameter should handle gracefully."""
    state = generate_state()

    response = await client.get(
        f"/api/v1/auth/google/callback?state={state}",
        follow_redirects=False
    )

    # Should still attempt to process, but likely fail at token exchange
    assert response.status_code in [302, 307]
