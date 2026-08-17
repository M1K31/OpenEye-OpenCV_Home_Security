"""Add configurable face detection settings to Camera

Revision ID: g1h2i3j4k5l6
Revises: f9g6h5i4j3k2
Create Date: 2025-12-08

These settings allow tuning face detection for different camera types:
- face_detection_model: "hog" (CPU) or "cnn" (GPU/CUDA)
- face_detection_upsample: 0-2, higher finds smaller faces but slower
- face_detection_scale: "auto", "none", or manual factor like "0.5"
- min_face_size_pixels: Minimum face size to detect
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
revision: str = 'g1h2i3j4k5l6'
down_revision: Union[str, Sequence[str], None] = 'f9g6h5i4j3k2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add face detection configuration columns to cameras table."""
    # Detection model: "hog" (CPU, fast) or "cnn" (GPU, accurate)
    add_column_if_missing('cameras', sa.Column('face_detection_model', sa.String(),
                                   nullable=True, server_default='hog'))

    # Upsample times: 0 (fastest), 1 (balanced), 2 (finds smallest faces)
    add_column_if_missing('cameras', sa.Column('face_detection_upsample', sa.Integer(),
                                   nullable=True, server_default='1'))

    # Scale mode: "auto" (adaptive), "none" (native), or "0.5" (manual)
    add_column_if_missing('cameras', sa.Column('face_detection_scale', sa.String(),
                                   nullable=True, server_default='auto'))

    # Minimum face size in pixels to detect (filters false positives)
    add_column_if_missing('cameras', sa.Column('min_face_size_pixels', sa.Integer(),
                                   nullable=True, server_default='20'))


def downgrade() -> None:
    """Remove face detection configuration columns."""
    with op.batch_alter_table('cameras', schema=None) as batch_op:
        batch_op.drop_column('min_face_size_pixels')
        batch_op.drop_column('face_detection_scale')
        batch_op.drop_column('face_detection_upsample')
        batch_op.drop_column('face_detection_model')
