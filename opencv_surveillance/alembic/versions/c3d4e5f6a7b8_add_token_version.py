"""give each user a token version, so a password change ends live sessions

Access tokens are bearer credentials that live until they expire — thirty
minutes by default. Changing a password revoked the refresh tokens but could not
reach an access token already issued, so every other signed-in session went on
working for the rest of that window. That is precisely the window somebody
resetting a compromised password is trying to close.

Tokens now carry the version they were issued under and are refused once it no
longer matches.

A counter rather than a "password changed at" timestamp: JWT encodes `iat` as
integer seconds, so a timestamp comparison is ambiguous for the whole second in
which the change lands — reject on equality and a user signing straight back in
is refused, accept on equality and a token issued in that same second survives.
A counter has no such boundary and does not care about clock skew.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def _columns(table):
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade():
    columns = _columns("users")
    # A fresh database gets the column from create_all(); only an upgraded one
    # reaches the body. Guarding on the column keeps this re-runnable, matching
    # the other migrations here.
    if not columns or "token_version" in columns:
        return

    # Defaults to 0 for existing rows, which matches what tokens issued after
    # this point will carry. Starting everyone at a fresh value instead would
    # invalidate every token in flight the moment the migration ran — signing
    # out every user for an upgrade that changed no password.
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    columns = _columns("users")
    if not columns or "token_version" not in columns:
        return
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("token_version")
