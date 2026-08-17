"""Add object detection alert fields to alert_configurations table

Revision ID: f9g6h5i4j3k2
Revises: e7f4a3b2c9d6
Create Date: 2025-11-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from backend.database.migration_guards import (
    add_column_if_missing,
    create_index_if_missing,
    create_table_if_missing,
)


# revision identifiers, used by Alembic.
revision: str = 'f9g6h5i4j3k2'
down_revision: Union[str, Sequence[str], None] = 'e7f4a3b2c9d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add object detection alert configuration fields."""

    # Add object detection alert fields to alert_configurations table
    # v3.10.0: Object Detection Alerts
    add_column_if_missing('alert_configurations', sa.Column('object_detection_alerts_enabled', sa.Boolean(), nullable=True, server_default='1'))
    add_column_if_missing('alert_configurations', sa.Column('vehicle_alerts_enabled', sa.Boolean(), nullable=True, server_default='1'))
    add_column_if_missing('alert_configurations', sa.Column('animal_alerts_enabled', sa.Boolean(), nullable=True, server_default='1'))
    add_column_if_missing('alert_configurations', sa.Column('package_alerts_enabled', sa.Boolean(), nullable=True, server_default='1'))
    add_column_if_missing('alert_configurations', sa.Column('identified_object_alerts_enabled', sa.Boolean(), nullable=True, server_default='1'))

    # Update existing rows to have default values (enabled)
    op.execute("UPDATE alert_configurations SET object_detection_alerts_enabled = 1 WHERE object_detection_alerts_enabled IS NULL")
    op.execute("UPDATE alert_configurations SET vehicle_alerts_enabled = 1 WHERE vehicle_alerts_enabled IS NULL")
    op.execute("UPDATE alert_configurations SET animal_alerts_enabled = 1 WHERE animal_alerts_enabled IS NULL")
    op.execute("UPDATE alert_configurations SET package_alerts_enabled = 1 WHERE package_alerts_enabled IS NULL")
    op.execute("UPDATE alert_configurations SET identified_object_alerts_enabled = 1 WHERE identified_object_alerts_enabled IS NULL")


def downgrade() -> None:
    """Downgrade schema - Remove object detection alert fields from alert_configurations table."""

    with op.batch_alter_table('alert_configurations', schema=None) as batch_op:
        batch_op.drop_column('identified_object_alerts_enabled')
        batch_op.drop_column('package_alerts_enabled')
        batch_op.drop_column('animal_alerts_enabled')
        batch_op.drop_column('vehicle_alerts_enabled')
        batch_op.drop_column('object_detection_alerts_enabled')
