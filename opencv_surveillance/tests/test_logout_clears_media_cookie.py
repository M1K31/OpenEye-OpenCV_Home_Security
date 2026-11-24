# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Signing out must remove the media cookie, not only the stored token.

Login mirrors the access token into an HttpOnly `access_token` cookie so that
<img> and <video> tags can authenticate — a plain tag cannot attach an
Authorization header. Because it is HttpOnly, the browser silently discards the
frontend's own `document.cookie` deletion; the server is the only thing that can
remove it.

Nothing did. `clear_media_auth_cookie()` was defined and never called from
anywhere, so a signed-out browser went on pulling /recordings, /faces,
/api/snapshots and /data/thumbnails for the remaining life of the access token —
up to ACCESS_TOKEN_EXPIRE_MINUTES, 30 by default. On a shared machine that is
the next person's access to recorded footage.
"""

import pytest


def _expiring_cookie_header(response) -> str:
    """The Set-Cookie header for access_token, or "" if none was sent."""
    for name, value in response.headers.raw:
        if name.decode().lower() == "set-cookie":
            header = value.decode()
            if header.startswith("access_token="):
                return header
    return ""


def _is_deletion(header: str) -> bool:
    """A cookie deletion is an empty value plus an immediate expiry."""
    if not header:
        return False
    lowered = header.lower()
    return "access_token=;" in lowered or "access_token=\"\";" in lowered or (
        "max-age=0" in lowered or "01 jan 1970" in lowered
    )


def _login(client, username, password):
    return client.post(
        "/api/token", data={"username": username, "password": password}
    )


def test_login_sets_the_media_cookie(client, test_user):
    """Precondition: the cookie this test is about is actually issued."""
    response = _login(client, test_user.username, "Testpass123!")
    assert response.status_code == 200
    assert "access_token=" in _expiring_cookie_header(response)


def test_revoke_clears_the_media_cookie(client, test_user):
    """The single-device logout path must delete the cookie."""
    login = _login(client, test_user.username, "Testpass123!")
    tokens = login.json()

    response = client.post(
        "/api/token/revoke",
        json={"refresh_token": tokens["refresh_token"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    assert _is_deletion(_expiring_cookie_header(response)), (
        "logout returned 200 without clearing the media cookie"
    )


def test_revoke_all_clears_the_media_cookie(client, test_user):
    """'Log out everywhere' that leaves this browser reading footage has not."""
    login = _login(client, test_user.username, "Testpass123!")
    tokens = login.json()

    response = client.post(
        "/api/token/revoke-all",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 200
    assert _is_deletion(_expiring_cookie_header(response))


def test_an_unknown_refresh_token_still_clears_the_cookie(client, test_user):
    """
    A 404 must not leave the caller holding a working media cookie.

    Someone presenting a token the server does not recognise is still trying to
    sign out. This also pins the framework behaviour the fix depends on: the
    cookie is set on the injected Response BEFORE the raise, and FastAPI must
    carry those headers onto the error response. If that ever stops being true,
    this test is what says so.
    """
    login = _login(client, test_user.username, "Testpass123!")
    tokens = login.json()

    response = client.post(
        "/api/token/revoke",
        json={"refresh_token": "a-token-that-was-never-issued"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 404
    assert _is_deletion(_expiring_cookie_header(response)), (
        "the 404 path returned without clearing the media cookie"
    )
