# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

import os

# Disable endpoint rate limiting for the whole suite BEFORE importing backend.main:
# the middleware reads this once when the app is constructed at import time. API
# tests legitimately fire many requests at one endpoint within seconds, which the
# limiter would (correctly) throttle — producing 429s that look like assertion
# failures and have nothing to do with what is under test. The limiter's own unit
# tests pass enabled=True explicitly so the throttling path is still covered.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database.session import Base
from backend.database import models
from backend.database import alert_models  # Import alert models to register them
from backend.database.models import RefreshToken  # Explicitly import to register
from backend.main import app
from backend.database.session import get_db


@pytest.fixture(scope="session")
def engine():
    # session-scoped engine for fast tests; use in-memory SQLite
    # CRITICAL: Use StaticPool to ensure all connections use the SAME in-memory database
    # Without this, each connection gets its own separate in-memory database
    from sqlalchemy.pool import StaticPool
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )


@pytest.fixture
def db_session(engine):
    # create fresh schema for each test function
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """FastAPI test client with overridden database dependency"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # CRITICAL FIX: Disable startup/shutdown events during testing
    # Startup events load cameras and create database sessions via get_db_context()
    # which bypasses dependency injection and accesses production database
    original_startup = app.router.on_startup.copy()
    original_shutdown = app.router.on_shutdown.copy()
    app.router.on_startup.clear()
    app.router.on_shutdown.clear()

    try:
        with TestClient(app, raise_server_exceptions=True) as test_client:
            yield test_client
    finally:
        # Restore original event handlers
        app.router.on_startup = original_startup
        app.router.on_shutdown = original_shutdown
        app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """Create a test user for authentication tests"""
    from backend.database import crud
    from backend.api.schemas import user as user_schema

    user_data = user_schema.UserCreate(
        username="testuser",
        password="testpass123",
        email="test@example.com"
    )
    user = crud.create_user(db=db_session, user=user_data)
    return user


@pytest.fixture
def auth_headers(client, test_user):
    """Generate authentication headers with valid JWT token"""
    response = client.post(
        "/api/auth/login-2fa",
        json={"username": "testuser", "password": "testpass123"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_camera(db_session):
    """Create a test camera in the database"""
    camera = models.Camera(
        camera_id="test_camera_1",
        camera_type="mock",
        source="mock",
        is_active=True,
        motion_detection_enabled=True,
        face_detection_enabled=True,
        recording_enabled=False
    )
    db_session.add(camera)
    db_session.commit()
    db_session.refresh(camera)
    return camera


@pytest.fixture
def patch_hashing_if_needed(monkeypatch):
    """
    Optional fixture for CI environments where bcrypt/passlib isn't available.
    Use by naming `patch_hashing_if_needed` in your test signature. It will replace
    get_password_hash and verify_password with simple deterministic functions.
    """
    try:
        # try importing real functions; if present, do nothing
        from backend.core.security import get_password_hash as _get_hash  # noqa: F401
        from backend.core.security import verify_password as _verify  # noqa: F401
        return
    except Exception:
        import backend.database.crud as crud_mod
        import backend.core.auth as auth_mod

        monkeypatch.setattr(crud_mod, 'get_password_hash', lambda p: 'hashed-' + p)
        monkeypatch.setattr(auth_mod, 'verify_password', lambda plain, hashed: hashed == 'hashed-' + plain)
        return
