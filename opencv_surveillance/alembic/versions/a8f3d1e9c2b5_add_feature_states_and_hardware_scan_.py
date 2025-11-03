"""Add feature states and hardware scan history tables

Revision ID: a8f3d1e9c2b5
Revises: 4b2aa0a5583c
Create Date: 2025-11-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = 'a8f3d1e9c2b5'
down_revision: Union[str, Sequence[str], None] = '4b2aa0a5583c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add hardware-aware feature management tables."""

    # Create feature_states table
    op.create_table(
        'feature_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('feature_id', sa.String(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('auto_configured', sa.Boolean(), nullable=True),
        sa.Column('user_override', sa.Boolean(), nullable=True),
        sa.Column('hardware_compatible', sa.Boolean(), nullable=True),
        sa.Column('compatibility_reason', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('feature_states', schema=None) as batch_op:
        batch_op.create_index('ix_feature_states_enabled', ['enabled'], unique=False)
        batch_op.create_index('ix_feature_states_feature_id', ['feature_id'], unique=True)
        batch_op.create_index('ix_feature_states_id', ['id'], unique=False)

    # Create hardware_scan_history table
    op.create_table(
        'hardware_scan_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scan_type', sa.String(), nullable=True),
        sa.Column('cpu_cores', sa.Integer(), nullable=True),
        sa.Column('ram_total_gb', sa.Float(), nullable=True),
        sa.Column('gpu_available', sa.Boolean(), nullable=True),
        sa.Column('gpu_name', sa.String(), nullable=True),
        sa.Column('gpu_memory_mb', sa.Integer(), nullable=True),
        sa.Column('hardware_tier', sa.String(), nullable=True),
        sa.Column('changes_detected', sa.Boolean(), nullable=True),
        sa.Column('changes_summary', sa.String(), nullable=True),
        sa.Column('features_enabled', sa.Integer(), nullable=True),
        sa.Column('features_disabled', sa.Integer(), nullable=True),
        sa.Column('scanned_at', sa.DateTime(), nullable=True),
        sa.Column('scanned_by', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('hardware_scan_history', schema=None) as batch_op:
        batch_op.create_index('ix_hardware_scan_history_id', ['id'], unique=False)
        batch_op.create_index('ix_hardware_scan_history_scanned_at', ['scanned_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema - Remove hardware-aware feature management tables."""

    with op.batch_alter_table('hardware_scan_history', schema=None) as batch_op:
        batch_op.drop_index('ix_hardware_scan_history_scanned_at')
        batch_op.drop_index('ix_hardware_scan_history_id')

    op.drop_table('hardware_scan_history')

    with op.batch_alter_table('feature_states', schema=None) as batch_op:
        batch_op.drop_index('ix_feature_states_id')
        batch_op.drop_index('ix_feature_states_feature_id')
        batch_op.drop_index('ix_feature_states_enabled')

    op.drop_table('feature_states')
