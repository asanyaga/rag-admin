# Database Schema: Authentication Feature

## Overview

This document defines the PostgreSQL database schema for the authentication feature. The schema supports email/password authentication, Google OAuth, session management via refresh tokens, and security features like login attempt tracking.

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                          users                              │
├─────────────────────────────────────────────────────────────┤
│ PK │ id              │ UUID                                 │
│    │ email           │ VARCHAR(255)     │ UNIQUE, NOT NULL  │
│    │ password_hash   │ VARCHAR(255)     │ NULL (OAuth)      │
│    │ full_name       │ VARCHAR(100)     │ NULL              │
│    │ auth_provider   │ auth_provider_enum│ NOT NULL         │
│    │ google_id       │ VARCHAR(255)     │ NULL, UNIQUE      │
│    │ is_active       │ BOOLEAN          │ DEFAULT true      │
│    │ created_at      │ TIMESTAMPTZ      │ NOT NULL          │
│    │ updated_at      │ TIMESTAMPTZ      │ NOT NULL          │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 1:N
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      refresh_tokens                         │
├─────────────────────────────────────────────────────────────┤
│ PK │ id              │ UUID                                 │
│ FK │ user_id         │ UUID             │ NOT NULL          │
│    │ token_hash      │ VARCHAR(255)     │ UNIQUE, NOT NULL  │
│    │ expires_at      │ TIMESTAMPTZ      │ NOT NULL          │
│    │ created_at      │ TIMESTAMPTZ      │ NOT NULL          │
│    │ revoked_at      │ TIMESTAMPTZ      │ NULL              │
│    │ user_agent      │ VARCHAR(500)     │ NULL              │
│    │ ip_address      │ INET             │ NULL              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      login_attempts                         │
├─────────────────────────────────────────────────────────────┤
│ PK │ id              │ UUID                                 │
│ FK │ user_id         │ UUID             │ NULL              │
│    │ email           │ VARCHAR(255)     │ NOT NULL          │
│    │ ip_address      │ INET             │ NOT NULL          │
│    │ success         │ BOOLEAN          │ NOT NULL          │
│    │ failure_reason  │ VARCHAR(50)      │ NULL              │
│    │ attempted_at    │ TIMESTAMPTZ      │ NOT NULL          │
│    │ user_agent      │ VARCHAR(500)     │ NULL              │
└─────────────────────────────────────────────────────────────┘
```

---

## Table Definitions

### users

Stores user account information. Supports both email/password and OAuth users.

```sql
-- Enum for authentication provider
CREATE TYPE auth_provider_enum AS ENUM ('email', 'google');

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Core identity
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    
    -- Authentication
    password_hash VARCHAR(255),  -- NULL for OAuth-only users
    auth_provider auth_provider_enum NOT NULL DEFAULT 'email',
    google_id VARCHAR(255),      -- Google's unique user ID
    
    -- Account status
    is_active BOOLEAN NOT NULL DEFAULT true,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT users_email_unique UNIQUE (email),
    CONSTRAINT users_google_id_unique UNIQUE (google_id),
    
    -- Ensure password exists for email auth, google_id exists for google auth
    CONSTRAINT users_auth_provider_check CHECK (
        (auth_provider = 'email' AND password_hash IS NOT NULL) OR
        (auth_provider = 'google' AND google_id IS NOT NULL)
    )
);

-- Indexes
CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_google_id ON users (google_id) WHERE google_id IS NOT NULL;
CREATE INDEX idx_users_created_at ON users (created_at);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Column Notes:**

| Column | Description |
|--------|-------------|
| id | Primary key, UUID v4 |
| email | User's email address, used for login |
| full_name | Display name, optional |
| password_hash | bcrypt hash, NULL for OAuth users |
| auth_provider | How user authenticates (email or google) |
| google_id | Google's unique identifier for OAuth users |
| is_active | Soft delete / account disable flag |
| created_at | Account creation timestamp |
| updated_at | Last modification timestamp |

---

### refresh_tokens

Stores refresh tokens for session management. Tokens are hashed for security.

```sql
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Relationship
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Token data (store hash, not plain token)
    token_hash VARCHAR(255) NOT NULL,
    
    -- Lifecycle
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,  -- NULL = active, set = revoked
    
    -- Metadata for security/debugging
    user_agent VARCHAR(500),
    ip_address INET,
    
    -- Constraints
    CONSTRAINT refresh_tokens_hash_unique UNIQUE (token_hash)
);

-- Indexes
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens (token_hash);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens (expires_at);

-- Index for cleanup queries (find expired/revoked tokens)
CREATE INDEX idx_refresh_tokens_cleanup ON refresh_tokens (expires_at) 
    WHERE revoked_at IS NULL;
```

