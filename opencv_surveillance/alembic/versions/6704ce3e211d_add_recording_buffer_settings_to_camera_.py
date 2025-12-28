"""Add recording buffer settings to Camera model

Revision ID: 6704ce3e211d
Revises: h1i2j3k4l5m6
Create Date: 2025-12-25 22:18:53.812030

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6704ce3e211d'
down_revision: Union[str, Sequence[str], None] = 'h1i2j3k4l5m6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add recording buffer settings columns."""
    # Use raw SQL for SQLite compatibility to avoid batch mode issues
    # with existing default values in the table
    connection = op.get_bind()

    # Check if columns already exist before adding
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('cameras')]

    if 'pre_motion_seconds' not in columns:
        op.execute("ALTER TABLE cameras ADD COLUMN pre_motion_seconds INTEGER DEFAULT 5")
    if 'post_motion_seconds' not in columns:
        op.execute("ALTER TABLE cameras ADD COLUMN post_motion_seconds INTEGER DEFAULT 10")
    if 'max_recording_duration' not in columns:
        op.execute("ALTER TABLE cameras ADD COLUMN max_recording_duration INTEGER DEFAULT 300")


def downgrade() -> None:
    """Downgrade schema - SQLite doesn't support DROP COLUMN easily."""
    # SQLite doesn't support DROP COLUMN, would need full table recreation
    # For safety, we'll leave columns in place on downgrade
    pass
