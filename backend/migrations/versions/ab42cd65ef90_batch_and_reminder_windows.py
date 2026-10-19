"""Add batch years and a second event reminder window.

Revision ID: ab42cd65ef90
Revises: d8a3b1c9e204
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ab42cd65ef90"
down_revision: Union[str, Sequence[str], None] = "d8a3b1c9e204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("company", sa.Column("year_of_passing", sa.Integer(), nullable=False, server_default="2027"))
    op.add_column("user", sa.Column("year_of_passing", sa.Integer(), nullable=True))
    op.add_column("eventreminder", sa.Column("day_before_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("eventreminder", sa.Column("day_before_claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("eventreminder", sa.Column("day_before_scheduled_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_eventreminder_day_before_claimed_at", "eventreminder", ["day_before_claimed_at"])
    op.create_index("ix_eventreminder_day_before_scheduled_at", "eventreminder", ["day_before_scheduled_at"])
    op.execute("UPDATE eventreminder SET day_before_scheduled_at = scheduled_at - INTERVAL '23 hours', sent_at = NULL, claimed_at = NULL")
    op.alter_column("eventreminder", "day_before_scheduled_at", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_eventreminder_day_before_claimed_at", table_name="eventreminder")
    op.drop_index("ix_eventreminder_day_before_scheduled_at", table_name="eventreminder")
    op.drop_column("eventreminder", "day_before_scheduled_at")
    op.drop_column("eventreminder", "day_before_claimed_at")
    op.drop_column("eventreminder", "day_before_sent_at")
    op.drop_column("user", "year_of_passing")
    op.drop_column("company", "year_of_passing")