**Column Notes:**

| Column | Description |
|--------|-------------|
| id | Primary key, UUID v4 |
| user_id | Foreign key to users table |
| token_hash | SHA-256 hash of the actual token |
| expires_at | When token expires (7 days from creation) |
| created_at | When token was issued |
| revoked_at | When token was revoked (logout, rotation) |
| user_agent | Browser/client info for security review |
| ip_address | Client IP for security review |

**Token Rotation Strategy:**

When a refresh token is used:
1. Validate token exists and is not expired/revoked
2. Mark current token as revoked (set revoked_at)
3. Create new refresh token
4. Return new token pair to client

This prevents token reuse and enables detection of token theft.

---

### login_attempts

Tracks authentication attempts for rate limiting and security monitoring.

```sql
CREATE TABLE login_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Who attempted (user_id NULL if user doesn't exist)
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    email VARCHAR(255) NOT NULL,
    
    -- Request info
    ip_address INET NOT NULL,
    user_agent VARCHAR(500),
    
    -- Result
    success BOOLEAN NOT NULL,
    failure_reason VARCHAR(50),  -- 'invalid_password', 'account_locked', etc.
    
    -- Timestamp
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_login_attempts_user_id ON login_attempts (user_id) 
    WHERE user_id IS NOT NULL;
CREATE INDEX idx_login_attempts_email ON login_attempts (email);
CREATE INDEX idx_login_attempts_ip ON login_attempts (ip_address);
CREATE INDEX idx_login_attempts_attempted_at ON login_attempts (attempted_at);

-- Composite index for lockout check query
CREATE INDEX idx_login_attempts_lockout_check ON login_attempts (user_id, attempted_at, success)
    WHERE success = false;
```

**Column Notes:**

| Column | Description |
|--------|-------------|
| id | Primary key, UUID v4 |
| user_id | FK to users (NULL if email not found) |
| email | Email used in attempt |
| ip_address | Client IP address |
| user_agent | Browser/client information |
| success | Whether login succeeded |
| failure_reason | Why it failed (for debugging) |
| attempted_at | When attempt occurred |

**Failure Reasons:**

| Value | Description |
|-------|-------------|
| `invalid_password` | Password didn't match |
| `user_not_found` | No user with that email |
| `account_locked` | Too many failed attempts |
| `account_inactive` | User account disabled |
| `wrong_provider` | Email user tried Google or vice versa |

---

## Common Queries

### Check Account Lockout

```sql
-- Count failed attempts in last 15 minutes for a user
SELECT COUNT(*) as failed_attempts
FROM login_attempts
WHERE user_id = :user_id
  AND success = false
  AND attempted_at > NOW() - INTERVAL '15 minutes';
```

### Find Valid Refresh Token

```sql
-- Find active, non-expired token by hash
SELECT rt.*, u.email, u.full_name
FROM refresh_tokens rt
JOIN users u ON rt.user_id = u.id
WHERE rt.token_hash = :token_hash
  AND rt.revoked_at IS NULL
  AND rt.expires_at > NOW()
  AND u.is_active = true;
```

### Get User by Email (Sign In)

```sql
SELECT id, email, password_hash, auth_provider, is_active
FROM users
WHERE email = :email;
```

### Get or Create Google User

```sql
-- First, try to find existing user
SELECT id, email, full_name, auth_provider
FROM users
WHERE google_id = :google_id;

-- If not found, check if email exists with different provider
SELECT id, auth_provider
FROM users
WHERE email = :email;

-- If neither found, create new user
INSERT INTO users (email, full_name, auth_provider, google_id)
VALUES (:email, :full_name, 'google', :google_id)
RETURNING id, email, full_name, auth_provider, created_at;
```

### Revoke All User Tokens (Sign Out Everywhere)

```sql
UPDATE refresh_tokens
SET revoked_at = NOW()
WHERE user_id = :user_id
  AND revoked_at IS NULL;
```

### Cleanup Expired Tokens

```sql
-- Run periodically (e.g., daily cron job)
DELETE FROM refresh_tokens
WHERE expires_at < NOW() - INTERVAL '7 days'
   OR revoked_at < NOW() - INTERVAL '7 days';
```

