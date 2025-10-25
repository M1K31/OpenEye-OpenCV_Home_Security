"""Initial migration - existing schema

Revision ID: 79605a54272e
Revises: 
Create Date: 2025-10-22 20:38:50.989770

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '79605a54272e'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Initial baseline migration.

    This is a baseline migration for existing databases.
    No schema changes are applied - this just marks the current schema state.

    For new installations, tables are created by Base.metadata.create_all()
    before migrations run.
    """
    # No-op: This is a baseline migration for existing databases
    # The schema is already in place via create_all() in main.py
    pass


def downgrade() -> None:
    """Downgrade schema - No-op for baseline migration."""
    # No-op: Cannot downgrade from baseline
    pass
