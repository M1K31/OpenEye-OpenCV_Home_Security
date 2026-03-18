"""Service discovery with three-mode cascade: registry -> mDNS -> static -> standalone."""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any

import httpx

from .config import EcosystemConfig

logger = logging.getLogger(__name__)


class DiscoveryMode(str, Enum):
    REGISTRY = "registry"
    PEER_TO_PEER = "peer_to_peer"
    STANDALONE = "standalone"


class DiscoveryManager:
    """Detects operating mode and resolves peer locations."""

    def __init__(self, config: EcosystemConfig):
        self.config = config
        self._mode: DiscoveryMode | None = None
        self._peers: dict[str, dict[str, Any]] = {}
        self._mdns_peers: list[dict] = []

    @property
    def mode(self) -> DiscoveryMode:
        return self._mode or DiscoveryMode.STANDALONE

    async def detect_mode(self) -> DiscoveryMode:
        """Run the discovery cascade and return the detected mode."""
        if not self.config.enabled:
            self._mode = DiscoveryMode.STANDALONE
            logger.info("Ecosystem disabled — standalone mode")
            return self._mode

        # 1. Check registry
        if await self._check_registry():
            self._mode = DiscoveryMode.REGISTRY
            logger.info(f"Registry found at {self.config.registry_url} — registry mode")
            return self._mode

        # 2. Check mDNS
        self._mdns_peers = self._check_mdns()
        if self._mdns_peers:
            self._mode = DiscoveryMode.PEER_TO_PEER
            logger.info(f"Found {len(self._mdns_peers)} peers via mDNS — peer-to-peer mode")
            return self._mode

        # 3. Check static peers
        if self.config.peers:
            self._mode = DiscoveryMode.PEER_TO_PEER
            logger.info(f"Using {len(self.config.peers)} static peers — peer-to-peer mode")
            return self._mode

        # 4. Standalone
        self._mode = DiscoveryMode.STANDALONE
        logger.info("No registry or peers found — standalone mode")
        return self._mode

    async def get_peers(self) -> dict[str, dict[str, Any]]:
        """Return discovered peers based on current mode."""
        if self._mode == DiscoveryMode.REGISTRY:
            services = await self._fetch_registry_services()
            self._peers = {
                svc["name"]: svc for svc in services
            }
            return self._peers

        if self._mode == DiscoveryMode.PEER_TO_PEER:
            # Merge mDNS and static peers
            peers = {}
            for mdns_peer in self._mdns_peers:
                name = mdns_peer["name"]
                peers[name] = {
                    "name": name,
                    "base_url": f"http://{mdns_peer['host']}:{mdns_peer['port']}",
                }
            for name, url in self.config.peers.items():
                if name not in peers:
                    peers[name] = {"name": name, "base_url": url}
            self._peers = peers
            return self._peers

        # STANDALONE
        return {}

    async def _check_registry(self) -> bool:
        """Check if the ecosystem registry is reachable."""
        try:
            async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
                resp = await client.get(f"{self.config.registry_url}/health")
                return resp.status_code == 200
        except Exception:
            return False

    def _check_mdns(self) -> list[dict]:
        """Scan for ecosystem services via mDNS. Returns list of peer dicts."""
        try:
            from registry.discovery import EcosystemDiscovery

            disc = EcosystemDiscovery()
            return disc.discover_services()
        except ImportError:
            logger.debug("mDNS discovery not available (zeroconf not installed)")
            return []
        except Exception as e:
            logger.debug(f"mDNS discovery failed: {e}")
            return []

    async def _fetch_registry_services(self) -> list[dict]:
        """Fetch all services from the registry, sorted by priority (highest first)."""
        try:
            async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
                resp = await client.get(f"{self.config.registry_url}/services")
                resp.raise_for_status()
                services = resp.json()
                # Sort by priority descending so highest-priority peers are first
                services.sort(key=lambda s: s.get("priority", 0), reverse=True)
                return services
        except Exception as e:
            logger.warning(f"Failed to fetch services from registry: {e}")
            return []

    async def register_self(self, name: str, host: str, port: int,
                            health_endpoint: str, webhook_url: str | None = None,
                            subscriptions: list[str] | None = None,
                            priority: int = 0) -> bool:
        """Register this service with the registry (Mode 1 only)."""
        if self._mode != DiscoveryMode.REGISTRY:
            return False
        try:
            payload = {
                "name": name,
                "host": host,
                "port": port,
                "health_endpoint": health_endpoint,
                "webhook_url": webhook_url,
                "subscriptions": subscriptions or [],
                "priority": priority,
            }
            async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
                resp = await client.post(f"{self.config.registry_url}/register", json=payload)
                resp.raise_for_status()
                logger.info(f"Registered with ecosystem registry as '{name}'")
                return True
        except Exception as e:
            logger.warning(f"Failed to register with registry: {e}")
            return False

    async def deregister_self(self, name: str) -> bool:
        """Deregister this service from the registry (Mode 1 only)."""
        if self._mode != DiscoveryMode.REGISTRY:
            return False
        try:
            async with httpx.AsyncClient(timeout=self.config.request_timeout) as client:
                resp = await client.delete(f"{self.config.registry_url}/deregister/{name}")
                return resp.status_code < 400
        except Exception:
            return False
