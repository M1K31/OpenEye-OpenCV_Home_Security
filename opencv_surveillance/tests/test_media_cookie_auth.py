# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Media routes must be loadable by the browser after a normal login.

Background
----------
``get_current_user_media`` accepts the JWT from an ``access_token`` cookie
because an ``<img>`` or ``<video>`` tag cannot attach an Authorization header.
Nothing ever set that cookie: the frontend keeps its token in localStorage, so
the fallback never fired and media routes answered 401 to exactly the tags that
needed them.

These tests pin both halves together — the login sets the cookie, and a request
carrying only that cookie is accepted. Testing them separately would let the two
drift apart again, which is how the gap survived this long.
"""

import pytest

from backend.core import auth


def test_login_sets_the_media_cookie(client, test_user):
    """A successful login must hand back an access_token cookie."""
    response = client.post(
        "/api/token",
        data={"username": test_user.username, "password": "Testpass123!"},
    )
    assert response.status_code == 200, response.text

    assert auth.MEDIA_COOKIE_NAME in response.cookies, (
        "login did not set the media cookie; <img>/<video> tags cannot "
        "authenticate without it"
    )


def test_media_cookie_is_httponly_and_samesite_strict(client, test_user):
    """
    The cookie is a credential the browser attaches automatically, so it must be
    unreadable from JavaScript and never sent cross-site. SameSite=Strict is the
    CSRF control for these routes.
    """
    response = client.post(
        "/api/token",
        data={"username": test_user.username, "password": "Testpass123!"},
    )
    assert response.status_code == 200, response.text

    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "httponly" in set_cookie, f"media cookie is not HttpOnly: {set_cookie}"
    assert "samesite=strict" in set_cookie, f"media cookie is not SameSite=Strict: {set_cookie}"


@pytest.mark.parametrize(
    "path",
    [
        "/api/snapshots/nope.jpg",
        "/faces/nope.jpg",
        "/recordings/nope.mp4",
        "/data/thumbnails/nope.jpg",
    ],
)
def test_media_routes_accept_the_cookie(client, test_user, path):
    """
    With the cookie present, a media route must get past authentication.

    404 is the pass condition, not 200: these filenames do not exist, and 404
    means the request was authenticated and then failed to find a file. A 401
    would mean the cookie was rejected — the regression this guards.
    """
    login = client.post(
        "/api/token",
        data={"username": test_user.username, "password": "Testpass123!"},
    )
    assert login.status_code == 200, login.text

    response = client.get(path)  # TestClient carries the cookie jar forward
    assert response.status_code != 401, (
        f"{path} rejected a request carrying the media cookie; "
        "the browser cannot load media in this state"
    )
    assert response.status_code == 404, (
        f"expected 404 for a missing file, got {response.status_code}"
    )


@pytest.mark.parametrize(
    "path",
    [
        "/api/snapshots/nope.jpg",
        "/faces/nope.jpg",
        "/recordings/nope.mp4",
        "/data/thumbnails/nope.jpg",
    ],
)
def test_media_routes_still_refuse_anonymous_callers(client, path):
    """The cookie is the only thing that should open these routes."""
    client.cookies.clear()
    response = client.get(path)
    assert response.status_code == 401, (
        f"{path} served media to a caller with no credentials"
    )
