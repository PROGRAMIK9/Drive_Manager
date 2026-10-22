"""Add company event process values.

Revision ID: cd53e8a412bf
Revises: ab42cd65ef90
"""
from typing import Sequence, Union

from alembic import op


revision: str = "cd53e8a412bf"
down_revision: Union[str, Sequence[str], None] = "ab42cd65ef90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE process ADD VALUE IF NOT EXISTS 'group_discussion'")
    op.execute("ALTER TYPE process ADD VALUE IF NOT EXISTS 'pen_paper_test'")
    op.execute("ALTER TYPE process ADD VALUE IF NOT EXISTS 'technical_assessment'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed without rebuilding the type.
    pass
