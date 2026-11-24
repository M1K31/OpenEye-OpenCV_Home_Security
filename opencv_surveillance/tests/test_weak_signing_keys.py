# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
No published constant may ever sign a token.

The service binds 0.0.0.0. A signing key that is committed to this repository
lets any host on the network mint an admin JWT, which sits in front of the
password, 2FA, account lockout and rate limiting alike — none of those run until
the signature has already verified.

This test exists because the guard was previously exact-match and the shipped
defaults did not match it. `_KNOWN_WEAK_KEYS` listed "your-secret-key" while
docker-compose.yml shipped "your-secret-key-change-in-production", so the guard
read as protection while accepting the very value it was written to refuse.

The cases below are therefore pinned to the DEFAULTS THAT SHIP, not to a
hand-written list of weak strings. If a default is reworded in compose, the
installer or the docs, the corresponding case here must be updated to match it —
and that is the point: the two cannot drift apart silently again.
"""

import pytest

from backend.core import auth


# Every placeholder this project has ever shipped, with where it comes from.
SHIPPED_PLACEHOLDERS = [
    ("your-secret-key-change-in-production", "docker-compose.yml SECRET_KEY"),
    ("your-jwt-secret-key", "docker-compose.yml JWT_SECRET_KEY"),
    ("dev-jwt-key-change-in-production", "setup_notification_encryption.py"),
    ("your-secret-key", "historical default"),
    ("dev-secret-key", "historical default"),
    ("dev-secret-key-change-in-production", "historical default"),
    ("change-me", "historical default"),
    ("changeme", "historical default"),
]


@pytest.mark.parametrize("key,origin", SHIPPED_PLACEHOLDERS)
def test_shipped_placeholders_are_refused(key, origin):
    """A default that ships in this repository must never sign a token."""
    assert auth._is_weak_key(key) is True, (
        f"{key!r} (from {origin}) would be accepted as a signing key"
    )


@pytest.mark.parametrize("key", ["", None, "   "])
def test_empty_keys_are_refused(key):
    assert auth._is_weak_key(key) is True


def test_case_does_not_launder_a_placeholder():
    """Capitalising a published constant does not make it secret."""
    assert auth._is_weak_key("YOUR-SECRET-KEY-CHANGE-IN-PRODUCTION") is True


def test_short_keys_are_refused():
    """Below 32 characters is under the HS256 key size and brute-forceable."""
    assert auth._is_weak_key("a" * 31) is True
    assert auth._is_weak_key("short") is True


def test_a_real_key_is_accepted():
    """The guard must not reject legitimate keys — that would break every install."""
    import secrets
    for _ in range(20):
        assert auth._is_weak_key(secrets.token_hex(32)) is False


def test_the_live_signing_key_is_not_weak():
    """
    Whatever this process resolved at import time must itself pass the guard.

    This is the end-to-end assertion: it fails if the resolution order ever
    lets a placeholder through, regardless of which branch produced it.
    """
    assert auth._is_weak_key(auth.SECRET_KEY) is False
    assert auth._is_weak_key(auth.JWT_SECRET_KEY) is False
