"""add trained_at to face_clusters

Records when a cluster was promoted into a trained profile.

The capture policy stops collecting new likenesses once a cluster reaches the
maturity threshold, on the assumption that it has by then been promoted to a
profile and will be refreshed on the normal per-day-per-camera schedule. Nothing
recorded whether that promotion actually happened, so a cluster whose training
never ran — auto-training disabled, the overnight window never firing, a
training error — would stop collecting at the threshold and never become a
profile, with no signal in either direction.

Existing rows are backfilled from is_identified + label, which together are what
the promotion path sets. That is an inference rather than a record: it is the
best available evidence for clusters promoted before this column existed, and it
errs towards "already trained", which preserves current behaviour rather than
making established clusters suddenly resume collecting.

Revision ID: 9c1d47f0be31
Revises: 6704ce3e211d
"""
from alembic import op
import sqlalchemy as sa
from backend.database.migration_guards import (
    add_column_if_missing,
    create_index_if_missing,
    create_table_if_missing,
)



revision = '9c1d47f0be31'
down_revision = '6704ce3e211d'
branch_labels = None
depends_on = None


def upgrade():
    add_column_if_missing('face_clusters', sa.Column('trained_at', sa.DateTime(), nullable=True))

    # Backfill: a cluster that carries a label and is marked identified went
    # through the promotion path, which is the only thing that sets both.
    op.execute(
        "UPDATE face_clusters "
        "SET trained_at = COALESCE(updated_at, created_at) "
        "WHERE is_identified = 1 AND label IS NOT NULL AND label != ''"
    )


def downgrade():
    with op.batch_alter_table('face_clusters') as batch_op:
        batch_op.drop_column('trained_at')
