# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./surveillance.db"

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
