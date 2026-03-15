"""Peer wrapper for direct API calls with HMAC authentication."""

import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class Peer:
    """Represents a discovered ecosystem peer service."""

    def __init__(self, name: str, base_url: str, hmac_secret: str,
                 timeout: float = 5.0):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self._hmac_secret = hmac_secret
        self._timeout = timeout
        self._degraded = False
        self._cached_token = None
        self._token_refresh_at = 0

    @property
    def is_degraded(self) -> bool:
        return self._degraded

    def mark_degraded(self) -> None:
        self._degraded = True
        logger.warning(f"Peer '{self.name}' marked as degraded")

    def mark_healthy(self) -> None:
        self._degraded = False

    def _auth_headers(self) -> dict[str, str]:
        """Generate HMAC auth headers for the request with token caching."""
        now = int(time.time())
        if not self._cached_token or now > self._token_refresh_at:
            from ecosystem_auth.tokens import create_ecosystem_token
            self._cached_token = create_ecosystem_token(self._hmac_secret, self.name)
            self._token_refresh_at = now + (12 * 3600)  # Refresh at 12h
        return {
            "Authorization": f"Bearer {json.dumps(self._cached_token)}",
            "X-Ecosystem-Source": self.name,
        }

    async def get(self, path: str, **kwargs: Any) -> Any | None:
        """Make an authenticated GET request to this peer."""
        return await self._request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Any | None:
        """Make an authenticated POST request to this peer."""
        return await self._request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> Any | None:
        """Make an authenticated PUT request to this peer."""
        return await self._request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> Any | None:
        """Make an authenticated DELETE request to this peer."""
        return await self._request("DELETE", path, **kwargs)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any | None:
        """Execute an HTTP request with auth and error handling."""
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {})
        headers.update(self._auth_headers())

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.request(method, url, headers=headers, **kwargs)
                resp.raise_for_status()
                self.mark_healthy()
                return resp.json()
        except Exception as e:
            self.mark_degraded()
            logger.warning(f"Request to {self.name} ({method} {url}) failed: {e}")
            return None
