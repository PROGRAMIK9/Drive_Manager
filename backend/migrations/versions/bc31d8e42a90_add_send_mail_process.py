"""Add SPC-only send_mail process value.

Revision ID: bc31d8e42a90
Revises: a7b8c9d0e1f2
"""
from typing import Sequence, Union

from alembic import op


revision: str = "bc31d8e42a90"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE process ADD VALUE IF NOT EXISTS 'send_mail'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed without rebuilding the type.
    pass
