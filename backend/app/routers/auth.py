from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.repositories import LoginAttemptRepository, ProjectRepository, RefreshTokenRepository, UserRepository
from app.schemas import AuthResponse, SignInRequest, SignUpRequest, TokenResponse, UserResponse
from app.services.auth_service import AuthService
from app.services.exceptions import AccountLockedError, AuthenticationError, ConflictError

# Import tracing for manual instrumentation (hybrid approach)
from app.observability import get_tracer
from opentelemetry.trace import Status, StatusCode

router = APIRouter(prefix="/auth", tags=["auth"])

# Get tracer for creating custom spans in this module
tracer = get_tracer(__name__)


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """Dependency to create AuthService with repositories."""
    user_repo = UserRepository(db)
    token_repo = RefreshTokenRepository(db)
    attempt_repo = LoginAttemptRepository(db)
    project_repo = ProjectRepository(db)
    return AuthService(user_repo, token_repo, attempt_repo, project_repo)


def get_client_info(request: Request) -> tuple[str, str | None]:
    """Extract IP address and User-Agent from request."""
    # Get IP address from X-Forwarded-For header or direct client
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()
    else:
        ip_address = request.client.host if request.client else "unknown"

    user_agent = request.headers.get("User-Agent")
    return ip_address, user_agent


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def sign_up(
    request_data: SignUpRequest,
    response: Response,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Create a new user account with email/password."""
    ip_address, user_agent = get_client_info(request)

    try:
        user, access_token, refresh_token = await auth_service.sign_up(
            request_data,
            ip_address,
            user_agent
        )

        # Set refresh token as HTTP-only cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=not settings.DEBUG,  # HTTPS only in production
            samesite="lax",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        )

        return AuthResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.model_validate(user)
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )


@router.post("/signin", response_model=AuthResponse)
async def sign_in(
    request_data: SignInRequest,
    response: Response,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Sign in with email/password.

    This endpoint demonstrates hybrid instrumentation:
    - Auto-instrumentation: FastAPI creates span for HTTP request
    - Manual instrumentation: Custom spans for business logic below
    """
    # Create a custom span for authentication flow
    # This span will be a child of the auto-generated HTTP span
    with tracer.start_as_current_span("authenticate_user") as auth_span:
        # Add context attributes for debugging and filtering
        auth_span.set_attribute("auth.email", request_data.email)
        auth_span.set_attribute("auth.method", "email_password")

        ip_address, user_agent = get_client_info(request)
        auth_span.set_attribute("client.ip", ip_address)
        if user_agent:
            auth_span.set_attribute("client.user_agent", user_agent[:100])  # Truncate for cardinality

        try:
            # The auth service call will create child spans for:
            # - Database query (via SQLAlchemy auto-instrumentation)
            # - Password verification (if we instrument that in the future)
            user, access_token, refresh_token = await auth_service.sign_in(
                request_data,
                ip_address,
                user_agent
            )

            # Record successful authentication
            auth_span.set_attribute("auth.success", True)
            auth_span.set_attribute("user.id", user.id)
            auth_span.set_status(Status(StatusCode.OK))

            # Set refresh token as HTTP-only cookie
            response.set_cookie(
                key="refresh_token",
                value=refresh_token,
                httponly=True,
                secure=not settings.DEBUG,
                samesite="lax",
                max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
            )

            return AuthResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user=UserResponse.model_validate(user)
            )

        except AuthenticationError as e:
            # Record authentication failure with details
            auth_span.set_attribute("auth.success", False)
            auth_span.set_attribute("auth.error", "invalid_credentials")
            auth_span.set_status(Status(StatusCode.ERROR, "Authentication failed"))

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
        except AccountLockedError as e:
            # Record account lockout
            auth_span.set_attribute("auth.success", False)
            auth_span.set_attribute("auth.error", "account_locked")
            auth_span.set_status(Status(StatusCode.ERROR, "Account locked"))

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(e)
            )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    request: Request,
    refresh_token: str = Cookie(None),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Refresh access and refresh tokens."""
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found"
        )

    ip_address, user_agent = get_client_info(request)

    try:
        new_access_token, new_refresh_token = await auth_service.refresh_tokens(
            refresh_token,
            ip_address,
            user_agent
        )

        # Set new refresh token as HTTP-only cookie
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
        )

        return TokenResponse(
            access_token=new_access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/signout", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(
    response: Response,
    refresh_token: str = Cookie(None),
    auth_service: AuthService = Depends(get_auth_service)
):
    """Sign out by revoking refresh token."""
    if refresh_token:
        await auth_service.sign_out(refresh_token)

    # Clear refresh token cookie
    response.delete_cookie(key="refresh_token")

    return None
