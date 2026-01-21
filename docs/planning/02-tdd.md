# Technical Design Document: Authentication Feature

## Overview

This document describes the technical architecture and implementation approach for the authentication feature supporting email/password and Google OAuth flows.

**Related Documents:** PRD (01-PRD.md), API Spec (03-API-SPEC.md), Database Schema (04-DATABASE-SCHEMA.md)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           Frontend (React)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  Sign In    │  │  Sign Up    │  │  Auth       │                 │
│  │  Page       │  │  Page       │  │  Context    │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
└─────────┼────────────────┼────────────────┼─────────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        API Layer (FastAPI)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  Auth       │  │  OAuth      │  │  User       │                 │
│  │  Router     │  │  Router     │  │  Router     │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
│         │                │                │                         │
│         ▼                ▼                ▼                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    Service Layer                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │   │
│  │  │  Auth       │  │  User       │  │  Token      │          │   │
│  │  │  Service    │  │  Service    │  │  Service    │          │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘          │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
          │                │                │
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Data Layer (PostgreSQL)                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  users      │  │  refresh_   │  │  login_     │                 │
│  │             │  │  tokens     │  │  attempts   │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Technology Decisions

### Authentication Strategy: JWT with Refresh Tokens

**Decision:** Use JWT access tokens (short-lived) with database-backed refresh tokens (long-lived).

**Rationale:**
- JWTs are stateless, reducing database load for authenticated requests
- Refresh tokens in database enable revocation and security controls
- Industry standard approach, well-supported by libraries
- Good learning opportunity for understanding token-based auth

**Alternatives Considered:**
- Session-based auth: Simpler but requires session store, less common in modern SPAs
- JWT-only (long-lived): Security risk, no revocation capability

### Password Hashing: bcrypt

**Decision:** Use bcrypt with cost factor 12.

**Rationale:**
- Purpose-built for password hashing (includes salt, resistant to rainbow tables)
- Cost factor 12 balances security with acceptable latency (~250ms)
- Well-supported in Python via `passlib` or `bcrypt` library

### OAuth Library: Authlib

**Decision:** Use Authlib for Google OAuth integration.

**Rationale:**
- Mature, well-maintained library
- Supports OAuth 2.0 and OIDC
- Good FastAPI integration
- Handles token exchange, validation, and refresh

### Database ORM: SQLAlchemy 2.0

**Decision:** Use SQLAlchemy with async support.

**Rationale:**
- Industry standard for Python
- Async support matches FastAPI's async nature
- Strong typing support with modern syntax

---

## Authentication Flows

### Email/Password Sign Up Flow

```
┌──────┐          ┌──────────┐          ┌──────────┐          ┌────────┐
│Client│          │  FastAPI │          │  Service │          │Database│
└──┬───┘          └────┬─────┘          └────┬─────┘          └───┬────┘
   │                   │                     │                    │
   │ POST /auth/signup │                     │                    │
   │ {email, password} │                     │                    │
   │──────────────────>│                     │                    │
   │                   │                     │                    │
   │                   │ validate_password() │                    │
   │                   │────────────────────>│                    │
   │                   │                     │                    │
   │                   │                     │ check email exists │
   │                   │                     │───────────────────>│
   │                   │                     │                    │
   │                   │                     │ hash password      │
   │                   │                     │ (bcrypt)           │
   │                   │                     │                    │
   │                   │                     │ INSERT user        │
   │                   │                     │───────────────────>│
   │                   │                     │                    │
   │                   │                     │ generate tokens    │
   │                   │                     │                    │
   │                   │                     │ INSERT refresh_token│
   │                   │                     │───────────────────>│
   │                   │                     │                    │
   │ 201 Created       │                     │                    │
   │ {access_token}    │                     │                    │
   │ Set-Cookie:       │                     │                    │
   │ refresh_token     │                     │                    │
   │<──────────────────│                     │                    │
```

### Email/Password Sign In Flow

```
┌──────┐          ┌──────────┐          ┌──────────┐          ┌────────┐
│Client│          │  FastAPI │          │  Service │          │Database│
└──┬───┘          └────┬─────┘          └────┬─────┘          └───┬────┘
   │                   │                     │                    │
   │ POST /auth/signin │                     │                    │
   │ {email, password} │                     │                    │
   │──────────────────>│                     │                    │
   │                   │                     │                    │
   │                   │ check_rate_limit()  │                    │
   │                   │────────────────────>│                    │
   │                   │                     │                    │
   │                   │                     │ get user by email  │
   │                   │                     │───────────────────>│
   │                   │                     │                    │
   │                   │                     │ check account lock │
   │                   │                     │───────────────────>│
   │                   │                     │                    │
   │                   │                     │ verify password    │
   │                   │                     │ (bcrypt)           │
   │                   │                     │                    │
   │                   │                     │ [if fail]          │
   │                   │                     │ record attempt     │
   │                   │                     │───────────────────>│
   │                   │                     │                    │
   │                   │                     │ [if success]       │
   │                   │                     │ clear attempts     │
   │                   │                     │ generate tokens    │
   │                   │                     │───────────────────>│
   │                   │                     │                    │
   │ 200 OK            │                     │                    │
   │ {access_token}    │                     │                    │
   │ Set-Cookie:       │                     │                    │
   │ refresh_token     │                     │                    │
   │<──────────────────│                     │                    │
```

