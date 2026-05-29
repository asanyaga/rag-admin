from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProviderKey(Base):
    """ProviderKey model for storing encrypted API keys for embedding providers.

    Implements BYOK (Bring Your Own Key) functionality where users provide
    their own API keys for embedding and LLM providers.

    Key design decisions:
    - Keys are encrypted at rest using Fernet symmetric encryption
    - Supports both account-level and project-level keys
    - Resolution order: project-level key → account-level key → error
    - project_id NULL means account-level (applies to all user's projects)

    Supported providers (MVP):
    - openai: OpenAI embedding models
    - voyage: Voyage AI embedding models
    - local: Local models via Ollama (no key needed, but config stored)
    """
    __tablename__ = "provider_keys"

    # Identity
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text('gen_random_uuid()')
    )

    # Ownership
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    project_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True
    )  # NULL = account-level key

    # Provider identification
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )  # e.g., "openai", "voyage", "local"

    # Encrypted API key
    # Encrypted using Fernet with app-level encryption key
    # Decrypted only when making provider API calls
    api_key_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    # Optional base URL for self-hosted / custom inference endpoints
    base_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        server_default=sa.text('NOW()')
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=sa.text('NOW()')
    )

    # Relationships
    user: Mapped["User"] = relationship()
    project: Mapped["Project | None"] = relationship()

    __table_args__ = (
        # Ensure unique provider key per user per project (or account-level)
        sa.UniqueConstraint(
            'user_id', 'project_id', 'provider',
            name='uq_provider_keys_user_project_provider'
        ),
        sa.Index('ix_provider_keys_user_id', 'user_id'),
        sa.Index('ix_provider_keys_project_id', 'project_id'),
        sa.Index('ix_provider_keys_user_provider', 'user_id', 'provider'),
    )
