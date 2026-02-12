"""create_default_project_for_users

Revision ID: f2913476b229
Revises: b2c3d4e5f6a7
Create Date: 2026-02-12 11:54:46.461113

"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = 'f2913476b229'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PROJECT_NAME = 'Default Project'


def upgrade() -> None:
    conn = op.get_bind()

    # Find all users who don't already have a default project
    users_without_default = conn.execute(
        sa.text(
            "SELECT u.id FROM users u "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM projects p WHERE p.user_id = u.id AND p.is_default = true"
            ")"
        )
    ).fetchall()

    for (user_id,) in users_without_default:
        conn.execute(
            sa.text(
                "INSERT INTO projects (id, user_id, name, description, is_default, is_archived, tags, created_at, updated_at) "
                "VALUES (:id, :user_id, :name, :description, true, false, ARRAY[]::text[], NOW(), NOW())"
            ),
            {
                "id": str(uuid4()),
                "user_id": user_id,
                "name": PROJECT_NAME,
                "description": "Auto-created default project",
            },
        )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        sa.text(
            "DELETE FROM projects WHERE name = :name AND is_default = true "
            "AND description = 'Auto-created default project'"
        ),
        {"name": PROJECT_NAME},
    )
