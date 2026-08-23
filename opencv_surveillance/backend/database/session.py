# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
import logging
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# The application root — the directory holding backend/, frontend/, and the
# installed data beside them. Derived from this file's own location, so it is
# the same directory no matter what working directory the process was started
# in. That property is the whole point: this module used to hardcode
# "sqlite:///./surveillance.db", a working-directory-relative URL, and the app
# only ever found its 74 MB database because the start script happened to cd
# into the app directory first. Launched any other way — a launch agent, a
# systemd unit, a login item, none of which inherit a shell's working directory
# — SQLite would create a brand new empty file elsewhere and the app would come
# up looking like a fresh install, with no error anywhere.
APP_ROOT = Path(__file__).resolve().parent.parent.parent


def _data_root() -> Path:
    """
    The directory this installation writes to.

    Imported lazily and defensively: session.py is imported extremely early, and
    a database that cannot be located because a path helper failed to import
    would be a much worse failure than falling back to the application root.
    """
    try:
        from backend.core.paths import DATA_ROOT

        return Path(DATA_ROOT)
    except Exception:  # pragma: no cover - defensive
        return APP_ROOT


DATA_ROOT = _data_root()

# The database is writable state, so it belongs with the rest of it. In a source
# checkout the data root *is* the application root, so this is unchanged for
# developers.
DEFAULT_DATABASE_PATH = DATA_ROOT / "surveillance.db"

# Where installs created before the data root existed keep their database.
# Checked so an upgrade adopts the real database instead of starting empty.
LEGACY_DATABASE_PATH = APP_ROOT / "surveillance.db"


def _resolve_database_url() -> str:
    """
    Work out which database to open, preferring explicit configuration.

    DATABASE_URL was previously ignored outright, so an installer that set it
    was quietly overruled. It is honoured now, with two guards: a relative
    SQLite path is resolved against the data root rather than the working
    directory, and a configured file that does not exist while a real database
    sits at a known location is refused in favour of the real one.

    That second guard exists because the failure it prevents is invisible.
    Opening the wrong SQLite path does not error — it creates an empty database
    and every camera, face and recording simply appears to be gone. It checks the
    pre-data-root location too, so an install being upgraded adopts its existing
    database instead of silently starting over.
    """
    configured = (os.getenv("DATABASE_URL") or "").strip()

    if not configured:
        # An install predating the data root keeps its database beside the code.
        # Adopt it rather than starting empty; the migration moves it later.
        if not DEFAULT_DATABASE_PATH.exists() and LEGACY_DATABASE_PATH.exists():
            logger.warning(
                "Using the database at %s. It predates the data root at %s and "
                "will be moved there by the storage migration.",
                LEGACY_DATABASE_PATH, DATA_ROOT,
            )
            return f"sqlite:///{LEGACY_DATABASE_PATH}"
        return f"sqlite:///{DEFAULT_DATABASE_PATH}"

    if not configured.startswith("sqlite:"):
        # Postgres, MySQL and friends have no filesystem semantics to correct.
        return configured

    prefix, _, raw_path = configured.partition("///")
    if not raw_path:
        return configured

    path = Path(raw_path)
    if not path.is_absolute():
        path = DATA_ROOT / path

    path = Path(os.path.normpath(str(path)))

    if not path.exists():
        for fallback in (DEFAULT_DATABASE_PATH, LEGACY_DATABASE_PATH):
            if fallback.exists() and fallback != path:
                logger.critical(
                    "Configured database %s does not exist, but a database is "
                    "present at %s. Using the existing database rather than "
                    "creating an empty one. Correct DATABASE_URL to remove this "
                    "warning.", path, fallback,
                )
                return f"{prefix}///{fallback}"

    return f"{prefix}///{path}"


SQLALCHEMY_DATABASE_URL = _resolve_database_url()

