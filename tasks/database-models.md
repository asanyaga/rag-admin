# Claude Code Task: Database Models and Migrations

## Objective

Implement the database models and create the initial migration for the authentication feature. This builds on the project scaffold.

## Prerequisites

- Project scaffold complete
- PostgreSQL running and accessible
- `backend/.env` configured with DATABASE_URL

## Reference Documents

Read these before starting:
- `CLAUDE.md` — Project conventions
- `docs/planning/04-DATABASE-SCHEMA.md` — Complete schema specification

## Tasks

### 1. Create SQLAlchemy Models

#### app/models/user.py

Implement the User model per the schema doc:
- UUID primary key (use `gen_random_uuid()` default)
- email (unique, indexed)
- full_name (nullable)
- password_hash (nullable, for OAuth users)
- auth_provider (enum: 'email', 'google')
- google_id (nullable, unique, indexed)
- is_active (boolean, default True)
- created_at, updated_at (timezone-aware)

Include the check constraint ensuring password_hash exists for email auth and google_id exists for google auth.

#### app/models/refresh_token.py

Implement RefreshToken model:
- UUID primary key
- user_id (foreign key to users, cascade delete)
- token_hash (unique, indexed)
- expires_at (indexed)
- created_at
- revoked_at (nullable)
- user_agent (nullable)
- ip_address (nullable, use INET type)

Add an `is_valid` property that checks not revoked and not expired.

#### app/models/login_attempt.py

Implement LoginAttempt model:
- UUID primary key
- user_id (foreign key, nullable, set null on delete)
- email (indexed)
- ip_address (INET type)
- user_agent (nullable)
- success (boolean)
- failure_reason (nullable)
- attempted_at (indexed)

#### app/models/__init__.py

Export all models and the AuthProvider enum:
```python
from app.models.user import User, AuthProvider
from app.models.refresh_token import RefreshToken
from app.models.login_attempt import LoginAttempt

__all__ = ["User", "AuthProvider", "RefreshToken", "LoginAttempt"]
```

### 2. Update Alembic Configuration

#### alembic/env.py

Update to import all models:
```python
from app.models import User, RefreshToken, LoginAttempt
```

This ensures Alembic detects the models for autogenerate.

### 3. Create Initial Migration

Run:
```bash
alembic revision --autogenerate -m "initial_auth_schema"
```

Review the generated migration file. Verify it includes:
- auth_provider_enum type creation
- All three tables with correct columns
- All indexes
- Foreign key constraints
- Check constraint on users table

If autogenerate misses the check constraint, add it manually:
```python
op.create_check_constraint(
    'users_auth_provider_check',
    'users',
    "(auth_provider = 'email' AND password_hash IS NOT NULL) OR "
    "(auth_provider = 'google' AND google_id IS NOT NULL)"
)
```

### 4. Create Repository Layer

#### app/repositories/user_repository.py

```python
class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        ...

    async def get_by_email(self, email: str) -> User | None:
        ...

    async def get_by_google_id(self, google_id: str) -> User | None:
        ...

    async def create(self, user: User) -> User:
        ...

    async def update(self, user: User) -> User:
        ...
```

#### app/repositories/refresh_token_repository.py

```python
class RefreshTokenRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        ...

    async def get_valid_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        """Get token only if not expired and not revoked."""
        ...

    async def create(self, token: RefreshToken) -> RefreshToken:
        ...

    async def revoke(self, token: RefreshToken) -> RefreshToken:
        """Set revoked_at to now."""
        ...

    async def revoke_all_for_user(self, user_id: UUID) -> int:
        """Revoke all tokens for user, return count revoked."""
        ...

    async def delete_expired(self, older_than_days: int = 7) -> int:
        """Delete tokens expired more than N days ago."""
        ...
```

#### app/repositories/login_attempt_repository.py

```python
class LoginAttemptRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, attempt: LoginAttempt) -> LoginAttempt:
        ...

    async def count_recent_failures(
        self, 
        user_id: UUID, 
        minutes: int = 15
    ) -> int:
        """Count failed attempts in last N minutes."""
        ...

    async def delete_old(self, older_than_days: int = 90) -> int:
        """Delete attempts older than N days."""
        ...
```

#### app/repositories/__init__.py

Export all repositories.

### 5. Write Tests

#### tests/repositories/test_user_repository.py

Test:
- Create user with email auth
- Create user with Google auth
- Get by email (found and not found)
- Get by Google ID (found and not found)
- Email uniqueness constraint
- Google ID uniqueness constraint

#### tests/repositories/test_refresh_token_repository.py

Test:
- Create token
- Get valid token
- Get expired token returns None
- Get revoked token returns None
- Revoke token
- Revoke all for user

#### tests/repositories/test_login_attempt_repository.py

Test:
- Create attempt
- Count recent failures (with and without failures)
- Count doesn't include old failures
- Count doesn't include successes

### 6. Verify Migration

Run the migration against a test database:
```bash
alembic upgrade head
```

Verify tables exist:
```bash
psql -h localhost -U postgres -d rag_admin -c "\dt"
```

Expected output shows: users, refresh_tokens, login_attempts, alembic_version

## Verification Checklist

- [ ] All three models created with correct fields and types
- [ ] AuthProvider enum defined and used
- [ ] Relationships between models work correctly
- [ ] Migration file generated and reviewed
- [ ] Migration applies cleanly to empty database
- [ ] All repository methods implemented
- [ ] Repository tests pass
- [ ] No type errors (run `mypy app/` if configured)

## Do Not

- Implement services or routers (next task)
- Add authentication logic
- Create Pydantic schemas (next task)
- Modify the config or database setup from TASK-01

## Notes for Next Task

After this task, TASK-03 will implement:
- Pydantic schemas for API requests/responses
- Auth utilities (password hashing, JWT)
- Auth service with business logic
- Auth router with endpoints