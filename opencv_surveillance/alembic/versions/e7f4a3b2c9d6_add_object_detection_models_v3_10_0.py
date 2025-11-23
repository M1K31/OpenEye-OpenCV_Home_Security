"""Add object detection models for v3.10.0

Revision ID: e7f4a3b2c9d6
Revises: d5e9f3a2b8c4
Create Date: 2025-11-15 01:00:00.000000

Adds YOLO-based object detection tracking:
- ObjectDetectionEvent table for tracking detected objects (vehicles, animals, packages)
- IdentifiedObject table for user-identified specific objects
- Updates to RecordingEvent for object detection counts
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision: str = 'e7f4a3b2c9d6'
down_revision: Union[str, Sequence[str], None] = 'd5e9f3a2b8c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema - Add object detection models

    Creates tables and indexes for YOLO-based object detection and identification
    """

    # Create identified_objects table
    op.create_table(
        'identified_objects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('object_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('object_class', sa.String(), nullable=False),
        sa.Column('object_subclass', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('representative_image_path', sa.String(), nullable=True),
        sa.Column('features', sa.String(), nullable=True),
        sa.Column('detection_count', sa.Integer(), default=0),
        sa.Column('first_seen_at', sa.DateTime(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('notification_config', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for identified_objects
    with op.batch_alter_table('identified_objects', schema=None) as batch_op:
        batch_op.create_index('idx_identified_object_id', ['object_id'], unique=True)
        batch_op.create_index('idx_identified_object_name', ['name'], unique=False)
        batch_op.create_index('idx_identified_object_class', ['object_class'], unique=False)
        batch_op.create_index('idx_identified_object_active', ['is_active'], unique=False)

    # Create object_detection_events table
    op.create_table(
        'object_detection_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('camera_id', sa.String(), nullable=False),
        sa.Column('object_class', sa.String(), nullable=False),
        sa.Column('object_subclass', sa.String(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('detected_at', sa.DateTime(), default=datetime.utcnow),
        sa.Column('bbox_x', sa.Integer(), nullable=False),
        sa.Column('bbox_y', sa.Integer(), nullable=False),
        sa.Column('bbox_width', sa.Integer(), nullable=False),
        sa.Column('bbox_height', sa.Integer(), nullable=False),
        sa.Column('frame_width', sa.Integer(), nullable=True),
        sa.Column('frame_height', sa.Integer(), nullable=True),
        sa.Column('snapshot_path', sa.String(), nullable=True),
        sa.Column('recording_id', sa.Integer(), nullable=True),
        sa.Column('recording_path', sa.String(), nullable=True),
        sa.Column('motion_detected', sa.Boolean(), default=False),
        sa.Column('identified_object_id', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['recording_id'], ['recording_events.id']),
        sa.ForeignKeyConstraint(['identified_object_id'], ['identified_objects.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for object_detection_events
    with op.batch_alter_table('object_detection_events', schema=None) as batch_op:
        batch_op.create_index('idx_object_camera_id', ['camera_id'], unique=False)
        batch_op.create_index('idx_object_class', ['object_class'], unique=False)
        batch_op.create_index('idx_object_detected_at', ['detected_at'], unique=False)
        batch_op.create_index('idx_object_camera_time', ['camera_id', 'detected_at'], unique=False)
        batch_op.create_index('idx_object_recording_id', ['recording_id'], unique=False)
        batch_op.create_index('idx_object_identified_id', ['identified_object_id'], unique=False)

    # Add object detection columns to recording_events table
    with op.batch_alter_table('recording_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('objects_detected', sa.Integer(), default=0))
        batch_op.add_column(sa.Column('identified_objects_detected', sa.Integer(), default=0))


def downgrade() -> None:
    """Downgrade schema - Remove object detection models."""

    # Remove columns from recording_events
    with op.batch_alter_table('recording_events', schema=None) as batch_op:
        batch_op.drop_column('identified_objects_detected')
        batch_op.drop_column('objects_detected')

    # Drop indexes and table for object_detection_events
    with op.batch_alter_table('object_detection_events', schema=None) as batch_op:
        batch_op.drop_index('idx_object_identified_id')
        batch_op.drop_index('idx_object_recording_id')
        batch_op.drop_index('idx_object_camera_time')
        batch_op.drop_index('idx_object_detected_at')
        batch_op.drop_index('idx_object_class')
        batch_op.drop_index('idx_object_camera_id')

    op.drop_table('object_detection_events')

    # Drop indexes and table for identified_objects
    with op.batch_alter_table('identified_objects', schema=None) as batch_op:
        batch_op.drop_index('idx_identified_object_active')
        batch_op.drop_index('idx_identified_object_class')
        batch_op.drop_index('idx_identified_object_name')
        batch_op.drop_index('idx_identified_object_id')

    op.drop_table('identified_objects')