### Google OAuth Flow

```
┌──────┐       ┌──────────┐       ┌────────┐       ┌────────┐
│Client│       │  FastAPI │       │ Google │       │Database│
└──┬───┘       └────┬─────┘       └───┬────┘       └───┬────┘
   │                │                 │                │
   │ GET /auth/google/authorize       │                │
   │───────────────>│                 │                │
   │                │                 │                │
   │ 302 Redirect   │                 │                │
   │ Location:      │                 │                │
   │ accounts.google.com/oauth        │                │
   │<───────────────│                 │                │
   │                │                 │                │
   │ User consents at Google          │                │
   │─────────────────────────────────>│                │
   │                │                 │                │
   │ 302 Redirect to callback         │                │
   │ ?code=AUTH_CODE│                 │                │
   │<─────────────────────────────────│                │
   │                │                 │                │
   │ GET /auth/google/callback?code=  │                │
   │───────────────>│                 │                │
   │                │                 │                │
   │                │ exchange code   │                │
   │                │ for tokens      │                │
   │                │────────────────>│                │
   │                │                 │                │
   │                │ get user info   │                │
   │                │────────────────>│                │
   │                │                 │                │
   │                │ find/create user│                │
   │                │────────────────────────────────>│
   │                │                 │                │
   │                │ generate tokens │                │
   │                │────────────────────────────────>│
   │                │                 │                │
   │ 302 Redirect   │                 │                │
   │ to frontend    │                 │                │
   │ Set-Cookie:    │                 │                │
   │ access_token,  │                 │                │
   │ refresh_token  │                 │                │
   │<───────────────│                 │                │
```

### Token Refresh Flow

```
┌──────┐          ┌──────────┐          ┌──────────┐          ┌────────┐
│Client│          │  FastAPI │          │  Service │          │Database│
└──┬───┘          └────┬─────┘          └────┬─────┘          └───┬────┘
   │                   │                     │                    │
   │ POST /auth/refresh│                     │                    │
   │ Cookie:           │                     │                    │
   │ refresh_token     │                     │                    │
   │──────────────────>│                     │                    │
   │                   │                     │                    │
   │                   │ validate_refresh()  │                    │
   │                   │────────────────────>│                    │
   │                   │                     │                    │
   │                   │                     │ find token in DB   │
   │                   │                     │───────────────────>│
   │                   │                     │                    │
   │                   │                     │ check not expired  │
   │                   │                     │ check not revoked  │
   │                   │                     │                    │
   │                   │                     │ rotate token       │
   │                   │                     │ (delete old,       │
   │                   │                     │  create new)       │
   │                   │                     │───────────────────>│
   │                   │                     │                    │
   │                   │                     │ generate new       │
   │                   │                     │ access token       │
   │                   │                     │                    │
   │ 200 OK            │                     │                    │
   │ {access_token}    │                     │                    │
   │ Set-Cookie:       │                     │                    │
   │ refresh_token     │                     │                    │
   │<──────────────────│                     │                    │
```

---

## Component Design

