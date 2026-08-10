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

DEFAULT_DATABASE_PATH = APP_ROOT / "surveillance.db"


def _resolve_database_url() -> str:
    """
    Work out which database to open, preferring explicit configuration.

    DATABASE_URL was previously ignored outright, so an installer that set it
    was quietly overruled. It is honoured now, with two guards: a relative
    SQLite path is resolved against the application root rather than the
    working directory, and a configured file that does not exist while a real
    database sits at the default location is refused in favour of the real one.

    That second guard exists because the failure it prevents is invisible.
    Opening the wrong SQLite path does not error — it creates an empty database
    and every camera, face and recording simply appears to be gone.
    """
    configured = (os.getenv("DATABASE_URL") or "").strip()

    if not configured:
        return f"sqlite:///{DEFAULT_DATABASE_PATH}"

    if not configured.startswith("sqlite:"):
        # Postgres, MySQL and friends have no filesystem semantics to correct.
        return configured

    prefix, _, raw_path = configured.partition("///")
    if not raw_path:
        return configured

    path = Path(raw_path)
    if not path.is_absolute():
        path = APP_ROOT / path

    path = Path(os.path.normpath(str(path)))

    if not path.exists() and DEFAULT_DATABASE_PATH.exists():
        logger.critical(
            "Configured database %s does not exist, but a database is present at "
            "%s. Using the existing database rather than creating an empty one. "
            "Correct DATABASE_URL to remove this warning.",
            path, DEFAULT_DATABASE_PATH,
        )
        path = DEFAULT_DATABASE_PATH

    return f"{prefix}///{path}"


SQLALCHEMY_DATABASE_URL = _resolve_database_url()

# CRITICAL FIX (2025-10-25): Use NullPool for SQLite to prevent connection issues
# Root cause: 25+ SessionLocal() calls in background threads don't properly close sessions
# NullPool creates fresh connection per request - perfect for SQLite with concurrent requests
# FIXED: 16 session leaks eliminated with context managers (see database/utils.py)
from sqlalchemy.pool import NullPool

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=NullPool,  # Creates new connection per request (prevents thread safety issues)
    echo=False  # Set to True for SQL debugging
)
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
