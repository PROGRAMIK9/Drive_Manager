"""Add Gmail OAuth state and Pub/Sub notification ledger."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "7c9e4a2d1f60"
down_revision: Union[str, Sequence[str], None] = "5b7d2e1a4c90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gmailoauthstate",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("state_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_gmailoauthstate_state_hash", "gmailoauthstate", ["state_hash"])
    op.create_index("ix_gmailoauthstate_user_id", "gmailoauthstate", ["user_id"])
    op.create_table(
        "gmailnotification",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pubsub_message_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("email_address", sa.String(length=320), nullable=False),
        sa.Column("history_id", sa.String(length=128), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
    )
    op.create_index("ix_gmailnotification_pubsub_message_id", "gmailnotification", ["pubsub_message_id"])
    op.create_index("ix_gmailnotification_email_address", "gmailnotification", ["email_address"])
    op.create_index("ix_gmailnotification_processing_status", "gmailnotification", ["processing_status"])


def downgrade() -> None:
    op.drop_table("gmailnotification")
    op.drop_table("gmailoauthstate")
