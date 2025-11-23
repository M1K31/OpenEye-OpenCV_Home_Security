"""Add refresh tokens table for JWT token rotation

Revision ID: b9c5e7f3d4a6
Revises: a8f3d1e9c2b5
Create Date: 2025-11-09 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b9c5e7f3d4a6'
down_revision: Union[str, Sequence[str], None] = 'a8f3d1e9c2b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add refresh_tokens table for JWT token rotation."""

    # Create refresh_tokens table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=512), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('revoked', sa.Boolean(), nullable=True),
        sa.Column('device_info', sa.String(length=255), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.create_index('ix_refresh_tokens_expires_at', ['expires_at'], unique=False)
        batch_op.create_index('ix_refresh_tokens_id', ['id'], unique=False)
        batch_op.create_index('ix_refresh_tokens_revoked', ['revoked'], unique=False)
        batch_op.create_index('ix_refresh_tokens_token', ['token'], unique=True)
        batch_op.create_index('ix_refresh_tokens_user_id', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema - Remove refresh_tokens table."""

    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.drop_index('ix_refresh_tokens_user_id')
        batch_op.drop_index('ix_refresh_tokens_token')
        batch_op.drop_index('ix_refresh_tokens_revoked')
        batch_op.drop_index('ix_refresh_tokens_id')
        batch_op.drop_index('ix_refresh_tokens_expires_at')

    op.drop_table('refresh_tokens')
