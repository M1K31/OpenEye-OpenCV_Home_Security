"""Add 2FA account lockout fields to users table

Revision ID: c4d8e2f1b3a7
Revises: b9c5e7f3d4a6
Create Date: 2025-11-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4d8e2f1b3a7'
down_revision: Union[str, Sequence[str], None] = 'b9c5e7f3d4a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add 2FA account lockout tracking fields to users table."""

    # Add account lockout fields to users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('failed_2fa_attempts', sa.Integer(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('last_failed_2fa_attempt', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('account_locked_until', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('lockout_count', sa.Integer(), nullable=True, server_default='0'))

    # Update existing rows to have default values
    op.execute("UPDATE users SET failed_2fa_attempts = 0 WHERE failed_2fa_attempts IS NULL")
    op.execute("UPDATE users SET lockout_count = 0 WHERE lockout_count IS NULL")


def downgrade() -> None:
    """Downgrade schema - Remove 2FA account lockout fields from users table."""

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('lockout_count')
        batch_op.drop_column('account_locked_until')
        batch_op.drop_column('last_failed_2fa_attempt')
        batch_op.drop_column('failed_2fa_attempts')
