"""Store registrations until email verification.

Revision ID: a7b8c9d0e1f2
Revises: f19d9b8b4c22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f19d9b8b4c22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("pendingregistration"):
        op.create_table(
            "pendingregistration",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("hashed_password", sa.String(), nullable=False),
            sa.Column(
                "role",
                postgresql.ENUM("spc", "student", name="role", create_type=False),
                nullable=False,
            ),
            sa.UniqueConstraint("email"),
        )
    if "ix_pendingregistration_email" not in {
        index["name"] for index in inspector.get_indexes("pendingregistration")
    }:
        op.create_index("ix_pendingregistration_email", "pendingregistration", ["email"])


def downgrade() -> None:
    op.drop_index("ix_pendingregistration_email", table_name="pendingregistration")
    op.drop_table("pendingregistration")