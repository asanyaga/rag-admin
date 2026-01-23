from datetime import datetime, timedelta

from app.config import settings
from app.models import AuthProvider, RefreshToken, User
from app.repositories import RefreshTokenRepository, UserRepository
from app.services.exceptions import ConflictError
from app.utils.jwt import create_access_token, create_refresh_token, hash_refresh_token


class OAuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository
    ):
        self.user_repo = user_repo
        self.token_repo = token_repo

    async def get_or_create_google_user(
        self,
        google_id: str,
        email: str,
        full_name: str | None,
        ip_address: str,
        user_agent: str | None
    ) -> tuple[User, str, str, bool]:
        """
        Find existing user by google_id, or create new user.

        Returns: (user, access_token, refresh_token, is_new_user)

        Raises:
            ConflictError: If email exists with different auth provider
        """
        # 1. Check for existing user by google_id
        user = await self.user_repo.get_by_google_id(google_id)
        if user:
            # Existing Google user - generate tokens and return
            access_token = create_access_token(user.id, user.email)
            refresh_token_plain = create_refresh_token()
            refresh_token_hash = hash_refresh_token(refresh_token_plain)

            # Store refresh token
            refresh_token_record = RefreshToken(
                user_id=user.id,
                token_hash=refresh_token_hash,
                expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
                ip_address=ip_address,
                user_agent=user_agent
            )
            await self.token_repo.create(refresh_token_record)

            return (user, access_token, refresh_token_plain, False)

        # 2. Check if email already registered with password
        existing = await self.user_repo.get_by_email(email)
        if existing:
            raise ConflictError(
                "This email is registered with a password. Please sign in with email.",
                code="EMAIL_EXISTS_DIFFERENT_PROVIDER"
            )

        # 3. Create new user with Google auth
        user = User(
            email=email,
            full_name=full_name,
            auth_provider=AuthProvider.google,
            google_id=google_id
        )
        user = await self.user_repo.create(user)

        # 4. Generate tokens
        access_token = create_access_token(user.id, user.email)
        refresh_token_plain = create_refresh_token()
        refresh_token_hash = hash_refresh_token(refresh_token_plain)

        # Store refresh token
        refresh_token_record = RefreshToken(
            user_id=user.id,
            token_hash=refresh_token_hash,
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=ip_address,
            user_agent=user_agent
        )
        await self.token_repo.create(refresh_token_record)

        return (user, access_token, refresh_token_plain, True)
