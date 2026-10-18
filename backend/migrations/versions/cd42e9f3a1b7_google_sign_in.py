"""Add Google identity to users.

Revision ID: cd42e9f3a1b7
Revises: bc31d8e42a90
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cd42e9f3a1b7"
down_revision: Union[str, Sequence[str], None] = "bc31d8e42a90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("google_sub", sa.String(), nullable=True))
    op.create_index("ix_user_google_sub", "user", ["google_sub"], unique=True)
    op.alter_column("user", "hashed_password", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.alter_column("user", "hashed_password", existing_type=sa.String(), nullable=False)
    op.drop_index("ix_user_google_sub", table_name="user")
    op.drop_column("user", "google_sub")
