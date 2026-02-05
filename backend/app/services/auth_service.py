from datetime import datetime, timedelta
from uuid import UUID

from app.config import settings
from app.models import AuthProvider, LoginAttempt, RefreshToken, User
from app.repositories import LoginAttemptRepository, ProjectRepository, RefreshTokenRepository, UserRepository
from app.schemas import SignInRequest, SignUpRequest
from app.schemas.project import ProjectCreate
from app.services.exceptions import AccountLockedError, AuthenticationError, ConflictError
from app.utils.jwt import create_access_token, create_refresh_token, hash_refresh_token
from app.utils.password import hash_password, validate_password_strength, verify_password


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
        attempt_repo: LoginAttemptRepository,
        project_repo: ProjectRepository
    ):
        self.user_repo = user_repo
        self.token_repo = token_repo
        self.attempt_repo = attempt_repo
        self.project_repo = project_repo

    async def sign_up(
        self,
        request: SignUpRequest,
        ip_address: str,
        user_agent: str | None
    ) -> tuple[User, str, str]:
        """
        Register a new user with email/password.

        Returns (user, access_token, refresh_token).

        Raises:
        - ValueError: password validation fails
        - ConflictError: email exists
        """
        # Validate password strength
        is_valid, error_message = validate_password_strength(request.password)
        if not is_valid:
            raise ValueError(error_message)

        # Check if email already exists
        existing_user = await self.user_repo.get_by_email(request.email)
        if existing_user:
            raise ConflictError("Email already registered")

        # Create user
        user = User(
            email=request.email,
            full_name=request.full_name,
            password_hash=hash_password(request.password),
            auth_provider=AuthProvider.email
        )
        user = await self.user_repo.create(user)

        # Create default project
        default_project = await self.project_repo.create(
            user_id=user.id,
            data=ProjectCreate(
                name="My Documents",
                description="Your personal document collection",
                tags=[]
            )
        )
        await self.project_repo.set_as_default(user.id, default_project.id)

        # Generate tokens
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

        return user, access_token, refresh_token_plain

    async def sign_in(
        self,
        request: SignInRequest,
        ip_address: str,
        user_agent: str | None
    ) -> tuple[User, str, str]:
        """
        Authenticate user with email/password.

        Returns (user, access_token, refresh_token).

        Raises:
        - AuthenticationError: invalid credentials
        - AccountLockedError: too many failed attempts
        """
        # Get user by email
        user = await self.user_repo.get_by_email(request.email)

        # Check if user exists
        if not user:
            await self._record_attempt(
                user_id=None,
                email=request.email,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                failure_reason="user_not_found"
            )
            raise AuthenticationError("Invalid email or password")

        # Check if account is locked
        if await self._check_account_locked(user.id):
            await self._record_attempt(
                user_id=user.id,
                email=request.email,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                failure_reason="account_locked"
            )
            raise AccountLockedError("Account temporarily locked due to too many failed attempts")

        # Check if account is active
        if not user.is_active:
            await self._record_attempt(
                user_id=user.id,
                email=request.email,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                failure_reason="account_inactive"
            )
            raise AuthenticationError("Account is inactive")

        # Check if user is email auth provider
        if user.auth_provider != AuthProvider.email:
            await self._record_attempt(
                user_id=user.id,
                email=request.email,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                failure_reason="wrong_provider"
            )
            raise AuthenticationError(f"Please sign in with {user.auth_provider.value}")

        # Verify password
        if not verify_password(request.password, user.password_hash):
            await self._record_attempt(
                user_id=user.id,
                email=request.email,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                failure_reason="invalid_password"
            )
            raise AuthenticationError("Invalid email or password")

        # Record successful attempt
        await self._record_attempt(
            user_id=user.id,
            email=request.email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True
        )

        # Generate tokens
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

        return user, access_token, refresh_token_plain

    async def refresh_tokens(
        self,
        refresh_token: str,
        ip_address: str,
        user_agent: str | None
    ) -> tuple[str, str]:
        """
        Refresh access and refresh tokens (token rotation).

        Returns (new_access_token, new_refresh_token).

        Raises:
        - AuthenticationError: token invalid/expired/revoked
        """
        # Hash the incoming token
        token_hash = hash_refresh_token(refresh_token)

        # Get valid refresh token from database
        token_record = await self.token_repo.get_valid_by_token_hash(token_hash)
        if not token_record:
            raise AuthenticationError("Invalid or expired refresh token")

        # Get user
        user = await self.user_repo.get_by_id(token_record.user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")

        # Revoke old token
        await self.token_repo.revoke(token_record)

        # Generate new tokens
        new_access_token = create_access_token(user.id, user.email)
        new_refresh_token_plain = create_refresh_token()
        new_refresh_token_hash = hash_refresh_token(new_refresh_token_plain)

        # Store new refresh token
        new_refresh_token_record = RefreshToken(
            user_id=user.id,
            token_hash=new_refresh_token_hash,
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=ip_address,
            user_agent=user_agent
        )
        await self.token_repo.create(new_refresh_token_record)

        return new_access_token, new_refresh_token_plain

    async def sign_out(self, refresh_token: str) -> None:
        """Revoke the refresh token."""
        token_hash = hash_refresh_token(refresh_token)
        token_record = await self.token_repo.get_by_token_hash(token_hash)

        if token_record and token_record.revoked_at is None:
            await self.token_repo.revoke(token_record)

    async def _check_account_locked(self, user_id: UUID) -> bool:
        """Check if account has too many recent failed attempts (5 in 15 minutes)."""
        failed_attempts = await self.attempt_repo.count_recent_failures(user_id, minutes=15)
        return failed_attempts >= 5

    async def _record_attempt(
        self,
        user_id: UUID | None,
        email: str,
        ip_address: str,
        user_agent: str | None,
        success: bool,
        failure_reason: str | None = None
    ) -> None:
        """Record a login attempt."""
        attempt = LoginAttempt(
            user_id=user_id,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            failure_reason=failure_reason
        )
        await self.attempt_repo.create(attempt)
