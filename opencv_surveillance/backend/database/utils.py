# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Database utility functions and context managers

IMPORTANT: Use these utilities instead of direct SessionLocal() calls
to prevent database session leaks.
"""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session
from .session import SessionLocal
import logging

logger = logging.getLogger(__name__)


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Ensures sessions are properly closed even if exceptions occur.

    Usage:
        with get_db_context() as db:
            # Use db here
            user = db.query(User).first()
            # Session automatically closed when exiting context

    Example (Background Thread):
        def background_task():
            with get_db_context() as db:
                # Safe to use in background threads
                data = db.query(Model).all()
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def execute_with_db(func, *args, **kwargs):
    """
    Execute a function with a database session.

    Useful for simple operations that need a database session.

    Args:
        func: Function to execute (receives db as first argument)
        *args: Additional positional arguments for func
        **kwargs: Additional keyword arguments for func

    Returns:
        Result from func

    Example:
        def get_user_count(db, min_age=18):
            return db.query(User).filter(User.age >= min_age).count()

        count = execute_with_db(get_user_count, min_age=21)
    """
    with get_db_context() as db:
        return func(db, *args, **kwargs)
