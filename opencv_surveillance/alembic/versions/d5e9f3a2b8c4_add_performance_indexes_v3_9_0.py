"""Add performance indexes for v3.9.0

Revision ID: d5e9f3a2b8c4
Revises: c4d8e2f1b3a7
Create Date: 2025-11-14 01:00:00.000000

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
revision: str = 'd5e9f3a2b8c4'
down_revision: Union[str, Sequence[str], None] = 'c4d8e2f1b3a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema - Add performance-critical indexes

    These indexes significantly improve query performance for:
    - Recordings list (sorted by date)
    - Face detection history (per camera/person over time)
    - Motion detection history (per camera over time)
    - Cluster filtering and sorting
    - Account lockout checks
    """

    # RecordingEvent indexes
    # Critical: Used for sorting recordings by date (mentioned in code comments)
    create_index_if_missing('idx_recording_started_at', 'recording_events', ['started_at'], unique=False)

    # Composite index for camera + time queries (very common pattern)
    create_index_if_missing('idx_recording_camera_time', 'recording_events', ['camera_id', 'started_at'], unique=False)

    # Index on ended_at for filtering completed recordings
    create_index_if_missing('idx_recording_ended_at', 'recording_events', ['ended_at'], unique=False)

    # FaceDetectionEvent composite indexes
    # Composite index for camera + time queries (face history per camera)
    create_index_if_missing('idx_face_camera_time', 'face_detection_events', ['camera_id', 'detected_at'], unique=False)

    # Composite index for person + time queries (face history per person)
    create_index_if_missing('idx_face_person_time', 'face_detection_events', ['person_name', 'detected_at'], unique=False)

    # MotionDetectionEvent composite indexes
    # Composite index for camera + time queries (motion history per camera)
    create_index_if_missing('idx_motion_camera_time', 'motion_detection_events', ['camera_id', 'detected_at'], unique=False)

    # FaceCluster indexes
    # Index for filtering identified vs unidentified clusters
    create_index_if_missing('idx_cluster_identified', 'face_clusters', ['is_identified'], unique=False)

    # Index for sorting clusters by creation date
    create_index_if_missing('idx_cluster_created_at', 'face_clusters', ['created_at'], unique=False)

    # Index for finding recently seen clusters
    create_index_if_missing('idx_cluster_last_seen', 'face_clusters', ['last_seen_at'], unique=False)

    # User indexes (for new lockout feature)
    # Index for checking account lockout status
    create_index_if_missing('idx_user_locked_until', 'users', ['account_locked_until'], unique=False)

    # Index for checking active users
    create_index_if_missing('idx_user_is_active', 'users', ['is_active'], unique=False)


def downgrade() -> None:
    """Downgrade schema - Remove performance indexes."""

    # Remove User indexes
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index('idx_user_is_active')
        batch_op.drop_index('idx_user_locked_until')

    # Remove FaceCluster indexes
    with op.batch_alter_table('face_clusters', schema=None) as batch_op:
        batch_op.drop_index('idx_cluster_last_seen')
        batch_op.drop_index('idx_cluster_created_at')
        batch_op.drop_index('idx_cluster_identified')

    # Remove MotionDetectionEvent indexes
    with op.batch_alter_table('motion_detection_events', schema=None) as batch_op:
        batch_op.drop_index('idx_motion_camera_time')

    # Remove FaceDetectionEvent indexes
    with op.batch_alter_table('face_detection_events', schema=None) as batch_op:
        batch_op.drop_index('idx_face_person_time')
        batch_op.drop_index('idx_face_camera_time')

    # Remove RecordingEvent indexes
    with op.batch_alter_table('recording_events', schema=None) as batch_op:
        batch_op.drop_index('idx_recording_ended_at')
        batch_op.drop_index('idx_recording_camera_time')
        batch_op.drop_index('idx_recording_started_at')
