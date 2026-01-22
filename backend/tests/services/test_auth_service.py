from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthProvider, LoginAttempt, User
from app.repositories import LoginAttemptRepository, RefreshTokenRepository, UserRepository
from app.schemas import SignInRequest, SignUpRequest
from app.services.auth_service import AuthService
from app.services.exceptions import AccountLockedError, AuthenticationError, ConflictError
from app.utils.jwt import hash_refresh_token


@pytest.fixture
def auth_service(test_db: AsyncSession) -> AuthService:
    user_repo = UserRepository(test_db)
    token_repo = RefreshTokenRepository(test_db)
    attempt_repo = LoginAttemptRepository(test_db)
    return AuthService(user_repo, token_repo, attempt_repo)


@pytest.mark.asyncio
async def test_sign_up_success(auth_service: AuthService):
    request = SignUpRequest(
        email="newuser@example.com",
        password="ValidPass123!",
        password_confirm="ValidPass123!",
        full_name="New User"
    )

    user, access_token, refresh_token = await auth_service.sign_up(
        request,
        ip_address="127.0.0.1",
        user_agent="Test Browser"
    )

    assert user.email == "newuser@example.com"
    assert user.full_name == "New User"
    assert user.auth_provider == AuthProvider.email
    assert user.password_hash is not None
    assert user.password_hash != "ValidPass123!"
    assert len(access_token) > 0
    assert len(refresh_token) > 0


@pytest.mark.asyncio
async def test_sign_up_with_existing_email(auth_service: AuthService, test_db: AsyncSession):
    # Create existing user
    user_repo = UserRepository(test_db)
    existing_user = User(
        email="existing@example.com",
        password_hash="hash",
        auth_provider=AuthProvider.email
    )
    await user_repo.create(existing_user)

    # Try to sign up with same email
    request = SignUpRequest(
        email="existing@example.com",
        password="ValidPass123!",
        password_confirm="ValidPass123!",
        full_name="Duplicate User"
    )

    with pytest.raises(ConflictError, match="Email already registered"):
        await auth_service.sign_up(
            request,
            ip_address="127.0.0.1",
            user_agent="Test Browser"
        )


@pytest.mark.asyncio
async def test_sign_up_with_weak_password(auth_service: AuthService):
    request = SignUpRequest(
        email="newuser@example.com",
        password="weak",
        password_confirm="weak"
    )

    with pytest.raises(ValueError):
        await auth_service.sign_up(
            request,
            ip_address="127.0.0.1",
            user_agent="Test Browser"
        )


@pytest.mark.asyncio
async def test_sign_in_success(auth_service: AuthService):
    # Sign up first
    signup_request = SignUpRequest(
        email="signin@example.com",
        password="ValidPass123!",
        password_confirm="ValidPass123!",
        full_name="Sign In User"
    )
    await auth_service.sign_up(
        signup_request,
        ip_address="127.0.0.1",
        user_agent="Test Browser"
    )

    # Sign in
    signin_request = SignInRequest(
        email="signin@example.com",
        password="ValidPass123!"
    )
    user, access_token, refresh_token = await auth_service.sign_in(
        signin_request,
        ip_address="127.0.0.1",
        user_agent="Test Browser"
    )

    assert user.email == "signin@example.com"
    assert len(access_token) > 0
    assert len(refresh_token) > 0


@pytest.mark.asyncio
async def test_sign_in_with_wrong_password(auth_service: AuthService, test_db: AsyncSession):
    # Create user directly
    user_repo = UserRepository(test_db)
    from app.utils.password import hash_password
    user = User(
        email="wrongpass@example.com",
        password_hash=hash_password("CorrectPass123!"),
        auth_provider=AuthProvider.email
    )
    await user_repo.create(user)

    # Try to sign in with wrong password
    signin_request = SignInRequest(
        email="wrongpass@example.com",
        password="WrongPass123!"
    )

    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        await auth_service.sign_in(
            signin_request,
            ip_address="127.0.0.1",
            user_agent="Test Browser"
        )


