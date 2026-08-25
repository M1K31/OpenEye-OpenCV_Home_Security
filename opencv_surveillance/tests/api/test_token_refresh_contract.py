# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
The refresh token travels in the request body.

The defect
----------
Both endpoints declared it directly in the signature:

    def refresh_token(..., refresh_token: str, db: Session = Depends(get_db)):

FastAPI reads a bare `str` that is not a path parameter as a QUERY parameter.
The browser client sends JSON — `{"refresh_token": "..."}` — which is also what
the endpoint's own docstring described ("in request body"), so every call was
answered with 422. Confirmed from the application log: three refresh attempts
across three sessions, every one a 422, never a single success.

What that meant in practice:

- **Refresh never worked.** A session could not be extended, so the client hit
  `handleAuthFailure()` and logged the user out once the access token expired.
- **Revoke never worked either.** Logout catches the failure and continues, so
  the refresh token was never revoked server-side — it stayed valid until it
  expired on its own, which is the opposite of what logging out should mean.

Neither failure was visible: one looks like an ordinary session timeout, the
other is silent by design.

Nothing tested the request contract. The route was covered for authorisation and
for CSRF exemption — both of which passed while the endpoint could not be called
at all. These tests check the shape of the request instead.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestTheTokenIsReadFromTheBody:
    """
    Asserted against the route definition rather than by calling the endpoint,
    so the check holds without a valid token or a database.
    """

    def _route(self, path):
        for route in _walk(app.routes):
            if getattr(route, "path", "").endswith(path):
                return route
        pytest.fail(f"no route ending in {path}")

    @pytest.mark.parametrize("path", ["/token/refresh", "/token/revoke"])
    def test_the_token_is_not_a_query_parameter(self, path):
        """
        The regression itself.

        A refresh token in a query string is also wrong on its own terms: query
        strings are written to server and proxy logs and kept in browser
        history, which is not where a credential belongs.
        """
        route = self._route(path)
        query_names = [p.name for p in route.dependant.query_params]

        assert "refresh_token" not in query_names, (
            f"{path} reads the refresh token from the query string; "
            "the client sends it as JSON, so every call is rejected with 422"
        )

    @pytest.mark.parametrize("path", ["/token/refresh", "/token/revoke"])
    def test_the_endpoint_declares_a_body(self, path):
        route = self._route(path)
        assert route.dependant.body_params, f"{path} declares no request body"


class TestTheRequestShapeIsAccepted:
    """
    Exercises the endpoint for real. A wrong token must be REFUSED (401), not
    MISUNDERSTOOD (422) — the distinction that was missing.
    """

    @pytest.mark.parametrize("path", ["/api/token/refresh", "/api/token/revoke"])
    def test_a_json_body_is_understood(self, client, path):
        response = client.post(path, json={"refresh_token": "not-a-real-token"})

        assert response.status_code != 422, (
            f"{path} rejected the shape the client sends: {response.text[:200]}"
        )

    def test_an_empty_body_is_still_a_validation_error(self, client):
        """The endpoint must still require the field — this is not a free pass."""
        response = client.post("/api/token/refresh", json={})
        assert response.status_code == 422


def _walk(routes, prefix=""):
    """
    Yields routes through included routers.

    Starlette 1.x keeps each include as one opaque entry rather than flattening
    it, so a flat scan of app.routes finds neither of these endpoints.
    """
    for route in routes:
        if type(route).__name__ == "_IncludedRouter":
            context = getattr(route, "include_context", None)
            child = getattr(route, "original_router", None)
            if child is None:
                continue
            yield from _walk(child.routes, prefix + (getattr(context, "prefix", "") or ""))
        else:
            yield route
