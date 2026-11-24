# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Changing a password must end sessions that are already signed in.

Revoking refresh tokens does not reach an access token that has already been
issued: it stays valid until `exp`, thirty minutes by default. So a user who
changed their password because they believed it was compromised left every other
session working for the rest of that window — the one thing the action is meant
to prevent.

Each token now carries the `tv` (token version) it was issued under, and a
password change bumps the user's version.

Why a counter and not a "password changed at" timestamp: JWT encodes `iat` as
integer SECONDS, so a timestamp comparison is ambiguous for the whole second the
change lands in. Rejecting on equality refuses a user signing straight back in;
accepting on equality lets a token issued in that same second survive the
change. This was measured, not theorised — a login and a password change in one
test produced the same `iat`. A counter has no boundary case and is unaffected
by clock skew.
"""

import pytest

from backend.core import auth


class _User:
    """Minimal stand-in: the check only reads token_version."""
    def __init__(self, version=0):
        self.token_version = version


def test_a_token_from_a_previous_version_is_refused():
    assert auth.token_is_superseded({"sub": "alice", "tv": 0}, _User(1)) is True


def test_a_token_from_the_current_version_is_accepted():
    assert auth.token_is_superseded({"sub": "alice", "tv": 3}, _User(3)) is False


def test_every_earlier_version_is_refused_not_just_the_previous_one():
    """Several changes in a row must not let an old token back in."""
    for issued in range(0, 5):
        assert auth.token_is_superseded({"tv": issued}, _User(5)) is True


def test_a_token_without_a_version_is_accepted():
    """
    Tokens issued before this feature carry no `tv`.

    Refusing them would sign out every user on upgrade for no security gain:
    they expire inside the access-token window regardless.
    """
    assert auth.token_is_superseded({"sub": "alice"}, _User(2)) is False


def test_a_user_without_the_column_is_unaffected():
    class Legacy:
        pass
    assert auth.token_is_superseded({"tv": 0}, Legacy()) is False


def test_issued_tokens_actually_carry_the_version(db_session, test_user):
    """The check is inert unless tokens carry the claim."""
    tokens = auth.create_tokens(db_session, test_user)
    payload = auth.jwt.decode(
        tokens["access_token"], auth.JWT_SECRET_KEY, algorithms=[auth.ALGORITHM])
    assert "tv" in payload, "access tokens must carry tv for the check to work"
    assert payload["tv"] == (test_user.token_version or 0)


class TestEndToEnd:
    def test_changing_a_password_rejects_the_old_access_token(self, client, test_user):
        """
        The behaviour, through the API.

        This is the case a timestamp could not handle: the login and the
        password change happen in the same second.
        """
        login = client.post(
            "/api/token",
            data={"username": test_user.username, "password": "Testpass123!"},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        assert client.get("/api/users/me", headers=headers).status_code == 200

        response = client.post(
            f"/api/users/{test_user.id}/password",
            json={"current_password": "Testpass123!",
                  "new_password": "BrandNewPass456!"},
            headers=headers,
        )
        assert response.status_code == 200, response.text

        after = client.get("/api/users/me", headers=headers)
        assert after.status_code == 401, (
            "the access token issued before the password change is still valid; "
            "other sessions stay signed in for up to ACCESS_TOKEN_EXPIRE_MINUTES"
        )

    def test_signing_back_in_immediately_works(self, client, test_user):
        """
        The regression a timestamp comparison would have introduced.

        Changing a password and signing straight back in lands inside the same
        second. That must work.
        """
        login = client.post("/api/token",
                            data={"username": test_user.username, "password": "Testpass123!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        client.post(
            f"/api/users/{test_user.id}/password",
            json={"current_password": "Testpass123!", "new_password": "BrandNewPass456!"},
            headers=headers,
        )

        again = client.post("/api/token",
                            data={"username": test_user.username, "password": "BrandNewPass456!"})
        assert again.status_code == 200, "could not sign in again after changing the password"
        fresh = {"Authorization": f"Bearer {again.json()['access_token']}"}
        assert client.get("/api/users/me", headers=fresh).status_code == 200
