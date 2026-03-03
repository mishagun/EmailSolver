"""add category_actions to analyses

Revision ID: a1b2c3d4e5f6
Revises: 8c146c84ef63
Create Date: 2026-03-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "8c146c84ef63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("category_actions", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "category_actions")