@pytest.mark.asyncio
async def test_sign_in_with_non_existent_email(auth_service: AuthService):
    signin_request = SignInRequest(
        email="nonexistent@example.com",
        password="AnyPass123!"
    )

    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        await auth_service.sign_in(
            signin_request,
            ip_address="127.0.0.1",
            user_agent="Test Browser"
        )


@pytest.mark.asyncio
async def test_account_lockout_after_failed_attempts(auth_service: AuthService, test_db: AsyncSession):
    # Create user
    user_repo = UserRepository(test_db)
    attempt_repo = LoginAttemptRepository(test_db)
    from app.utils.password import hash_password
    user = User(
        email="lockout@example.com",
        password_hash=hash_password("CorrectPass123!"),
        auth_provider=AuthProvider.email
    )
    user = await user_repo.create(user)

    # Create 5 failed attempts within last 15 minutes
    for i in range(5):
        attempt = LoginAttempt(
            user_id=user.id,
            email=user.email,
            ip_address="127.0.0.1",
            success=False,
            attempted_at=datetime.utcnow() - timedelta(minutes=i)
        )
        await attempt_repo.create(attempt)

    # Try to sign in
    signin_request = SignInRequest(
        email="lockout@example.com",
        password="CorrectPass123!"
    )

    with pytest.raises(AccountLockedError, match="Account temporarily locked"):
        await auth_service.sign_in(
            signin_request,
            ip_address="127.0.0.1",
            user_agent="Test Browser"
        )


@pytest.mark.asyncio
async def test_token_refresh_success(auth_service: AuthService):
    # Sign up first
    signup_request = SignUpRequest(
        email="refresh@example.com",
        password="ValidPass123!",
        password_confirm="ValidPass123!",
        full_name="Refresh User"
    )
    _, _, initial_refresh_token = await auth_service.sign_up(
        signup_request,
        ip_address="127.0.0.1",
        user_agent="Test Browser"
    )

    # Refresh tokens
    new_access_token, new_refresh_token = await auth_service.refresh_tokens(
        initial_refresh_token,
        ip_address="127.0.0.1",
        user_agent="Test Browser"
    )

    assert len(new_access_token) > 0
    assert len(new_refresh_token) > 0
    assert new_refresh_token != initial_refresh_token


@pytest.mark.asyncio
async def test_token_refresh_with_invalid_token(auth_service: AuthService):
    with pytest.raises(AuthenticationError, match="Invalid or expired refresh token"):
        await auth_service.refresh_tokens(
            "invalid-token",
            ip_address="127.0.0.1",
            user_agent="Test Browser"
        )


@pytest.mark.asyncio
async def test_token_refresh_revokes_old_token(auth_service: AuthService, test_db: AsyncSession):
    # Sign up first
    signup_request = SignUpRequest(
        email="revoke@example.com",
        password="ValidPass123!",
        password_confirm="ValidPass123!",
        full_name="Revoke User"
    )
    _, _, initial_refresh_token = await auth_service.sign_up(
        signup_request,
        ip_address="127.0.0.1",
        user_agent="Test Browser"
    )

    # Refresh tokens
    await auth_service.refresh_tokens(
        initial_refresh_token,
        ip_address="127.0.0.1",
        user_agent="Test Browser"
    )

    # Try to use old token again
    with pytest.raises(AuthenticationError):
        await auth_service.refresh_tokens(
            initial_refresh_token,
            ip_address="127.0.0.1",
            user_agent="Test Browser"
        )


@pytest.mark.asyncio
async def test_sign_out(auth_service: AuthService, test_db: AsyncSession):
    # Sign up first
    signup_request = SignUpRequest(
        email="signout@example.com",
        password="ValidPass123!",
        password_confirm="ValidPass123!",
        full_name="Sign Out User"
    )
    _, _, refresh_token = await auth_service.sign_up(
        signup_request,
        ip_address="127.0.0.1",
        user_agent="Test Browser"
    )

    # Sign out
    await auth_service.sign_out(refresh_token)

    # Try to refresh with signed out token
    with pytest.raises(AuthenticationError):
        await auth_service.refresh_tokens(
            refresh_token,
            ip_address="127.0.0.1",
            user_agent="Test Browser"
        )
