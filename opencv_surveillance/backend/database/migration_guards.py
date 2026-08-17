# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Make migrations survive meeting a database that already has the schema.

`main.py` runs `alembic upgrade head` and then `create_all()` as a fallback. On
any install where `create_all()` won mattered — it runs unconditionally, and it
ran before alembic on older versions — tables exist that alembic believes it
still has to create. The next upgrade then dies on "table motion_zones already
exists", every later migration is skipped, and the failure is logged as
"Migration warning (non-critical)".

It is not non-critical. `create_all()` only creates missing TABLES; it will never
add a column to a table that exists. So once the chain breaks, every subsequent
column-addition silently does nothing, and the schema quietly falls behind the
models. That is why `trained_at` had to be added by hand at startup.

These helpers make each operation describe the state it wants rather than the
action it takes, so running a migration against a database that already has the
result is a no-op instead of an error.

Guarded operations are safe to re-run. Unguarded ones are not, so prefer these
in any new migration.
"""

from alembic import op
import sqlalchemy as sa


def _inspector():
    return sa.inspect(op.get_bind())


def table_exists(table: str) -> bool:
    return table in _inspector().get_table_names()


def column_exists(table: str, column: str) -> bool:
    if not table_exists(table):
        return False
    return column in {c["name"] for c in _inspector().get_columns(table)}


def index_exists(table: str, index: str) -> bool:
    if not table_exists(table):
        return False
    return index in {i["name"] for i in _inspector().get_indexes(table)}


def create_table_if_missing(table: str, *columns, **kwargs):
    """`op.create_table`, unless the table is already there."""
    if table_exists(table):
        return None
    return op.create_table(table, *columns, **kwargs)


def add_column_if_missing(table: str, column: sa.Column, **kwargs):
    """
    `op.add_column`, unless the column is already there.

    Skips silently when the table itself is absent: a column addition for a
    table that does not exist is either a migration that has not run yet or one
    whose table was dropped, and failing here would break the chain for
    everything after it.
    """
    if not table_exists(table) or column_exists(table, column.name):
        return None
    return op.add_column(table, column, **kwargs)


def create_index_if_missing(index: str, table: str, columns, **kwargs):
    if not table_exists(table) or index_exists(table, index):
        return None
    return op.create_index(index, table, columns, **kwargs)


def drop_column_if_present(table: str, column: str, **kwargs):
    """For downgrades, which meet the same problem from the other direction."""
    if not column_exists(table, column):
        return None
    return op.drop_column(table, column, **kwargs)


def drop_table_if_present(table: str, **kwargs):
    if not table_exists(table):
        return None
    return op.drop_table(table, **kwargs)
