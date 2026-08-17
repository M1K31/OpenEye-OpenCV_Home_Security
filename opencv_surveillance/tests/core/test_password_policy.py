# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Tests for the single authority on password acceptability.

The rule underneath these: every path that sets a password answers to the same
policy, and that policy is the configuration rather than a literal copied into
each schema. What is asserted here is mostly *sameness* — four endpoints that
used to disagree now cannot.
"""

import pytest
from pydantic import ValidationError

from backend.core import password_policy
from backend.core.password_policy import password_failures, validate_password
from backend.api.schemas.user import UserCreate, UserPasswordChange
from backend.api.schemas.password_reset import PasswordResetRequest
from backend.api.routes.setup import SetupInitializeRequest

GOOD = "Str0ng!Passw0rd"


class TestTheRules:
    def test_a_compliant_password_passes(self):
        assert password_failures(GOOD) == []
        assert validate_password(GOOD) == GOOD

    @pytest.mark.parametrize("password,expected", [
        ("Sh0rt!", "at least"),
        ("nouppercase1!", "uppercase"),
        ("NOLOWERCASE1!", "lowercase"),
        ("NoDigitsHere!", "number"),
        ("NoSpecialChar1", "special"),
    ])
    def test_each_rule_is_enforced(self, password, expected):
        failures = password_failures(password)
        assert any(expected in f for f in failures), failures

    def test_every_failure_is_reported_not_just_the_first(self):
        """
        Someone fixing a password should be told all of it at once, rather than
        discovering the rules one rejection at a time.
        """
        assert len(password_failures("short")) >= 3

    def test_validate_raises_with_all_reasons_joined(self):
        with pytest.raises(ValueError) as exc:
            validate_password("short")
        message = str(exc.value)
        assert "at least" in message and "uppercase" in message


class TestTheRulesComeFromConfiguration:
    def test_relaxing_the_minimum_length_relaxes_the_check(self, monkeypatch):
        """
        The point of the whole change. These settings existed in config.py and
        were read by nothing, so an operator who tightened them changed no
        behaviour at all.
        """
        monkeypatch.setattr(password_policy, "MIN_PASSWORD_LENGTH", 30)
        assert any("at least 30" in f for f in password_failures(GOOD))

    def test_disabling_a_character_rule_disables_the_check(self, monkeypatch):
        monkeypatch.setattr(password_policy, "REQUIRE_SPECIAL_CHAR", False)
        assert password_failures("N0SpecialChars") == []


class TestEveryPathAgrees:
    """
    Before this, four live endpoints enforced four different standards:

        POST /setup/admin           8 chars + all four character classes
        POST /users/                nothing at all
        POST /users/{id}/password   8 chars, no character classes
        POST /auth/reset-password   4 chars, no character classes

    so a reset could set a password the change path refused, and user creation
    accepted anything including an empty string.
    """

    def _build(self, schema, password):
        payloads = {
            UserCreate: dict(username="u", email="u@example.com", password=password),
            UserPasswordChange: dict(current_password="x", new_password=password),
            PasswordResetRequest: dict(username="u", totp_code="123456",
                                       new_password=password),
            SetupInitializeRequest: dict(username="user", email="u@example.com",
                                         password=password),
        }
        return schema(**payloads[schema])

    ALL = [UserCreate, UserPasswordChange, PasswordResetRequest, SetupInitializeRequest]

    @pytest.mark.parametrize("schema", ALL)
    def test_a_compliant_password_is_accepted_everywhere(self, schema):
        assert self._build(schema, GOOD) is not None

    @pytest.mark.parametrize("schema", ALL)
    @pytest.mark.parametrize("weak", ["1234", "short", "alllowercase1!", "NoDigit!"])
    def test_a_weak_password_is_refused_everywhere(self, schema, weak):
        with pytest.raises(ValidationError):
            self._build(schema, weak)

    @pytest.mark.parametrize("schema", ALL)
    def test_an_empty_password_is_refused_everywhere(self, schema):
        """UserCreate accepted this before — it had no constraint whatsoever."""
        with pytest.raises(ValidationError):
            self._build(schema, "")

    def test_the_reset_path_is_no_weaker_than_the_change_path(self):
        """
        The specific defect: POST /auth/reset-password carried min_length=4
        while POST /users/{id}/password carried min_length=8, so a reset could
        leave an account with a password the product's own rule forbids.
        """
        four_chars = "Ab1!"
        with pytest.raises(ValidationError):
            self._build(PasswordResetRequest, four_chars)
        with pytest.raises(ValidationError):
            self._build(UserPasswordChange, four_chars)
