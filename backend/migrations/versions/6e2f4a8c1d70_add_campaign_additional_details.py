"""Ensure placement campaigns store arbitrary extracted details.

Revision ID: 6e2f4a8c1d70
Revises: 4d6e9f1a2b30
"""
from typing import Sequence, Union

from alembic import op


revision: str = "6e2f4a8c1d70"
down_revision: Union[str, Sequence[str], None] = "4d6e9f1a2b30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS supports both databases that applied the original campaign
    # migration before this column was added and databases created from its
    # current definition, which already includes the column.
    op.execute(
        "ALTER TABLE placementcampaign "
        "ADD COLUMN IF NOT EXISTS additional_details JSON NOT NULL DEFAULT '{}'::json"
    )


def downgrade() -> None:
    op.drop_column("placementcampaign", "additional_details")
