# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
The database must never hold a usable refresh token.

A refresh token is a bearer credential: whoever holds it can mint access tokens
until it expires, without the password and without 2FA. Stored verbatim, the
database was a file of live credentials — and backup.py archives that database,
so every backup archive could resume every active session for up to
REFRESH_TOKEN_EXPIRE_DAYS.

Rotation did not help with this. Reuse detection assumes an attacker had to
steal one token; reading the table hands over all of them at once, each of them
current.

These tests assert the property (no plaintext anywhere in the row) rather than
the mechanism, so they keep holding if the digest is ever changed.
"""

import hashlib

import pytest

from backend.database import crud, models


@pytest.fixture
def issued(db_session, test_user):
    """A real token, issued through the same path login uses."""
    raw = "a-refresh-token-value-that-is-long-and-random-enough-for-a-test"
    record = crud.create_refresh_token(db=db_session, user_id=test_user.id, token=raw)
    return raw, record


def test_the_stored_row_does_not_contain_the_token(issued, db_session):
    """The core property: the row must not be usable if it is read."""
    raw, record = issued
    stored = db_session.query(models.RefreshToken).filter_by(id=record.id).one()

    for column in stored.__table__.columns.keys():
        value = getattr(stored, column)
        if isinstance(value, str):
            assert raw not in value, (
                f"column {column!r} contains the refresh token in the clear"
            )


def test_the_stored_value_is_the_digest(issued):
    raw, record = issued
    assert record.token_hash == hashlib.sha256(raw.encode()).hexdigest()
    assert len(record.token_hash) == 64


def test_a_valid_token_still_resolves(issued, db_session):
    """Hashing must not break the lookup path — otherwise no one can refresh."""
    raw, record = issued
    found = crud.get_refresh_token(db_session, raw)
    assert found is not None
    assert found.id == record.id


def test_the_stored_digest_is_not_itself_a_valid_token(issued, db_session):
    """
    Presenting the digest must not authenticate.

    If the lookup ever compared the presented value against the column without
    hashing it, anyone who read the database could sign in with what they read.
    """
    raw, record = issued
    assert crud.get_refresh_token(db_session, record.token_hash) is None


def test_an_unknown_token_resolves_to_nothing(db_session):
    assert crud.get_refresh_token(db_session, "never-issued") is None


def test_revocation_still_works_through_the_raw_token(issued, db_session):
    raw, record = issued
    assert crud.revoke_refresh_token(db_session, raw) is True
    db_session.refresh(record)
    assert record.revoked is True


def test_the_model_has_no_plaintext_column(db_session):
    """
    Guard against the column coming back.

    A later migration or model edit that reintroduces `token` would restore the
    original problem silently, because every other test here would still pass.
    """
    assert "token" not in models.RefreshToken.__table__.columns.keys()
    assert "token_hash" in models.RefreshToken.__table__.columns.keys()


def test_hashing_is_stable_and_single_sourced():
    """Two implementations of the digest would break every refresh."""
    value = "some-token"
    assert crud.hash_refresh_token(value) == crud.hash_refresh_token(value)
    assert crud.hash_refresh_token(value) != crud.hash_refresh_token(value + "x")
