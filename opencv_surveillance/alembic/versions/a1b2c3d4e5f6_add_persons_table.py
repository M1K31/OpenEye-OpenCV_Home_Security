"""add persons table and person_id references

Gives a person an identity of their own. Until now a person existed only as a
repeated string in three unlinked places — a gallery folder name, a cluster
label, and person_name on every detection — which is why renaming had to sweep
three stores and still missed rows.

Adds the table and the foreign keys only. person_name stays populated, so
behaviour is unchanged; the backfill that creates rows from existing names is a
separate, previewable step (backend/core/person_migration.py) rather than
something that happens silently during an upgrade.

Revision ID: a1b2c3d4e5f6
Revises: 9c1d47f0be31
"""
from alembic import op
import sqlalchemy as sa

from backend.database.migration_guards import (
    add_column_if_missing,
    create_index_if_missing,
    create_table_if_missing,
)

revision = 'a1b2c3d4e5f6'
down_revision = '9c1d47f0be31'
branch_labels = None
depends_on = None


def upgrade():
    create_table_if_missing(
        'persons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        # 'cluster' or 'user'. Recorded rather than inferred from the name.
        sa.Column('origin', sa.String(), nullable=False, server_default='cluster'),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    create_index_if_missing('ix_persons_name', 'persons', ['name'], unique=True)

    # Nullable, and no foreign-key constraint on SQLite: adding one to an
    # existing table requires a full table rebuild, and the reference is
    # enforced in application code either way.
    add_column_if_missing('face_detection_events',
                          sa.Column('person_id', sa.Integer(), nullable=True))
    create_index_if_missing('ix_face_detection_events_person_id',
                            'face_detection_events', ['person_id'])

    add_column_if_missing('face_clusters',
                          sa.Column('person_id', sa.Integer(), nullable=True))
    create_index_if_missing('ix_face_clusters_person_id',
                            'face_clusters', ['person_id'])


def downgrade():
    with op.batch_alter_table('face_clusters') as batch_op:
        batch_op.drop_column('person_id')
    with op.batch_alter_table('face_detection_events') as batch_op:
        batch_op.drop_column('person_id')
    op.drop_table('persons')
