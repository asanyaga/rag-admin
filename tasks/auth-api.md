# Claude Code Task: Auth API Implementation

## Objective

Implement the authentication API layer: Pydantic schemas, auth utilities, service layer, and router endpoints for email/password sign-up and sign-in.

## Prerequisites

- Project scaffold complete 
- Database models and repositories complete
- PostgreSQL running with migrations applied

## Reference Documents

Read these before starting:
- `CLAUDE.md` — Project conventions
- `docs/planning/03-API-SPEC.md` — Endpoint contracts, request/response schemas
- `docs/planning/02-TDD.md` — Architecture, security requirements, flow diagrams

## Tasks

### 1. Pydantic Schemas

Create `backend/app/schemas/auth.py`:

```python
class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    password_confirm: str
    full_name: str | None = None

class SignInRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class AuthResponse(TokenResponse):
    user: UserResponse
```

Create `backend/app/schemas/user.py`:

```python
class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    auth_provider: AuthProvider
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### 2. Auth Utilities

Create `backend/app/utils/password.py`:
- `hash_password(password: str) -> str` — bcrypt hash with cost factor 12
- `verify_password(plain: str, hashed: str) -> bool`
- `validate_password_strength(password: str) -> tuple[bool, str | None]` — check requirements from PRD

Create `backend/app/utils/jwt.py`:
- `create_access_token(user_id: UUID, email: str) -> str`
- `decode_access_token(token: str) -> dict | None`
- `create_refresh_token() -> str` — generate random token
- `hash_refresh_token(token: str) -> str` — SHA-256 for database storage

Use settings from `app/config.py` for JWT_SECRET_KEY, expiry times, etc.

### 3. Auth Service

Create `backend/app/services/auth_service.py`:

```python
class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
        attempt_repo: LoginAttemptRepository
    ):
        ...

    async def sign_up(
        self, 
        request: SignUpRequest,
        ip_address: str,
        user_agent: str | None
    ) -> tuple[User, str, str]:
        """
        Returns (user, access_token, refresh_token).
        Raises:
        - ValueError: password validation fails
        - ConflictError: email exists
        """
        ...

    async def sign_in(
        self,
        request: SignInRequest,
        ip_address: str,
        user_agent: str | None
    ) -> tuple[User, str, str]:
        """
        Returns (user, access_token, refresh_token).
        Raises:
        - AuthenticationError: invalid credentials
        - AccountLockedError: too many failed attempts
        """
        ...

    async def refresh_tokens(
        self,
        refresh_token: str,
        ip_address: str,
        user_agent: str | None
    ) -> tuple[str, str]:
        """
        Returns (new_access_token, new_refresh_token).
        Implements token rotation.
        Raises:
        - AuthenticationError: token invalid/expired/revoked
        """
        ...

    async def sign_out(self, refresh_token: str) -> None:
        """Revoke the refresh token."""
        ...

    async def _check_account_locked(self, user_id: UUID) -> bool:
        """Check if account has too many recent failed attempts."""
        ...

    async def _record_attempt(
        self,
        user_id: UUID | None,
        email: str,
        ip_address: str,
        user_agent: str | None,
        success: bool,
        failure_reason: str | None = None
    ) -> None:
        ...
```

Create custom exceptions in `backend/app/services/exceptions.py`:
- `AuthenticationError`
- `AccountLockedError`
- `ConflictError`

### 4. Auth Dependencies

Create `backend/app/dependencies/auth.py`:

```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Decode JWT, fetch user from database.
    Raises HTTPException 401 if invalid.
    """
    ...

async def get_current_active_user(
    user: User = Depends(get_current_user)
) -> User:
    """
    Verify user.is_active is True.
    Raises HTTPException 403 if inactive.
    """
    ...
```

### 5. Auth Router

Create `backend/app/routers/auth.py`:

Implement endpoints per `docs/planning/03-API-SPEC.md`:

- `POST /auth/signup` — create account, return tokens
- `POST /auth/signin` — authenticate, return tokens  
- `POST /auth/signout` — revoke refresh token
- `POST /auth/refresh` — rotate tokens

Each endpoint should:
- Parse request body with Pydantic schema
- Extract IP address and User-Agent from request
- Call auth service
- Handle exceptions, return appropriate HTTP status
- Set refresh token as HTTP-only cookie

### 6. Users Router

Create `backend/app/routers/users.py`:

- `GET /users/me` — return current user (requires auth)

### 7. Wire Up Routers

Update `backend/app/main.py`:
- Import and include auth router at `/api/v1/auth`
- Import and include users router at `/api/v1/users`

### 8. Write Tests

#### Unit Tests

`tests/utils/test_password.py`:
- Password hashing and verification
- Password strength validation (valid and invalid cases)

`tests/utils/test_jwt.py`:
- Access token creation and decoding
- Expired token handling
- Invalid token handling

`tests/services/test_auth_service.py`:
- Sign up success
- Sign up with existing email
- Sign up with weak password
- Sign in success
- Sign in with wrong password
- Sign in with non-existent email
- Account lockout after failed attempts
- Token refresh success
- Token refresh with invalid token

#### Integration Tests

`tests/routers/test_auth.py`:
- Full sign up flow via API
- Full sign in flow via API
- Sign out invalidates token
- Token refresh returns new tokens
- Rate limiting (if implemented)

## Verification Checklist

- [ ] All Pydantic schemas created with proper validation
- [ ] Password hashing uses bcrypt with cost factor 12
- [ ] JWT tokens created and decoded correctly
- [ ] Auth service handles all flows per spec
- [ ] Custom exceptions defined and used
- [ ] Auth router returns correct status codes
- [ ] Refresh token set as HTTP-only cookie
- [ ] `GET /users/me` returns current user
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual test: sign up → sign in → get me → sign out works

## Do Not

- Implement Google OAuth (separate task)
- Implement rate limiting middleware (can add later)
- Add password reset flow (out of scope per PRD)
- Modify database models from TASK-02

## Notes for Next Task

After this task, TASK-04 will implement:
- Google OAuth flow
- OAuth callback handling
- Account collision handling (Google email vs existing email account)