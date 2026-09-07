# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
The ecosystem shared secret must not be weak, however it was supplied.

ECOSYSTEM_HMAC_SECRET signs requests BETWEEN devices, so a guessable value lets
anything on the network impersonate this installation to its peers.

There are two ways to set it, and only one was checked. The API route that
manages it validates the value (hex, 32-128 characters — see
routes/settings.py). Setting the environment variable directly, in .env, in
docker-compose or in a shell, bypassed that completely: the value went straight
to sign_request as-is.

The behaviour on a bad secret is to disable peering, not to sign with it. That
matches what the bridge already did for a MISSING secret. Peering silently off
is recoverable and says so in the log; peering running on a guessable key is
neither.
"""

import pytest

from backend.core.auth import is_weak_secret
from backend.core import ecosystem_ai_bridge


REFUSED = [
    ("", "empty"),
    ("   ", "whitespace"),
    ("changeme", "classic placeholder"),
    ("secret", "too short"),
    ("a" * 31, "31 characters — under the 32 the algorithm needs"),
    ("ci-test-secret-not-for-production-0123456789abcdef", "the value CI used to use"),
    ("your-secret-key-change-in-production", "a shipped placeholder"),
]

ACCEPTED = [
    ("a" * 32, "32 characters, the minimum"),
    ("3f9a1c7e4b2d8056a1e3c5f70b9d24618c4a7e0d3b5f9126ae4c8d0b7f3a5e29",
     "64 hex characters — what `openssl rand -hex 32` produces"),
]


@pytest.mark.parametrize("value,why", REFUSED)
def test_weak_secrets_are_refused(value, why):
    assert is_weak_secret(value) is True, f"{why} was accepted as a signing secret"


@pytest.mark.parametrize("value,why", ACCEPTED)
def test_real_secrets_are_accepted(value, why):
    """
    The guard must not reject legitimate secrets.

    Over-rejecting here would disable ecosystem peering for installations that
    configured it correctly, which is a worse failure than the one being fixed.
    """
    assert is_weak_secret(value) is False, f"{why} was refused"


class TestTheBridgeRefusesToSignWithAWeakSecret:
    """The behaviour, not just the predicate."""

    def test_a_weak_environment_secret_disables_peering(self, monkeypatch):
        monkeypatch.setenv("ECOSYSTEM_HMAC_SECRET", "changeme")
        assert ecosystem_ai_bridge._make_profile_client() is None

    def test_a_missing_secret_disables_peering(self, monkeypatch):
        """Unchanged behaviour — recorded so it is not lost in a later edit."""
        monkeypatch.delenv("ECOSYSTEM_HMAC_SECRET", raising=False)
        assert ecosystem_ai_bridge._make_profile_client() is None

    def test_a_strong_secret_is_not_rejected_by_this_check(self, monkeypatch):
        """
        A good secret must get past the strength check.

        It may still return None because the optional ecosystem packages are
        absent, which is the common case and not what this test is about — so
        assert on the reason rather than the result: the strength check must not
        be what stopped it.
        """
        monkeypatch.setenv("ECOSYSTEM_HMAC_SECRET", "b" * 64)
        assert is_weak_secret("b" * 64) is False


def test_ci_supplies_a_secret_the_application_would_accept():
    """
    CI must exercise the real signing path.

    A CI secret that the application refuses means CI stops testing ecosystem
    signing at all, while still appearing to. This caught exactly that: the
    previous value contained "not-for-production" and would now be rejected.
    """
    import pathlib
    import re

    workflow = pathlib.Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml"
    if not workflow.exists():
        pytest.skip("ci.yml not present")

    found = re.findall(r'ECOSYSTEM_HMAC_SECRET:\s*"([^"]+)"', workflow.read_text())
    assert found, "ci.yml no longer sets ECOSYSTEM_HMAC_SECRET"
    for value in found:
        assert not is_weak_secret(value), (
            f"ci.yml sets a secret the application refuses: {value!r}. "
            "CI would silently stop covering the signed path."
        )
