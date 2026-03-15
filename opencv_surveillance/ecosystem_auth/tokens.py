"""
HMAC-SHA256 token generation and verification.

Extracted from OpenEye's ecosystem_security.py for cross-project reuse.
All projects in the ecosystem use the same HMAC secret for inter-service auth.
"""

import hashlib
import hmac
import json
import secrets
import time
from typing import Optional


def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure hex token."""
    return secrets.token_hex(length)


def hash_token(token: str) -> str:
    """Create a one-way SHA-256 hash of a token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token_hash(token: str, token_hash: str) -> bool:
    """Verify a token against its stored hash using constant-time comparison."""
    return hmac.compare_digest(hash_token(token), token_hash)


def sign_payload(payload: dict, secret: str) -> str:
    """
    Sign a payload with HMAC-SHA256.

    The payload is JSON-serialized with sorted keys for deterministic output,
    ensuring the same payload produces the same signature across Python and JS.
    """
    message = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_signature(payload: dict, signature: str, secret: str) -> bool:
    """Verify the HMAC-SHA256 signature of a payload (constant-time comparison)."""
    expected = sign_payload(payload, secret)
    return hmac.compare_digest(expected, signature)


def create_ecosystem_token(secret: str, service_name: str, ttl_seconds: int = 86400) -> dict:
    """
    Create a signed ecosystem token for inter-service communication.

    Returns a dict with token, issued_at, expires_at, and signature.
    """
    now = int(time.time())
    token_data = {
        "token": generate_secure_token(),
        "service": service_name,
        "issued_at": now,
        "expires_at": now + ttl_seconds,
    }
    token_data["signature"] = sign_payload(
        {"service": service_name, "issued_at": now, "expires_at": now + ttl_seconds},
        secret,
    )
    return token_data


def verify_ecosystem_token(token_data: dict, secret: str) -> bool:
    """
    Verify a signed ecosystem token is valid and not expired.
    """
    now = int(time.time())
    if now > token_data.get("expires_at", 0):
        return False

    expected_payload = {
        "service": token_data.get("service", ""),
        "issued_at": token_data.get("issued_at", 0),
        "expires_at": token_data.get("expires_at", 0),
    }
    return verify_signature(expected_payload, token_data.get("signature", ""), secret)