### Backend Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Settings and configuration
│   ├── database.py             # Database connection and session
│   │
│   ├── models/                 # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── refresh_token.py
│   │   └── login_attempt.py
│   │
│   ├── schemas/                # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── auth.py             # SignUpRequest, SignInRequest, TokenResponse
│   │   └── user.py             # UserCreate, UserResponse
│   │
│   ├── routers/                # API route handlers
│   │   ├── __init__.py
│   │   ├── auth.py             # /auth/* endpoints
│   │   └── users.py            # /users/* endpoints (me, etc.)
│   │
│   ├── services/               # Business logic
│   │   ├── __init__.py
│   │   ├── auth_service.py     # Authentication logic
│   │   ├── user_service.py     # User CRUD operations
│   │   └── token_service.py    # JWT generation/validation
│   │
│   ├── dependencies/           # FastAPI dependencies
│   │   ├── __init__.py
│   │   ├── auth.py             # get_current_user dependency
│   │   └── database.py         # get_db session dependency
│   │
│   └── utils/                  # Utilities
│       ├── __init__.py
│       ├── password.py         # Password hashing utilities
│       └── security.py         # Security helpers
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Pytest fixtures
│   ├── test_auth.py
│   └── test_users.py
│
├── alembic/                    # Database migrations
│   ├── versions/
│   └── env.py
│
├── requirements.txt
└── alembic.ini
```

### Frontend Structure

```
frontend/
├── src/
│   ├── main.tsx                # React entry point
│   ├── App.tsx                 # Root component with routing
│   │
│   ├── api/                    # API client
│   │   ├── client.ts           # Axios instance with interceptors
│   │   └── auth.ts             # Auth API calls
│   │
│   ├── contexts/               # React contexts
│   │   └── AuthContext.tsx     # Authentication state management
│   │
│   ├── hooks/                  # Custom hooks
│   │   └── useAuth.ts          # Auth context consumer hook
│   │
│   ├── pages/                  # Page components
│   │   ├── SignInPage.tsx
│   │   ├── SignUpPage.tsx
│   │   └── HomePage.tsx        # Protected page example
│   │
│   ├── components/             # Reusable components
│   │   ├── PrivateRoute.tsx    # Route protection wrapper
│   │   ├── SignInForm.tsx
│   │   ├── SignUpForm.tsx
│   │   └── GoogleAuthButton.tsx
│   │
│   └── types/                  # TypeScript types
│       └── auth.ts
│
├── package.json
└── vite.config.ts
```

---

## Security Implementation Details

### JWT Token Structure

**Access Token Payload:**
```json
{
  "sub": "user_uuid",
  "email": "user@example.com",
  "type": "access",
  "iat": 1234567890,
  "exp": 1234568790
}
```

**Refresh Token:**
- Stored in database, not as JWT
- Contains: token_hash, user_id, expires_at, created_at, revoked_at
- Client receives opaque token (UUID or random string)

### Password Validation

```python
# Password requirements
PASSWORD_MIN_LENGTH = 8
PASSWORD_PATTERN = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]).{8,}$'
```

### Rate Limiting Implementation

Using `slowapi` or custom middleware:

```python
# Rate limit configuration
SIGNIN_RATE_LIMIT = "10/minute"
SIGNUP_RATE_LIMIT = "5/minute"
```

### Account Lockout Logic

```python
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# Check before authentication
def is_account_locked(user_id: UUID) -> bool:
    recent_failures = get_recent_failures(user_id, minutes=LOCKOUT_DURATION_MINUTES)
    return len(recent_failures) >= MAX_FAILED_ATTEMPTS
```

---

## Environment Configuration

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname

# JWT
JWT_SECRET_KEY=<256-bit-random-string>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Google OAuth
GOOGLE_CLIENT_ID=<from-google-console>
GOOGLE_CLIENT_SECRET=<from-google-console>
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback

# Application
FRONTEND_URL=http://localhost:5173
ALLOWED_ORIGINS=http://localhost:5173
```

---

## Error Handling Strategy

### Backend Error Responses

All errors return consistent JSON structure:

```json
{
  "detail": "Human-readable error message",
  "code": "ERROR_CODE",
  "field": "field_name"  // Optional, for validation errors
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `INVALID_CREDENTIALS` | 401 | Email or password incorrect |
| `ACCOUNT_LOCKED` | 403 | Too many failed attempts |
| `EMAIL_EXISTS` | 409 | Email already registered |
| `INVALID_TOKEN` | 401 | Token expired or invalid |
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `OAUTH_ERROR` | 400 | OAuth flow failed |

---

## Testing Strategy

### Unit Tests
- Password hashing/verification
- JWT generation/validation
- Password policy validation
- Service layer business logic

### Integration Tests
- Full sign-up flow
- Full sign-in flow
- Token refresh flow
- Account lockout behavior
- Google OAuth flow (mocked)

### Test Data

```python
# Test user fixtures
TEST_USER_EMAIL = "test@example.com"
TEST_USER_PASSWORD = "TestPass123!"
```

---

## Dependencies

### Backend (Python)

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
sqlalchemy>=2.0.0
asyncpg>=0.29.0
alembic>=1.13.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
authlib>=1.3.0
httpx>=0.26.0
slowapi>=0.1.9
python-multipart>=0.0.6
```

### Frontend (Node.js)

```
react>=18.0.0
react-router-dom>=6.0.0
axios>=1.6.0
@tanstack/react-query>=5.0.0  # Optional, for data fetching
```

---

## Deployment Considerations

While not in scope for initial development, these notes support future deployment:

1. **HTTPS Required:** All auth endpoints must use HTTPS in production
2. **Cookie Settings:** Set `Secure=true`, `SameSite=Strict` in production
3. **CORS:** Restrict to specific frontend domain
4. **Secrets Management:** Use environment variables or secrets manager
5. **Database:** Use connection pooling, SSL connection