### Cleanup Old Login Attempts

```sql
-- Run periodically to prevent table bloat
DELETE FROM login_attempts
WHERE attempted_at < NOW() - INTERVAL '90 days';
```

---

## SQLAlchemy Models

### User Model

```python
from datetime import datetime
from enum import Enum as PyEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AuthProvider(str, PyEnum):
    EMAIL = "email"
    GOOGLE = "google"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), 
        primary_key=True, 
        default=uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), 
        unique=True, 
        nullable=False, 
        index=True
    )
    full_name: Mapped[str | None] = mapped_column(String(100))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    auth_provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider), 
        nullable=False, 
        default=AuthProvider.EMAIL
    )
    google_id: Mapped[str | None] = mapped_column(
        String(255), 
        unique=True, 
        index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, 
        nullable=False, 
        default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    login_attempts: Mapped[list["LoginAttempt"]] = relationship(
        back_populates="user"
    )
```

### RefreshToken Model

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import INET, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), 
        primary_key=True, 
        default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(255), 
        unique=True, 
        nullable=False,
        index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    user_agent: Mapped[str | None] = mapped_column(String(500))
    ip_address: Mapped[str | None] = mapped_column(INET)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    @property
    def is_valid(self) -> bool:
        """Check if token is active and not expired."""
        return (
            self.revoked_at is None 
            and self.expires_at > datetime.utcnow()
        )
```

### LoginAttempt Model

```python
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import INET, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), 
        primary_key=True, 
        default=uuid4
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), 
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True
    )
    email: Mapped[str] = mapped_column(
        String(255), 
        nullable=False,
        index=True
    )
    ip_address: Mapped[str] = mapped_column(INET, nullable=False, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(50))
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        default=datetime.utcnow,
        index=True
    )

    # Relationships
    user: Mapped["User | None"] = relationship(back_populates="login_attempts")
```

---

## Migrations

### Initial Migration (Alembic)

```python
"""Initial auth schema

Revision ID: 001_initial_auth
Create Date: 2024-01-15 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_initial_auth'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum type
    auth_provider_enum = postgresql.ENUM(
        'email', 'google', 
        name='auth_provider_enum'
    )
    auth_provider_enum.create(op.get_bind())

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(100), nullable=True),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('auth_provider', auth_provider_enum, nullable=False, server_default='email'),
        sa.Column('google_id', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('email', name='users_email_unique'),
        sa.UniqueConstraint('google_id', name='users_google_id_unique'),
        sa.CheckConstraint(
            "(auth_provider = 'email' AND password_hash IS NOT NULL) OR "
            "(auth_provider = 'google' AND google_id IS NOT NULL)",
            name='users_auth_provider_check'
        )
    )
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_google_id', 'users', ['google_id'], postgresql_where=sa.text('google_id IS NOT NULL'))
    op.create_index('idx_users_created_at', 'users', ['created_at'])

    # Create refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token_hash', sa.String(255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('token_hash', name='refresh_tokens_hash_unique')
    )
    op.create_index('idx_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('idx_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'])
    op.create_index('idx_refresh_tokens_expires_at', 'refresh_tokens', ['expires_at'])

    # Create login_attempts table
    op.create_table(
        'login_attempts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('ip_address', postgresql.INET(), nullable=False),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('failure_reason', sa.String(50), nullable=True),
        sa.Column('attempted_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL')
    )
    op.create_index('idx_login_attempts_user_id', 'login_attempts', ['user_id'])
    op.create_index('idx_login_attempts_email', 'login_attempts', ['email'])
    op.create_index('idx_login_attempts_ip', 'login_attempts', ['ip_address'])
    op.create_index('idx_login_attempts_attempted_at', 'login_attempts', ['attempted_at'])


def downgrade() -> None:
    op.drop_table('login_attempts')
    op.drop_table('refresh_tokens')
    op.drop_table('users')
    
    # Drop enum type
    auth_provider_enum = postgresql.ENUM(
        'email', 'google', 
        name='auth_provider_enum'
    )
    auth_provider_enum.drop(op.get_bind())
```

---

## Data Retention

| Table | Retention Policy |
|-------|------------------|
| users | Indefinite (until account deletion) |
| refresh_tokens | Delete 7 days after expiry or revocation |
| login_attempts | Delete after 90 days |

Implement via scheduled job (cron) or database-level scheduled tasks.