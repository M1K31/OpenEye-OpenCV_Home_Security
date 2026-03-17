"""Publish events to the ecosystem via bus (Mode 1) or direct webhooks (Mode 2)."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

import httpx

from .config import EcosystemConfig
from .discovery import DiscoveryMode
from .match import matches_pattern

logger = logging.getLogger(__name__)


class EventPublisher:
    """Publishes events with mode-appropriate delivery."""

    def __init__(self, config: EcosystemConfig, mode: DiscoveryMode, service_name: str):
        self.config = config
        self._mode = mode
        self._service_name = service_name
        self._peer_webhooks: dict[str, dict[str, Any]] = {}

    def set_peer_webhooks(self, webhooks: dict[str, dict[str, Any]]) -> None:
        """Set peer webhook URLs and subscriptions (Mode 2)."""
        self._peer_webhooks = webhooks

    async def publish(self, event_type: str, data: dict[str, Any]) -> dict:
        """Publish an event. Behavior depends on discovery mode."""
        if self._mode == DiscoveryMode.STANDALONE:
            return {"delivered": 0, "failed": 0, "mode": "standalone"}

        envelope = self._build_envelope(event_type, data)

        if self._mode == DiscoveryMode.REGISTRY:
            return await self._publish_via_registry(envelope)

        return await self._publish_direct(envelope)

    def _build_envelope(self, event_type: str, data: dict[str, Any]) -> dict:
        """Build a signed event envelope."""
        from ecosystem_auth.tokens import sign_payload

        envelope = {
            "id": str(uuid.uuid4()),
            "type": event_type,
            "source": self._service_name,
            "timestamp": time.time(),
            "data": data,
        }
        signable = {
            "id": envelope["id"],
            "type": envelope["type"],
            "source": envelope["source"],
            "timestamp": envelope["timestamp"],
            "data": envelope["data"],
        }
        envelope["signature"] = sign_payload(signable, self.config.hmac_secret)
        return envelope

    async def _publish_via_registry(self, envelope: dict) -> dict:
        """Publish by POSTing to the registry's event bus endpoint."""
        try:
            async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
                resp = await client.post(
                    f"{self.config.registry_url}/events/publish",
                    json=envelope,
                    headers={
                        "X-Ecosystem-Signature": envelope.get("signature", ""),
                        "X-Ecosystem-Event": envelope["type"],
                        "X-Ecosystem-Source": envelope["source"],
                    },
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"Failed to publish via registry: {e}")
            return {"delivered": 0, "failed": 1, "error": str(e)}

    async def _publish_direct(self, envelope: dict) -> dict:
        """Publish directly to matching peer webhooks (Mode 2)."""
        matching = self._get_matching_peers(envelope["type"])
        if not matching:
            return {"delivered": 0, "failed": 0, "subscribers": []}

        tasks = [
            self._deliver_to_peer(envelope, name, info["webhook_url"])
            for name, info in matching.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        delivered = sum(1 for r in results if r is True)
        failed = len(results) - delivered
        return {
            "delivered": delivered,
            "failed": failed,
            "subscribers": list(matching.keys()),
        }

    async def _deliver_to_peer(self, envelope: dict, name: str, webhook_url: str) -> bool:
        """Deliver event to a single peer with retry."""
        headers = {
            "Content-Type": "application/json",
            "X-Ecosystem-Signature": envelope.get("signature", ""),
            "X-Ecosystem-Event": envelope["type"],
            "X-Ecosystem-Source": envelope["source"],
        }
        for attempt in range(1, self.config.event_retry_attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
                    resp = await client.post(webhook_url, json=envelope, headers=headers)
                if resp.status_code < 400:
                    return True
            except Exception:
                pass
            if attempt < self.config.event_retry_attempts:
                await asyncio.sleep(self.config.event_retry_delay)

        logger.warning(f"Failed to deliver event to {name} after {self.config.event_retry_attempts} attempts")
        return False

    def _get_matching_peers(self, event_type: str) -> dict[str, dict]:
        """Filter peers whose subscriptions match the event type."""
        matching = {}
        for name, info in self._peer_webhooks.items():
            for pattern in info.get("subscriptions", []):
                if matches_pattern(event_type, pattern):
                    matching[name] = info
                    break
        return matching
