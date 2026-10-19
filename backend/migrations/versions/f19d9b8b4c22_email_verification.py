"""Add email verification state.

Revision ID: f19d9b8b4c22
Revises: e05ec3557e4f
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f19d9b8b4c22"
down_revision: Union[str, Sequence[str], None] = "e05ec3557e4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("user", "is_verified", server_default=None)


def downgrade() -> None:
    op.drop_column("user", "is_verified")