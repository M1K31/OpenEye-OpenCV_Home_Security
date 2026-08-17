"""Add performance indexes

Revision ID: 9057848527e7
Revises: 79605a54272e
Create Date: 2025-10-22 23:52:18.013552

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
revision: str = '9057848527e7'
down_revision: Union[str, Sequence[str], None] = '79605a54272e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes for common queries"""
    # RecordingEvent indexes
    create_index_if_missing(
        'idx_recording_camera_time',
        'recording_events',
        ['camera_id', 'started_at'],
        unique=False
    )
    create_index_if_missing(
        'idx_recording_started_at',
        'recording_events',
        ['started_at'],
        unique=False
    )

    # FaceDetectionEvent indexes
    create_index_if_missing(
        'idx_face_camera_time',
        'face_detection_events',
        ['camera_id', 'detected_at'],
        unique=False
    )
    create_index_if_missing(
        'idx_face_person_time',
        'face_detection_events',
        ['person_name', 'detected_at'],
        unique=False
    )
    create_index_if_missing(
        'idx_face_cluster_time',
        'face_detection_events',
        ['cluster_id', 'detected_at'],
        unique=False
    )

    # MotionDetectionEvent indexes
    create_index_if_missing(
        'idx_motion_camera_time',
        'motion_detection_events',
        ['camera_id', 'detected_at'],
        unique=False
    )
    create_index_if_missing(
        'idx_motion_detected_at',
        'motion_detection_events',
        ['detected_at'],
        unique=False
    )

    # FaceCluster indexes
    create_index_if_missing(
        'idx_cluster_identified',
        'face_clusters',
        ['is_identified'],
        unique=False
    )
    create_index_if_missing(
        'idx_cluster_updated',
        'face_clusters',
        ['updated_at'],
        unique=False
    )


def downgrade() -> None:
    """Remove performance indexes"""
    # Drop all indexes in reverse order
    op.drop_index('idx_cluster_updated', table_name='face_clusters')
    op.drop_index('idx_cluster_identified', table_name='face_clusters')
    op.drop_index('idx_motion_detected_at', table_name='motion_detection_events')
    op.drop_index('idx_motion_camera_time', table_name='motion_detection_events')
    op.drop_index('idx_face_cluster_time', table_name='face_detection_events')
    op.drop_index('idx_face_person_time', table_name='face_detection_events')
    op.drop_index('idx_face_camera_time', table_name='face_detection_events')
    op.drop_index('idx_recording_started_at', table_name='recording_events')
    op.drop_index('idx_recording_camera_time', table_name='recording_events')
