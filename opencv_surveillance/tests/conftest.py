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
        password="Testpass123!",
        email="test@example.com"
    )
    user = crud.create_user(db=db_session, user=user_data)
    return user


@pytest.fixture(autouse=True)
def no_real_camera_io(monkeypatch):
    """
    Stop tests from opening real cameras or network streams.

    POST /api/cameras calls camera_manager.add_camera(), which constructs a capture
    and connects. test_create_camera posts source "rtsp://example.com/stream", so the
    request blocked inside OpenCV's RTSP connect and the test never returned — the
    suite hung indefinitely and only a per-test timeout revealed which test was at
    fault. In CI that meant a runner held open with no useful output.

    A unit test asserting "POST /cameras creates a record and returns it" has no
    business dialling a camera, so add_camera is stubbed to report success without
    touching hardware or the network. Tests that genuinely exercise camera_manager
    should patch it explicitly with the behaviour they need.
    """
    # The singleton is exported as `manager`; the routes alias it on import
    # (`from backend.core.camera_manager import manager as camera_manager`). Import it
    # by its real name and let an ImportError surface — silently skipping the patch
    # is how this stub appeared to work while the suite kept hanging.
    from backend.core.camera_manager import manager as camera_manager

    # The create route does not just call add_camera — it then looks the camera up and
    # checks `is_running` to confirm it started. A stub that only reports success
    # leaves that lookup empty and the endpoint fails with a 500, so record the camera
    # and hand back a minimal running stand-in.
    class _StubCamera:
        def __init__(self, camera_id):
            self.camera_id = camera_id
            self.is_running = True

    stubbed = {}
    real_get_camera = camera_manager.get_camera

    def _fake_add_camera(camera_id, camera_type="mock", source=None,
                         enable_face_detection=False, *args, **kwargs):
        stubbed[camera_id] = _StubCamera(camera_id)
        return True, f"Camera '{camera_id}' added (stubbed in tests)"

    def _fake_get_camera(camera_id, *args, **kwargs):
        if camera_id in stubbed:
            return stubbed[camera_id]
        return real_get_camera(camera_id, *args, **kwargs)

    monkeypatch.setattr(camera_manager, "add_camera", _fake_add_camera)
    monkeypatch.setattr(camera_manager, "get_camera", _fake_get_camera)
    yield


@pytest.fixture(autouse=True)
def isolate_storage_paths(tmp_path, monkeypatch):
    """
    Redirect all storage paths at a per-test temp directory.

    The faces API is filesystem-backed (a person is a directory under faces_dir), so
    without this the suite wrote into the developer's REAL data directory: running the
    tests left a stray "John Doe" person in ~/.local/share/openeye/faces, which then
    leaked into later tests — "list people when none exist" found one. Tests must
    never touch real user data, and must not depend on execution order.

    Autouse so every test is isolated by default rather than relying on each author
    remembering to opt in.
    """
    from backend.core.paths import paths

    for attr in ("data_dir", "faces_dir", "recordings_dir",
                 "snapshots_dir", "thumbnails_dir"):
        if hasattr(paths, attr):
            target = tmp_path / attr.replace("_dir", "")
            target.mkdir(parents=True, exist_ok=True)
            monkeypatch.setattr(paths, attr, target, raising=False)
    yield


@pytest.fixture
def admin_user(db_session):
    """
    Create an ADMIN user.

    The default role for a new user is `viewer`, so the plain `test_user` fixture is
    correctly refused (403) by anything guarded with require_user/require_admin —
    uploads, deletions, model training. Tests that mean to exercise those endpoints
    need a privileged identity; tests that mean to check the authorisation boundary
    should keep using the viewer fixture.
    """
    from backend.database import crud
    from backend.api.schemas import user as user_schema

    user = crud.create_user(
        db=db_session,
        user=user_schema.UserCreate(
            username="adminuser",
            password="Adminpass123!",
            email="admin@example.com",
        ),
    )
    user.role = "admin"
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_auth_headers(client, admin_user):
    """Authentication headers for an admin user."""
    response = client.post(
        "/api/auth/login-2fa",
        json={"username": "adminuser", "password": "Adminpass123!"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth_headers(client, test_user):
    """Generate authentication headers with valid JWT token"""
    response = client.post(
        "/api/auth/login-2fa",
        json={"username": "testuser", "password": "Testpass123!"}
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
