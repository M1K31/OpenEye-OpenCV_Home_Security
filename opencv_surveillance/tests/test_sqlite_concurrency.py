# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
SQLite must be configured for concurrent readers and writers.

Background
----------
Measured on the live database 2026-08-22: `journal_mode = delete`, the default
rollback journal, and no pragma set anywhere in the codebase.

Under that journal a writer takes an exclusive lock over the whole database, so
readers block writers and writers block readers. OpenEye writes continuously
from camera threads — motion events, face detections, recording rows — while the
dashboard reads. One camera has masked this. A second camera roughly doubles the
write rate and adds a second writer, which is where `database is locked` starts
appearing.

WAL changes that: readers do not block the writer and the writer does not block
readers. `busy_timeout` makes a contending connection wait rather than fail
immediately, and `synchronous=NORMAL` is the standard companion to WAL — durable
across application crashes, trading only a power-loss window that a surveillance
appliance already accepts for its video files.

These are set on every new connection because `busy_timeout` and `synchronous`
are per-connection. `journal_mode` is a property of the database file and
persists, but is set here too so a fresh install gets it without a migration.
"""

import sqlite3

import pytest
from sqlalchemy import create_engine, text

from backend.database.session import apply_sqlite_pragmas


@pytest.fixture
def sqlite_engine(tmp_path):
    """A real file-backed SQLite engine — in-memory databases cannot use WAL."""
    db = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db}", connect_args={"check_same_thread": False})
    apply_sqlite_pragmas(engine)
    return engine


def test_journal_mode_is_wal(sqlite_engine):
    """The whole point: readers must not block the writer."""
    with sqlite_engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
    assert mode.lower() == "wal", f"expected WAL, got {mode!r}"


def test_busy_timeout_is_set(sqlite_engine):
    """
    A contending connection should wait, not fail instantly.

    Without this, a write that arrives while another is in flight raises
    'database is locked' immediately rather than waiting the moment it takes for
    the other to finish.
    """
    with sqlite_engine.connect() as conn:
        timeout = conn.execute(text("PRAGMA busy_timeout")).scalar()
    assert timeout >= 5000, f"busy_timeout too low: {timeout}ms"


def test_synchronous_is_normal(sqlite_engine):
    """NORMAL is the correct companion to WAL: durable on crash, much faster."""
    with sqlite_engine.connect() as conn:
        sync = conn.execute(text("PRAGMA synchronous")).scalar()
    assert sync == 1, f"expected synchronous=NORMAL (1), got {sync}"


def test_pragmas_apply_to_every_new_connection(sqlite_engine):
    """
    Per-connection settings must survive pooling.

    The engine uses NullPool, so every session opens a fresh connection. A
    pragma applied only once at startup would protect the first connection and
    nothing else.
    """
    for _ in range(3):
        with sqlite_engine.connect() as conn:
            assert conn.execute(text("PRAGMA busy_timeout")).scalar() >= 5000
            assert conn.execute(text("PRAGMA synchronous")).scalar() == 1


def test_a_reader_does_not_block_a_writer(tmp_path):
    """
    The behaviour all of this exists for, demonstrated rather than asserted.

    Under the default rollback journal an open read transaction blocks a writer.
    Under WAL it does not. Two raw connections are used so the test exercises
    SQLite itself rather than SQLAlchemy's session handling.
    """
    db = tmp_path / "concurrent.db"
    engine = create_engine(f"sqlite:///{db}", connect_args={"check_same_thread": False})
    apply_sqlite_pragmas(engine)

    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE events (id INTEGER PRIMARY KEY, note TEXT)"))
        conn.execute(text("INSERT INTO events (note) VALUES ('first')"))
        conn.commit()

    reader = sqlite3.connect(str(db), timeout=5)
    writer = sqlite3.connect(str(db), timeout=5)
    try:
        # Hold an open read transaction, as the dashboard does while listing.
        reader.execute("BEGIN")
        reader.execute("SELECT * FROM events").fetchall()

        # A camera thread writing while that read is open must succeed.
        writer.execute("INSERT INTO events (note) VALUES ('during-read')")
        writer.commit()
    finally:
        reader.close()
        writer.close()


def test_non_sqlite_engines_are_left_alone():
    """
    PostgreSQL must not be handed SQLite pragmas.

    The project documents PostgreSQL as the path beyond a handful of cameras, so
    this configuration has to be a no-op there rather than an error.
    """
    engine = create_engine("postgresql://user:pass@localhost/does_not_exist")
    # Must not raise, and must not attach a listener that would fire on connect.
    apply_sqlite_pragmas(engine)


# ---------------------------------------------------------------------------
# Engine construction must suit the database being opened.
# ---------------------------------------------------------------------------

def test_sqlite_gets_sqlite_specific_connect_args():
    """check_same_thread is required for SQLite under a threaded server."""
    from backend.database.session import engine_kwargs_for

    kwargs = engine_kwargs_for("sqlite:////tmp/x.db")
    assert kwargs["connect_args"].get("check_same_thread") is False
    assert kwargs.get("poolclass") is not None, "SQLite needs NullPool"


def test_postgres_is_not_given_sqlite_arguments():
    """
    PostgreSQL must not receive check_same_thread.

    psycopg2 rejects it outright — `invalid dsn: invalid connection option
    "check_same_thread"` — so every connection attempt failed. DATABASE_URL
    accepts a postgresql:// URL and .env.example documents it as the production
    option, so this was a documented path that could not work.

    NullPool is also dropped: it exists to keep SQLite's single-writer model out
    of trouble, and using it with PostgreSQL discards connection pooling for no
    benefit.
    """
    kwargs = __import__(
        "backend.database.session", fromlist=["engine_kwargs_for"]
    ).engine_kwargs_for("postgresql://user:pass@localhost/openeye")

    assert "check_same_thread" not in kwargs.get("connect_args", {})
    assert "poolclass" not in kwargs, "PostgreSQL should keep normal pooling"


def test_the_rejected_argument_is_actually_rejected_by_the_driver():
    """
    Pins why this matters, rather than asserting a dict shape in the abstract.

    If a future change reintroduces the argument, this documents the exact
    failure it causes.
    """
    psycopg2 = __import__("pytest").importorskip("psycopg2")
    with __import__("pytest").raises(psycopg2.ProgrammingError, match="check_same_thread"):
        psycopg2.connect(
            host="127.0.0.1", port=59999, dbname="x", user="u", password="p",
            check_same_thread=False,
        )
