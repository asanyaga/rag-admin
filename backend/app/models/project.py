from datetime import datetime
from uuid import UUID, uuid4
import json

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, TypeDecorator
from sqlalchemy.dialects.postgresql import ARRAY, TEXT, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StringList(TypeDecorator):
    """Custom type to store list of strings.

    Uses PostgreSQL ARRAY in production, JSON in SQLite for testing.
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(ARRAY(TEXT))
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if dialect.name == 'postgresql':
            return value
        elif value is not None:
            return json.dumps(value)
        return value

    def process_result_value(self, value, dialect):
        if dialect.name == 'postgresql':
            return value if value is not None else []
        elif value is not None:
            return json.loads(value) if value else []
        return []


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=sa.text('gen_random_uuid()')
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    description: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True
    )
    tags: Mapped[list[str]] = mapped_column(
        StringList,
        nullable=False,
        default=list
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default='false'
    )
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
    user: Mapped["User"] = relationship(back_populates="projects")
    documents: Mapped[list["Document"]] = relationship(back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        sa.UniqueConstraint('user_id', 'name', name='uq_projects_user_name'),
        sa.Index('ix_projects_user_id', 'user_id'),
        sa.Index('ix_projects_is_archived', 'is_archived'),
        sa.Index('ix_projects_created_at', 'created_at'),
        sa.Index('ix_projects_user_active', 'user_id', 'is_archived'),
    )
