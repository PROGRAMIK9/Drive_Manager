"""Keep a named revision boundary for email date fields now in base migration."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "5b7d2e1a4c90"
down_revision: Union[str, Sequence[str], None] = "3a1c8f9d2b40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # These nullable columns are included in the initial email automation
    # migration so a fresh install and an upgraded install share one schema.
    pass


def downgrade() -> None:
    pass
