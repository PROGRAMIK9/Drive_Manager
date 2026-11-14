"""Remove unsent campaign drafts; previews are now browser-only.

Revision ID: 8b4f1a7c2d90
Revises: 7a2d4f8c1b60
"""
from typing import Sequence, Union

from alembic import op


revision: str = "8b4f1a7c2d90"
down_revision: Union[str, Sequence[str], None] = "7a2d4f8c1b60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM placementcampaign WHERE status = 'DRAFT'")


def downgrade() -> None:
    # Deleted unsent drafts cannot be restored.
    pass
