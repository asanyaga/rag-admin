from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.repositories import RefreshTokenRepository, UserRepository
from app.services.exceptions import ConflictError
from app.services.oauth_service import OAuthService
from app.utils.oauth import oauth
from app.utils.oauth_state import generate_state, validate_state
from app.utils.request import get_client_ip

router = APIRouter(prefix="/auth", tags=["oauth"])


def get_oauth_service(db: AsyncSession = Depends(get_db)) -> OAuthService:
    """Dependency to create OAuthService with repositories."""
    user_repo = UserRepository(db)
    token_repo = RefreshTokenRepository(db)
    return OAuthService(user_repo, token_repo)


@router.get("/google/authorize")
async def google_authorize(request: Request):
    """
    Initiate Google OAuth flow.
    Redirects user to Google consent screen.
    """
    state = generate_state()
    redirect_uri = settings.GOOGLE_REDIRECT_URI

    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
        state=state
    )


@router.get("/google/callback")
async def google_callback(
    request: Request,
    state: str = Query(...),
    code: str = Query(None),
    error: str = Query(None),
    oauth_service: OAuthService = Depends(get_oauth_service)
):
    """
    Handle Google OAuth callback.
    Exchange code for tokens, get user info, create/find user.
    Redirect to frontend with tokens.
    """
    # 1. Check for OAuth error from Google
    if error:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?error=OAUTH_FAILED&message={error}"
        )

    # 2. Validate state (CSRF protection)
    if not validate_state(state):
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?error=INVALID_STATE"
        )

    # 3. Exchange code for tokens
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?error=OAUTH_FAILED"
        )

    # 4. Get user info from Google
    user_info = token.get('userinfo')
    if not user_info:
        # Fallback: fetch from userinfo endpoint
        user_info = await oauth.google.userinfo(token=token)

    google_id = user_info['sub']
    email = user_info['email']
    full_name = user_info.get('name')

    # 5. Get or create user
    try:
        user, access_token, refresh_token, is_new = await oauth_service.get_or_create_google_user(
            google_id=google_id,
            email=email,
            full_name=full_name,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent")
        )
    except ConflictError as e:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth/callback?error=EMAIL_EXISTS_DIFFERENT_PROVIDER"
        )

    # 6. Redirect to frontend with tokens
    response = RedirectResponse(
        url=f"{settings.FRONTEND_URL}/auth/callback?success=true"
    )

    # Set refresh token as HTTP-only cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=60 * 60 * 24 * 7,  # 7 days
        path="/api/v1/auth"
    )

    # Set access token as temporary cookie (frontend extracts and stores in memory)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=False,  # Frontend needs to read this
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=60,  # Short-lived, just for handoff
        path="/"
    )

    return response
