"""FastAPI middleware/dependency for ecosystem authentication."""

import os
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .tokens import verify_signature

security_scheme = HTTPBearer(auto_error=False)


def get_ecosystem_secret() -> str:
    """Get the shared HMAC secret from environment."""
    secret = os.environ.get("ECOSYSTEM_HMAC_SECRET", "dev-ecosystem-secret-change-in-production")
    return secret


async def require_ecosystem_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> dict:
    """
    FastAPI dependency that validates ecosystem HMAC-signed requests.

    Checks the X-Ecosystem-Signature header against the request body,
    or validates a Bearer token from the Authorization header.
    """
    secret = get_ecosystem_secret()

    # Check HMAC signature header (for webhook/event payloads)
    signature = request.headers.get("X-Ecosystem-Signature")
    if signature:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON body",
            )
        if not verify_signature(body, signature, secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid ecosystem signature",
            )
        return {"auth_method": "hmac", "payload": body}

    # Check Bearer token (for service-to-service calls)
    if credentials:
        from .tokens import verify_ecosystem_token
        import json

        try:
            token_data = json.loads(credentials.credentials)
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format",
            )
        if not verify_ecosystem_token(token_data, secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired ecosystem token",
            )
        return {"auth_method": "token", "service": token_data.get("service")}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing ecosystem authentication",
    )
