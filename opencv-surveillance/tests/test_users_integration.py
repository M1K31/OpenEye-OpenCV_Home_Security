from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes import users


def test_create_user_route(db_session, patch_hashing_if_needed):
    app = FastAPI()
    app.include_router(users.router, prefix="/api", tags=["users"])

    client = TestClient(app)

    payload = {"username": "intuser", "email": "int@example.com", "password": "secret"}
    resp = client.post("/api/users/", json=payload)
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body.get("username") == "intuser"
    assert "id" in body
