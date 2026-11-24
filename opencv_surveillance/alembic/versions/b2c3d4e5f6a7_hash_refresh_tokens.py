"""store refresh tokens as a digest, not in the clear

A refresh token is a bearer credential: whoever holds it can mint access tokens
until it expires. They were stored verbatim, so the database was a file of live
credentials — and backup.py archives that database, which made every backup
archive able to resume every active session for up to REFRESH_TOKEN_EXPIRE_DAYS,
bypassing both the password and 2FA.

Existing rows cannot be converted: a digest cannot be derived from a value we no
longer keep, and keeping the plaintext to convert it would defeat the change.
They are deleted, so every session signs in once after this upgrade. That is
also the point — it invalidates any token already sitting in a backup taken
before this ran.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def _columns(table):
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade():
    columns = _columns("refresh_tokens")

    # A fresh database gets the table from create_all() with the new column
    # already in place, so there is nothing to rename. Only an upgraded one
    # reaches the body below. Guarding on the column rather than the table
    # keeps this re-runnable, matching the other migrations in this tree.
    if not columns or "token_hash" in columns:
        return

    # Delete first, and unconditionally. The rename below only changes the
    # column's name and width, so any surviving row would keep its plaintext
    # value sitting in a column now labelled as a digest — the worst outcome
    # available, because every later reader would trust the label. Emptying the
    # table is what makes the rename honest.
    op.execute(sa.text("DELETE FROM refresh_tokens"))

    # batch_alter_table because SQLite cannot rename or retype a column in
    # place; alembic recreates the table and copies the (now empty) contents.
    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.alter_column(
            "token",
            new_column_name="token_hash",
            existing_type=sa.String(length=512),
            type_=sa.String(length=64),   # sha256, hex-encoded
            existing_nullable=False,
        )


def downgrade():
    columns = _columns("refresh_tokens")
    if not columns or "token" in columns:
        return

    # Reversing the schema cannot reverse the security property: the digests
    # are one-way, so there are no tokens to restore. Empty the table again
    # rather than leave digests in a column that means plaintext.
    op.execute(sa.text("DELETE FROM refresh_tokens"))

    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.alter_column(
            "token_hash",
            new_column_name="token",
            existing_type=sa.String(length=64),
            type_=sa.String(length=512),
            existing_nullable=False,
        )