# CRITICAL FIX (2025-10-25): Use NullPool for SQLite to prevent connection issues
# Root cause: 25+ SessionLocal() calls in background threads don't properly close sessions
# NullPool creates fresh connection per request - perfect for SQLite with concurrent requests
# FIXED: 16 session leaks eliminated with context managers (see database/utils.py)
from sqlalchemy.pool import NullPool

def engine_kwargs_for(url: str) -> dict:
    """
    Engine arguments appropriate to the database in `url`.

    These used to be applied unconditionally, which made PostgreSQL unusable.
    `check_same_thread` is a SQLite driver option; psycopg2 rejects it outright —
    `invalid dsn: invalid connection option "check_same_thread"` — so every
    connection attempt failed. `DATABASE_URL` accepts a `postgresql://` URL and
    `.env.example` documents PostgreSQL as the production option, so this was a
    documented path that could not work.

    NullPool is likewise SQLite-specific here. It exists because 25+ background
    threads open sessions and SQLite tolerates that badly; applying it to
    PostgreSQL would throw away connection pooling for no benefit.
    """
    if url.startswith("sqlite"):
        return {
            # SQLite refuses cross-thread use by default; the server is threaded.
            "connect_args": {"check_same_thread": False},
            # A fresh connection per request, rather than sharing one across
            # background threads.
            "poolclass": NullPool,
            "echo": False,
        }

    # PostgreSQL and anything else: driver defaults, with real pooling.
    return {"echo": False}


engine = create_engine(SQLALCHEMY_DATABASE_URL, **engine_kwargs_for(SQLALCHEMY_DATABASE_URL))


def apply_sqlite_pragmas(target_engine) -> bool:
    """
    Configure SQLite for concurrent readers and writers. No-op for other engines.

    Measured on the live database 2026-08-22: `journal_mode = delete` — the
    default rollback journal — and no pragma set anywhere in the codebase.

    Under that journal a writer takes an exclusive lock over the whole database,
    so readers block the writer and the writer blocks readers. OpenEye writes
    continuously from camera threads (motion events, face detections, recording
    rows) while the dashboard reads. A single camera masks this. A second camera
    doubles the write rate and adds a second writer, which is where
    "database is locked" starts appearing — and it would look like a fault in
    whatever was added last rather than a storage setting.

    Returns True if the pragmas were installed.

    Set on every new connection because busy_timeout and synchronous are
    per-connection, and the engine uses NullPool, so every session opens a fresh
    one. journal_mode is a property of the database FILE and persists once set,
    but is issued here too so a fresh install is correct without a migration.

    Not enabled here, deliberately: `foreign_keys=ON`. SQLite does not enforce
    foreign keys unless asked, so this database has never had them enforced, and
    turning them on could start rejecting writes that reference rows which are
    already missing. That needs an audit of existing data first — recorded in
    todos_changelog.md rather than done quietly as part of a performance change.
    """
    if not target_engine.url.drivername.startswith("sqlite"):
        return False

    from sqlalchemy import event

    @event.listens_for(target_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        try:
            # Readers no longer block the writer, and the writer no longer
            # blocks readers.
            cursor.execute("PRAGMA journal_mode=WAL")
            # Wait for a contended lock rather than failing instantly.
            cursor.execute(
                f"PRAGMA busy_timeout={int(os.getenv('OPENEYE_SQLITE_BUSY_TIMEOUT_MS', '10000'))}")
            # The standard companion to WAL: durable across an application
            # crash, trading only a power-loss window that an appliance already
            # accepts for its video files.
            cursor.execute("PRAGMA synchronous=NORMAL")
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("Could not apply SQLite pragmas: %s", e)
        finally:
            cursor.close()

    return True


if apply_sqlite_pragmas(engine):
    logger.info("SQLite configured for concurrent access (WAL, busy_timeout, synchronous=NORMAL)")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Dependency for FastAPI routes
def get_db():
    """
    Database session dependency for FastAPI.
    Yields a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
