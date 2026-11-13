"""Store editable key/value facts extracted from placement emails.

Revision ID: 7a2d4f8c1b60
Revises: 6e2f4a8c1d70
"""
from typing import Sequence, Union

from alembic import op


revision: str = "7a2d4f8c1b60"
down_revision: Union[str, Sequence[str], None] = "6e2f4a8c1d70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE pendingplacementopportunity "
        "ADD COLUMN IF NOT EXISTS additional_data JSON NULL"
    )
    op.execute(
        """
        UPDATE pendingplacementopportunity AS opportunity
        SET additional_data = NULLIF(COALESCE(
            (email.extracted_data -> 'placement_extraction' -> 'additional_details')::jsonb,
            (email.extracted_data -> 'additional_details')::jsonb,
            '{}'::jsonb
        ), '{}'::jsonb)::json
        FROM processedemail AS email
        WHERE opportunity.source_email_id = email.id
          AND opportunity.additional_data IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("pendingplacementopportunity", "additional_data")
