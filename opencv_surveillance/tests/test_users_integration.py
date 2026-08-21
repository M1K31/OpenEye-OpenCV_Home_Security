from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import users
from backend.core import auth
from backend.database.session import get_db


def test_create_user_route(db_session, patch_hashing_if_needed):
    """
    Creating a user through the router returns the new user.

    The app built here MUST override get_db. Without it the router resolved the real
    session factory and this test wrote "intuser" into the developer's actual
    surveillance.db: the first run passed, and every run afterwards failed with 400
    "Username already registered" because the row was still there. The failure looked
    like a broken endpoint when it was leftover state from the previous run.
    """
    app = FastAPI()
    app.include_router(users.router, prefix="/api", tags=["users"])
    app.dependency_overrides[get_db] = lambda: db_session

    # Account creation became admin-only on 2026-08-20 — it was previously
    # reachable with no credentials, which let anyone on the network add accounts
    # to an installed system. This test covers the creation logic, not the
    # authorization check (test_route_authorization.py owns that), so satisfy the
    # dependency with a stand-in administrator.
    app.dependency_overrides[auth.require_admin] = lambda: SimpleNamespace(
        id=1, username="admin", role="admin", is_active=True
    )

    client = TestClient(app)

    payload = {"username": "intuser", "email": "int@example.com", "password": "Secret1!"}
    resp = client.post("/api/users/", json=payload)
    assert resp.status_code in (200, 201), resp.text
    body = resp.json()
    assert body.get("username") == "intuser"
    assert "id" in body


def test_create_user_route_rejects_anonymous_callers(db_session, patch_hashing_if_needed):
    """An unauthenticated caller must not be able to create an account."""
    app = FastAPI()
    app.include_router(users.router, prefix="/api", tags=["users"])
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)

    resp = client.post(
        "/api/users/",
        json={"username": "sneaky", "email": "s@example.com", "password": "Secret1!"},
    )
    assert resp.status_code in (401, 403), resp.text
