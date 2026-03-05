"""add unsubscribe header fields

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6g7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("classified_emails", sa.Column("unsubscribe_header", sa.Text(), nullable=True))
    op.add_column("classified_emails", sa.Column("unsubscribe_post_header", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("classified_emails", "unsubscribe_post_header")
    op.drop_column("classified_emails", "unsubscribe_header")
