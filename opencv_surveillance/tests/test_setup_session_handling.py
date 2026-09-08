# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
The setup routes must not leak database connections.

Both took their session with `db = next(get_db())`. That pulls the session out
of the generator dependency and abandons it: the generator's
`finally: db.close()` never runs, so the connection is never returned to the
pool.

The shape is what makes it serious. The login page calls GET /api/setup/status
on every load and it requires no authentication, so it leaked one connection per
page view until the pool was exhausted — at which point every request blocks,
with nothing in the logs pointing at the cause. main.py was audited for exactly
this pattern in v3.6.0.1; these two sites were missed.
"""

import pathlib
import re

import pytest


SETUP = pathlib.Path(__file__).resolve().parents[1] / "backend/api/routes/setup.py"


def test_no_route_pulls_a_session_from_the_generator():
    """
    `next(get_db())` is the defect, and it is invisible at runtime — the
    endpoint works perfectly until the pool runs out.

    Checked with the AST rather than by searching the text: the docstrings in
    setup.py name the old pattern in order to explain why it went, and a
    substring search flags that prose. It did on first run.
    """
    import ast

    tree = ast.parse(SETUP.read_text())
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # next(...)
        if not (isinstance(node.func, ast.Name) and node.func.id == "next"):
            continue
        if not node.args:
            continue
        inner = node.args[0]
        # ...where the argument is itself a call to get_db()
        if isinstance(inner, ast.Call) and getattr(inner.func, "id", "") == "get_db":
            offenders.append(f"line {node.lineno}")

    assert not offenders, (
        "setup.py takes a session out of the generator and abandons it at "
        + ", ".join(offenders)
    )


def test_the_routes_declare_the_session_as_a_dependency():
    text = SETUP.read_text()
    assert text.count("db: Session = Depends(get_db)") >= 2, (
        "both setup routes should receive the session as a dependency"
    )


def test_status_works_and_is_unauthenticated(client):
    """It is called by the login page before anyone can have a token."""
    response = client.get("/api/setup/status")
    assert response.status_code == 200
    assert "setup_complete" in response.json()


def test_status_can_be_called_repeatedly(client):
    """
    The leak showed up under repetition, so exercise it.

    With a pooled engine this exhausts the pool once the connections are
    abandoned; the assertion is simply that every call still succeeds.
    """
    for _ in range(30):
        assert client.get("/api/setup/status").status_code == 200


def test_initialize_does_not_leak_exception_text(client, monkeypatch):
    """
    Unauthenticated endpoint: an unexpected failure must not return internals.

    Forced rather than provoked. The first version of this test assumed the
    `test_user` fixture would make setup refuse — it does not, because that
    user's role is "user" and the route only refuses when an ADMIN exists. It
    got a 200 and proved nothing.
    """
    import backend.api.routes.setup as setup_module

    secret = "sqlite:////srv/openeye/data/surveillance.db"

    class Exploding:
        def query(self, *a, **k):
            raise RuntimeError(f"connection failed: {secret}")
        def rollback(self):
            pass

    monkeypatch.setattr(
        setup_module, "get_db", lambda: iter([Exploding()]), raising=True)
    from backend.database.session import get_db as real_get_db
    client.app.dependency_overrides[real_get_db] = lambda: Exploding()
    try:
        response = client.post(
            "/api/setup/initialize",
            json={"username": "someone", "email": "a@b.com",
                  "password": "Abcdef123!"},
        )
    finally:
        client.app.dependency_overrides.pop(real_get_db, None)

    assert response.status_code == 500
    body = response.text
    assert secret not in body, "the 500 body leaked the database path"
    assert "connection failed" not in body
    assert "Traceback" not in body
    assert "See the server log" in body
