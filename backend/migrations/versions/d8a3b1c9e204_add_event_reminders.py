"""Persist event reminder schedules.

Revision ID: d8a3b1c9e204
Revises: cd42e9f3a1b7
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8a3b1c9e204"
down_revision: Union[str, Sequence[str], None] = "cd42e9f3a1b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eventreminder",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id"),
    )
    op.create_index("ix_eventreminder_company_id", "eventreminder", ["company_id"])
    op.create_index("ix_eventreminder_scheduled_at", "eventreminder", ["scheduled_at"])
    op.create_index("ix_eventreminder_claimed_at", "eventreminder", ["claimed_at"])


def downgrade() -> None:
    op.drop_index("ix_eventreminder_claimed_at", table_name="eventreminder")
    op.drop_index("ix_eventreminder_scheduled_at", table_name="eventreminder")
    op.drop_index("ix_eventreminder_company_id", table_name="eventreminder")
    op.drop_table("eventreminder")
