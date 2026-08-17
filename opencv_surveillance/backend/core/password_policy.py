# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
The single authority on what makes an acceptable password.

Before this module there were four standards, all live at once:

    POST /setup/admin           8 chars + all four character classes
    POST /users/                no constraint whatsoever
    POST /users/{id}/password   8 chars, no character classes
    POST /auth/reset-password   4 chars, no character classes

So the reset path accepted a password the change path would reject, user
creation accepted anything at all, and only the setup path applied the rules the
product documents. Meanwhile MIN_PASSWORD_LENGTH, REQUIRE_UPPERCASE and the rest
sat in config.py and were read by nothing — an operator tightening them changed
no behaviour anywhere.

Everything that accepts a new password now validates through here, and here
reads the configuration. One place to change the rules, one place to test them,
and the settings that claim to control this actually do.

Note this validates a *proposed* password. It is never applied to a password
being checked at login: an existing password that no longer satisfies a
tightened rule must still let its owner in, so they can change it.
"""

import re
from typing import List

from backend.core.config import (
    MIN_PASSWORD_LENGTH,
    MAX_PASSWORD_LENGTH,
    REQUIRE_UPPERCASE,
    REQUIRE_LOWERCASE,
    REQUIRE_DIGIT,
    REQUIRE_SPECIAL_CHAR,
)

SPECIAL_CHARACTERS = r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]/\\~`\';]'

# bcrypt hashes only the first 72 bytes; hash_password() truncates rather than
# rejecting, so two passwords sharing a 72-byte prefix are the same password to
# the hasher. Not enforced here — rejecting long passwords is the wrong fix, and
# the truncation is deliberate — but recorded so the next reader knows the ceiling
# on effective length is 72 bytes, not MAX_PASSWORD_LENGTH characters.
BCRYPT_EFFECTIVE_BYTES = 72


def password_failures(password: str) -> List[str]:
    """
    Every rule the password breaks, as human-readable messages.

    Returns all failures rather than the first, so someone fixing a password is
    told everything at once instead of discovering the rules one rejection at a
    time.
    """
    failures: List[str] = []

    if len(password) < MIN_PASSWORD_LENGTH:
        failures.append(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long")
    if len(password) > MAX_PASSWORD_LENGTH:
        failures.append(
            f"Password must be at most {MAX_PASSWORD_LENGTH} characters long")
    if REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        failures.append("Password must contain at least one uppercase letter")
    if REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
        failures.append("Password must contain at least one lowercase letter")
    if REQUIRE_DIGIT and not re.search(r"\d", password):
        failures.append("Password must contain at least one number")
    if REQUIRE_SPECIAL_CHAR and not re.search(SPECIAL_CHARACTERS, password):
        failures.append("Password must contain at least one special character")

    return failures


def validate_password(password: str) -> str:
    """
    Return the password if it is acceptable, otherwise raise ValueError.

    Shaped to be used directly as a pydantic field validator, which expects the
    validated value back and turns ValueError into a 422.
    """
    failures = password_failures(password)
    if failures:
        raise ValueError(", ".join(failures))
    return password
