# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
JWT_SECRET_KEY must actually sign the tokens.

It was computed at import and then never read: all four jwt.encode/decode call
sites passed SECRET_KEY. Meanwhile .env.example, docker-compose.yml, DOCKER.md
and setup-production.sh all instruct operators to set it.

The failure mode that matters is not the dead variable, it is what an operator
believes. Rotating a signing key after a suspected compromise is how you
invalidate every issued token. Rotating this one invalidated nothing, and
nothing said so — a security control that silently does nothing is worse than
no control, because it stops the operator looking for a real one.

These tests assert the property (the advertised key is the one in force), so
they hold regardless of which variable the implementation ends up naming.
"""

import pathlib

import jwt as pyjwt
import pytest

from backend.core import auth


def test_the_key_is_used_to_sign():
    """A token must verify under the key the configuration advertises."""
    token = auth.create_access_token({"sub": "alice"})
    payload = pyjwt.decode(token, auth.JWT_SECRET_KEY, algorithms=[auth.ALGORITHM])
    assert payload["sub"] == "alice"


def test_a_token_signed_with_another_key_is_refused():
    """The guarantee behind rotation: a different key must not verify."""
    forged = pyjwt.encode({"sub": "attacker"}, "a" * 64, algorithm=auth.ALGORITHM)
    with pytest.raises(auth.JWTError):
        pyjwt.decode(forged, auth.JWT_SECRET_KEY, algorithms=[auth.ALGORITHM])


def test_no_token_operation_still_uses_the_general_key():
    """
    Pin it in the source.

    JWT_SECRET_KEY falls back to SECRET_KEY when unset, so in a default test
    environment the two are equal and a behavioural test cannot tell them
    apart. Reading the call sites can.
    """
    import pathlib

    root = pathlib.Path(auth.__file__).resolve().parents[1]
    offenders = []
    for path in root.rglob("*.py"):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if ("jwt.encode(" in line or "jwt.decode(" in line) and "JWT_SECRET_KEY" not in line:
                offenders.append(f"{path.relative_to(root)}:{number}: {stripped}")
    assert not offenders, "token operations not using JWT_SECRET_KEY:\n" + "\n".join(offenders)


def _resolved_keys(env: dict) -> tuple:
    """
    Import auth in a CLEAN interpreter and report the keys it resolved.

    A subprocess rather than importlib.reload: auth generates a random
    per-install key at import when none is supplied, so reloading it inside the
    test session swaps the key out from under every module that already did
    `from backend.core.auth import ...`, and unrelated tests then fail to verify
    tokens they just created. That is exactly what happened when this was first
    written with reload.
    """
    import json
    import os
    import subprocess
    import sys

    script = (
        "from backend.core import auth; import json; "
        "print(json.dumps([auth.SECRET_KEY, auth.JWT_SECRET_KEY]))"
    )
    environment = {**os.environ, **env}
    environment.pop("JWT_SECRET_KEY", None) if env.get("_drop_jwt") else None
    environment.pop("_drop_jwt", None)

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, env=environment,
        cwd=str(pathlib.Path(auth.__file__).resolve().parents[2]),
    )
    assert result.returncode == 0, result.stderr
    return tuple(json.loads(result.stdout.strip().splitlines()[-1]))


def test_it_falls_back_to_secret_key_when_unset():
    """
    An installation that never set it must be unaffected.

    This is what keeps the change from signing everyone out: only someone who
    explicitly set a DIFFERENT JWT_SECRET_KEY sees a re-login.
    """
    secret, jwt_key = _resolved_keys({"SECRET_KEY": "f" * 64, "_drop_jwt": "1"})
    assert jwt_key == secret == "f" * 64


def test_a_distinct_jwt_key_is_honoured():
    """Setting it must now actually change the signing key — the whole point."""
    secret, jwt_key = _resolved_keys(
        {"SECRET_KEY": "a" * 64, "JWT_SECRET_KEY": "b" * 64})
    assert secret == "a" * 64
    assert jwt_key == "b" * 64


def test_a_weak_jwt_key_is_refused():
    """A placeholder must not become the signing key by this route either."""
    secret, jwt_key = _resolved_keys(
        {"SECRET_KEY": "e" * 64, "JWT_SECRET_KEY": "your-jwt-secret-key"})
    assert jwt_key != "your-jwt-secret-key"
    assert jwt_key == secret
