# Claude Code Task: Google OAuth Backend Implementation

## Objective

Implement Google OAuth sign-up and sign-in on the backend: OAuth configuration, authorization redirect, callback handling, and user creation/lookup.

## Prerequisites

- Auth API complete (TASK-03)
- Auth UI complete (TASK-04)
- Google Cloud project with OAuth credentials (see Setup section)

## Reference Documents

Read these before starting:
- `CLAUDE.md` — Project conventions
- `docs/planning/02-TDD.md` — Google OAuth flow diagram, security considerations
- `docs/planning/03-API-SPEC.md` — OAuth endpoint contracts
- `docs/planning/01-PRD.md` — User stories US-3 and US-4, error messages

## Google Cloud Setup (Manual Step)

Before implementation, you need Google OAuth credentials:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use existing)
3. Enable "Google+ API" or "Google Identity" API
4. Go to Credentials → Create Credentials → OAuth Client ID
5. Application type: Web application
6. Authorized redirect URI: `http://localhost:8000/api/v1/auth/google/callback`
7. Copy Client ID and Client Secret to `.env`

```bash
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
```

## Tasks

### 1. OAuth Configuration

Create `backend/app/utils/oauth.py`:

```python
from authlib.integrations.starlette_client import OAuth

oauth = OAuth()

def setup_oauth(app_config):
    """
    Configure Google OAuth provider.
    Call this during app startup.
    """
    oauth.register(
        name='google',
        client_id=app_config.GOOGLE_CLIENT_ID,
        client_secret=app_config.GOOGLE_CLIENT_SECRET,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={
            'scope': 'openid email profile'
        }
    )
```

Update `backend/app/main.py`:
- Call `setup_oauth()` on startup
- Pass config settings

### 2. State Management for CSRF Protection

OAuth requires state parameter to prevent CSRF attacks.

Create `backend/app/utils/oauth_state.py`:

```python
import secrets
from datetime import datetime, timedelta

# In-memory store (replace with Redis in production)
_state_store: dict[str, datetime] = {}

def generate_state() -> str:
    """Generate random state, store with expiry."""
    state = secrets.token_urlsafe(32)
    _state_store[state] = datetime.utcnow() + timedelta(minutes=10)
    return state

def validate_state(state: str) -> bool:
    """Check state exists and not expired. Consume on use."""
    if state not in _state_store:
        return False
    expiry = _state_store.pop(state)
    return datetime.utcnow() < expiry

def cleanup_expired_states() -> None:
    """Remove expired states. Call periodically."""
    now = datetime.utcnow()
    expired = [s for s, exp in _state_store.items() if exp < now]
    for s in expired:
        _state_store.pop(s, None)
```

### 3. Google OAuth Service

create `backend/app/services/oauth_service.py`:

```python
class OAuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository
    ):
        ...

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
            ...

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
            auth_provider=AuthProvider.GOOGLE,
            google_id=google_id
        )
        user = await self.user_repo.create(user)
        
        # 4. Generate tokens
        ...

        return (user, access_token, refresh_token, True)
```

### 4. OAuth Router Endpoints

create `backend/app/routers/oauth.py`:

#### GET /auth/google/authorize

```python
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
```

#### GET /auth/google/callback

```python
@router.get("/google/callback")
async def google_callback(
    request: Request,
    state: str = Query(...),
    code: str = Query(None),
    error: str = Query(None),
    db: AsyncSession = Depends(get_db)
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
    oauth_service = OAuthService(...)
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
        secure=settings.is_production,
        samesite="strict",
        max_age=60 * 60 * 24 * 7,  # 7 days
        path="/api/v1/auth"
    )
    
    # Set access token as temporary cookie (frontend extracts and stores in memory)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=False,  # Frontend needs to read this
        secure=settings.is_production,
        samesite="strict",
        max_age=60,  # Short-lived, just for handoff
        path="/"
    )

    return response
```

### 5. Utility Functions

Add to `backend/app/utils/request.py`:

```python
def get_client_ip(request: Request) -> str:
    """Extract client IP, handling proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
```

### 6. Update Config

Ensure `backend/app/config.py` has:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"
    
    @property
    def is_production(self) -> bool:
        return not self.DEBUG
```

### 7. Write Tests

#### Unit Tests

`tests/services/test_oauth_service.py`:
- Create new user from Google account
- Find existing Google user (returns existing, doesn't create duplicate)
- Email collision (Google email matches existing password user)

`tests/utils/test_oauth_state.py`:
- State generation is unique
- Valid state passes validation
- Used state fails second validation (consumed)
- Expired state fails validation

#### Integration Tests

`tests/routers/test_oauth.py`:
- Authorize endpoint redirects to Google (check Location header format)
- Callback with invalid state returns error redirect
- Callback with valid flow creates user and redirects with cookies

Note: Full OAuth flow is hard to test without mocking. Mock the `oauth.google` methods:

```python
@pytest.fixture
def mock_google_oauth(mocker):
    mock_token = {
        'userinfo': {
            'sub': 'google-123',
            'email': 'test@gmail.com',
            'name': 'Test User'
        }
    }
    mocker.patch.object(
        oauth.google, 
        'authorize_access_token', 
        return_value=mock_token
    )
    return mock_token
```

## Verification Checklist

- [ ] OAuth configured with Authlib
- [ ] State generation and validation working
- [ ] GET /auth/google/authorize redirects to Google
- [ ] GET /auth/google/callback handles success flow
- [ ] GET /auth/google/callback handles error cases
- [ ] New Google users created with correct auth_provider
- [ ] Existing Google users found by google_id
- [ ] Email collision returns appropriate error
- [ ] Tokens set as cookies on success
- [ ] CSRF protection via state parameter working
- [ ] Unit tests pass
- [ ] Integration tests pass (with mocked Google)
- [ ] Manual test with real Google account works

## Do Not

- Implement frontend OAuth handling (separate task)
- Store Google access/refresh tokens (not needed for basic auth)
- Implement account linking (out of scope per PRD)
- Use sessions for state storage (in-memory is fine for learning; note production would use Redis)

## Error Codes Reference

| Code | When | Frontend Action |
|------|------|-----------------|
| `OAUTH_FAILED` | Google returned error or token exchange failed | Show "Sign in with Google failed" |
| `INVALID_STATE` | CSRF validation failed | Show "Something went wrong, please try again" |
| `EMAIL_EXISTS_DIFFERENT_PROVIDER` | Email registered with password | Show "This email uses password sign in" |

## Notes for Next Task

After this task, TASK-06 will implement:
- Frontend `/auth/callback` route
- Extract tokens from cookies/URL
- Handle OAuth error states
- Enable Google buttons on sign-in/sign-up pages