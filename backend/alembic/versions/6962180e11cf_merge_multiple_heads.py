"""merge_multiple_heads

Revision ID: 6962180e11cf
Revises: b3c4d5e6f7a8, c4d5e6f7a8b9
Create Date: 2026-05-28 10:02:32.822070

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6962180e11cf'
down_revision: Union[str, None] = ('b3c4d5e6f7a8', 'c4d5e6f7a8b9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
