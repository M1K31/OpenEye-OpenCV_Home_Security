"""
Refresh-token rotation and reuse-detection tests.

These cover the security contract of the refresh flow rather than the CRUD layer:
a refresh token is single-use, and replaying one that has already been rotated is
treated as evidence of theft (OAuth 2.0 Security BCP) — the whole token family is
revoked so a stolen token cannot outlive its detection.
"""
import pytest
from datetime import datetime, timedelta
from fastapi import HTTPException

from backend.core import auth
from backend.database import crud
from backend.api.schemas.user import UserCreate


def _make_user(db, username="rotationuser"):
    return crud.create_user(
        db,
        UserCreate(
            username=username,
            email=f"{username}@example.com",
            password="Testpassword123!",
        ),
    )


class TestRefreshTokenRotation:
    def test_refresh_rotates_and_revokes_the_old_token(self, db_session):
        """A successful refresh must issue a NEW refresh token and burn the old one."""
        user = _make_user(db_session, "rotate1")
        tokens = auth.create_tokens(db_session, user)
        old_refresh = tokens["refresh_token"]

        new_tokens = auth.refresh_access_token(db_session, old_refresh)

        assert new_tokens["refresh_token"] != old_refresh, "refresh token was not rotated"
        assert new_tokens["access_token"]
        old_record = crud.get_refresh_token(db_session, old_refresh)
        assert old_record.revoked is True, "old refresh token should be revoked after use"

    def test_replaying_a_used_token_revokes_the_whole_family(self, db_session):
        """
        Reuse detection: presenting an already-rotated token means it leaked, so every
        refresh token for that user must be revoked — not just the replayed one.
        """
        user = _make_user(db_session, "rotate2")
        tokens = auth.create_tokens(db_session, user)
        old_refresh = tokens["refresh_token"]

        # Legitimate rotation -> new token is valid, old one is now spent.
        new_tokens = auth.refresh_access_token(db_session, old_refresh)
        new_refresh = new_tokens["refresh_token"]
        assert crud.get_refresh_token(db_session, new_refresh).revoked is False

        # Attacker replays the spent token.
        with pytest.raises(HTTPException) as exc:
            auth.refresh_access_token(db_session, old_refresh)
        assert exc.value.status_code == 401

        # The still-live token must ALSO be dead now, or the thief keeps access.
        assert crud.get_refresh_token(db_session, new_refresh).revoked is True, (
            "reuse detection must revoke the entire family, not just the replayed token"
        )

    def test_expired_refresh_token_is_rejected(self, db_session):
        user = _make_user(db_session, "rotate3")
        crud.create_refresh_token(
            db_session,
            user_id=user.id,
            token="expired-token-abc",
            expires_at=datetime.utcnow() - timedelta(seconds=1),
        )
        with pytest.raises(HTTPException) as exc:
            auth.refresh_access_token(db_session, "expired-token-abc")
        assert exc.value.status_code == 401

    def test_unknown_refresh_token_is_rejected(self, db_session):
        with pytest.raises(HTTPException) as exc:
            auth.refresh_access_token(db_session, "no-such-token")
        assert exc.value.status_code == 401

    def test_default_expiry_is_applied_when_not_specified(self, db_session):
        """create_refresh_token must not require callers to compute the expiry."""
        user = _make_user(db_session, "rotate4")
        rec = crud.create_refresh_token(
            db_session, user_id=user.id, token="defaults-token-xyz"
        )
        assert rec.expires_at > datetime.utcnow()
