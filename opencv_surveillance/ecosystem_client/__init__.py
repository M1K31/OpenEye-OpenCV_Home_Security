"""Ecosystem client library for inter-service communication."""
from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any, Callable, Coroutine

from .config import EcosystemConfig
from .discovery import DiscoveryManager, DiscoveryMode
from .event_publisher import EventPublisher
from .event_subscriber import EventSubscriber
from .peer import Peer

__version__ = "0.1.0"

logger = logging.getLogger(__name__)

HandlerFunc = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class EcosystemClient:
    """
    Thin client for ecosystem integration.

    Handles service discovery, event pub/sub, and direct peer calls
    across three operating modes:
    - REGISTRY: full ecosystem with appEcosystem registry
    - PEER_TO_PEER: direct mDNS or static peer discovery
    - STANDALONE: no-op, project runs independently
    """

    def __init__(
        self,
        service_name: str,
        service_port: int,
        health_endpoint: str = "/health",
        subscriptions: list[str] | None = None,
        config: EcosystemConfig | None = None,
    ):
        self._config = config or EcosystemConfig.from_env()
        self._config.service_name = service_name
        self._config.service_port = service_port
        self._config.health_endpoint = health_endpoint

        self._service_name = service_name
        self._service_port = service_port
        self._health_endpoint = health_endpoint
        self._subscriptions = subscriptions or []

        self._discovery = DiscoveryManager(self._config)
        self._publisher = EventPublisher(
            self._config, mode=DiscoveryMode.STANDALONE, service_name=service_name,
        )
        self._subscriber = EventSubscriber(hmac_secret=self._config.hmac_secret)

        self._peers: dict[str, dict[str, Any]] = {}
        self._peer_objects: dict[str, Peer] = {}
        self._started = False
        self._refresh_task: asyncio.Task | None = None

    @property
    def mode(self) -> DiscoveryMode:
        return self._discovery.mode

    async def start(self) -> None:
        """Start the ecosystem client: detect mode, register, discover peers."""
        if self._started:
            return

        mode = await self._discovery.detect_mode()
        self._publisher._mode = mode

        if mode == DiscoveryMode.REGISTRY:
            host = self._get_local_ip()
            webhook_url = f"http://{host}:{self._service_port}{self._config.webhook_path}"
            all_subs = list(set(self._subscriptions + self._subscriber.subscriptions))
            await self._discovery.register_self(
                name=self._service_name,
                host=host,
                port=self._service_port,
                health_endpoint=self._health_endpoint,
                webhook_url=webhook_url,
                subscriptions=all_subs,
            )

        # Discover peers
        await self._refresh_peers()

        self._started = True
        logger.info(
            f"Ecosystem client started: {self._service_name} in {mode.value} mode"
        )

        # Start background refresh
        self._refresh_task = asyncio.create_task(self._periodic_refresh())

    async def stop(self) -> None:
        """Stop the ecosystem client: deregister, cancel background tasks."""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

        if self._discovery.mode == DiscoveryMode.REGISTRY:
            await self._discovery.deregister_self(self._service_name)

        self._started = False
        logger.info(f"Ecosystem client stopped: {self._service_name}")

    async def discover(self, service_name: str) -> Peer | None:
        """Get a Peer object for a discovered service, or None if not found."""
        if service_name in self._peer_objects:
            peer = self._peer_objects[service_name]
            if not peer.is_degraded:
                return peer

        if service_name in self._peers:
            peer_info = self._peers[service_name]
            base_url = peer_info.get("base_url", "")
            if base_url:
                peer = Peer(
                    name=service_name,
                    base_url=base_url,
                    hmac_secret=self._config.hmac_secret,
                    timeout=self._config.request_timeout,
                )
                self._peer_objects[service_name] = peer
                return peer

        return None

    async def publish(self, event_type: str, data: dict[str, Any]) -> dict:
        """Publish an event to the ecosystem."""
        return await self._publisher.publish(event_type, data)

    def on(self, event_pattern: str, handler: HandlerFunc | None = None):
        """Register an event handler. Works as method or decorator."""
        result = self._subscriber.on(event_pattern, handler)
        # Update subscriptions list for registration
        if event_pattern not in self._subscriptions:
            self._subscriptions.append(event_pattern)
        return result

    async def handle_webhook(self, envelope: dict[str, Any]) -> None:
        """Process an incoming webhook event."""
        await self._subscriber.dispatch(envelope)

    async def _refresh_peers(self) -> None:
        """Refresh the peer list from discovery."""
        self._peers = await self._discovery.get_peers()
        # Clear cached peer objects for removed peers
        for name in list(self._peer_objects.keys()):
            if name not in self._peers:
                del self._peer_objects[name]
        # Update publisher's peer webhooks for Mode 2
        if self._discovery.mode == DiscoveryMode.PEER_TO_PEER:
            webhooks = {}
            for name, info in self._peers.items():
                base_url = info.get("base_url", "")
                webhooks[name] = {
                    "webhook_url": f"{base_url}{self._config.webhook_path}",
                    "subscriptions": info.get("subscriptions", ["*"]),
                }
            self._publisher.set_peer_webhooks(webhooks)

    async def _periodic_refresh(self) -> None:
        """Periodically re-check discovery and refresh peers."""
        while True:
            await asyncio.sleep(self._config.discovery_interval)
            try:
                old_mode = self._discovery.mode
                new_mode = await self._discovery.detect_mode()
                if new_mode != old_mode:
                    logger.info(
                        f"Mode changed: {old_mode.value} -> {new_mode.value}"
                    )
                    self._publisher._mode = new_mode
                await self._refresh_peers()
            except Exception as e:
                logger.debug(f"Periodic refresh error: {e}")

    @staticmethod
    def _get_local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
