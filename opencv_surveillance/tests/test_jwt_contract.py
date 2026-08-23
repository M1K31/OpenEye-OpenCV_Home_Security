# Copyright (c) 2025 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
The security contract every JWT in this application must satisfy.

Written deliberately against the application's own API rather than against the
JWT library, so it holds across the migration from python-jose to PyJWT and
would hold across any future change of library.

Why the migration (audit P2-2)
------------------------------
python-jose verifies every token in the system and is effectively unmaintained,
with published advisories including algorithm confusion (CVE-2024-33663) and a
decompression denial of service (CVE-2024-33664). PyJWT was already a declared
dependency with **zero** importers.

The most important test here is the `alg: none` case. Algorithm confusion is the
attack the advisory describes: a token whose header claims no signature, or a
different algorithm than the server expects, must be refused. Passing
`algorithms=[ALGORITHM]` as an explicit list is what enforces that — the server
decides the algorithm, never the token.
"""

import base64
import json
from datetime import timedelta

import pytest

from backend.core import auth


def _tamper_payload(token: str, changes: dict) -> str:
    """Rewrite a token's claims, leaving its original signature attached."""
    header_b64, payload_b64, signature = token.split(".")

    def _pad(segment):
        return segment + "=" * (-len(segment) % 4)

    payload = json.loads(base64.urlsafe_b64decode(_pad(payload_b64)))
    payload.update(changes)
    new_payload = base64.urlsafe_b64encode(
        json.dumps(payload).encode()).decode().rstrip("=")
    return f"{header_b64}.{new_payload}.{signature}"


def test_a_token_round_trips():
    """The basic contract: what we sign, we can read back."""
    token = auth.create_access_token({"sub": "alice"})
    payload = auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
    assert payload["sub"] == "alice"


def test_an_expired_token_is_refused():
    """Expiry must be enforced by the library, not by calling code."""
    token = auth.create_access_token({"sub": "alice"}, expires_delta=timedelta(seconds=-30))
    with pytest.raises(auth.JWTError):
        auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])


def test_a_token_signed_with_another_key_is_refused():
    """A signature from a key we do not hold proves nothing."""
    token = auth.jwt.encode({"sub": "mallory"}, "not-our-secret", algorithm=auth.ALGORITHM)
    with pytest.raises(auth.JWTError):
        auth.jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])


def test_a_tampered_payload_is_refused():
    """Editing claims must invalidate the signature."""
    token = auth.create_access_token({"sub": "alice"})
    forged = _tamper_payload(token, {"sub": "admin"})
    with pytest.raises(auth.JWTError):
        auth.jwt.decode(forged, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])


def test_an_unsigned_token_is_refused():
    """
    Algorithm confusion — the attack the python-jose advisory describes.

    A token whose header says `alg: none` carries no signature at all. If the
    server honoured the token's own claim about how it was signed, anyone could
    mint any identity. The algorithm must come from the server.
    """
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": "admin"}).encode()).decode().rstrip("=")
    unsigned = f"{header}.{payload}."

    with pytest.raises(auth.JWTError):
        auth.jwt.decode(unsigned, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])


def test_garbage_is_refused_rather_than_crashing():
    """Malformed input must raise the error type callers already handle."""
    for junk in ("", "not-a-token", "a.b.c", "..."):
        with pytest.raises(auth.JWTError):
            auth.jwt.decode(junk, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])


def test_decode_is_always_given_an_explicit_algorithm_list():
    """
    Every decode call in the codebase must pin the algorithm.

    Omitting `algorithms=` is what makes algorithm confusion possible in the
    first place. A static check, so a new call site cannot quietly drop it.
    """
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent / "backend"
    offenders = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "decode"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "jwt"
            ):
                if not any(kw.arg == "algorithms" for kw in node.keywords):
                    offenders.append(f"{path.name}:{node.lineno}")

    assert not offenders, (
        "jwt.decode() called without an explicit algorithms list at: "
        + ", ".join(offenders)
    )
