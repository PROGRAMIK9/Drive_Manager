"""Add durable Gmail job retry state and multiple interview dates."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8d2f6a1c9b40"
down_revision: Union[str, Sequence[str], None] = "7c9e4a2d1f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gmailnotification", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("gmailnotification", sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("gmailnotification", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column("gmailnotification", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("pendingplacementopportunity", sa.Column("interview_dates", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade() -> None:
    op.drop_column("pendingplacementopportunity", "interview_dates")
    op.drop_column("gmailnotification", "last_error")
    op.drop_column("gmailnotification", "next_attempt_at")
    op.drop_column("gmailnotification", "processing_started_at")
    op.drop_column("gmailnotification", "attempt_count")
