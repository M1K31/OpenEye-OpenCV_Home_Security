"""
Webhook System Module
HTTP callback system for sending events to external services

This module manages webhook subscriptions, retries, and delivery of camera events
to external HTTP endpoints. Supports filtering, authentication, and delivery tracking.
"""

import json
import logging
import asyncio
import hashlib
import hmac
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
import aiohttp
from dataclasses import dataclass, asdict, field
from urllib.parse import urlparse
import time

logger = logging.getLogger(__name__)


class WebhookEvent(Enum):
    """Types of events that can trigger webhooks"""
    MOTION_DETECTED = "motion_detected"
    MOTION_ENDED = "motion_ended"
    FACE_DETECTED = "face_detected"
    RECORDING_STARTED = "recording_started"
    RECORDING_STOPPED = "recording_stopped"
    CAMERA_ONLINE = "camera_online"
    CAMERA_OFFLINE = "camera_offline"
    AUDIO_DETECTED = "audio_detected"
    OBJECT_DETECTED = "object_detected"
    ZONE_BREACH = "zone_breach"
    SYSTEM_ALERT = "system_alert"
    ALL = "*"  # Wildcard for all events


@dataclass
class WebhookConfig:
    """Webhook configuration"""
    id: str
    url: str
    events: List[str]  # List of WebhookEvent values
    active: bool = True
    
    # Authentication
    secret: Optional[str] = None  # For HMAC signature
    headers: Dict[str, str] = field(default_factory=dict)
    
    # Filtering
    camera_ids: Optional[List[str]] = None  # If None, all cameras
    
    # Retry configuration
    max_retries: int = 3
    retry_delay: int = 5  # seconds
    timeout: int = 10  # seconds
    
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_triggered: Optional[str] = None
    total_deliveries: int = 0
    failed_deliveries: int = 0


@dataclass
class WebhookPayload:
    """Webhook delivery payload"""
    event_type: str
    camera_id: str
    timestamp: str
    data: Dict[str, Any]
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(asdict(self))
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class WebhookDelivery:
    """Record of webhook delivery attempt"""
    webhook_id: str
    event_type: str
    timestamp: str
    success: bool
    status_code: Optional[int] = None
    response_time: Optional[float] = None  # milliseconds
    error: Optional[str] = None
    retry_count: int = 0


class WebhookManager:
    """
    Manages webhook subscriptions and deliveries
    
    Handles registration, event filtering, delivery with retries,
    and signature verification for secure webhooks.
    """
    
    def __init__(self, database_file: str = "webhooks.json"):
        """
        Initialize webhook manager
        
        Args:
            database_file: File to persist webhook configurations
        """
        self.database_file = database_file
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.delivery_history: List[WebhookDelivery] = []
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Load existing webhooks
        self._load_webhooks()
    
    def _load_webhooks(self):
        """Load webhook configurations from file"""
        try:
            with open(self.database_file, 'r') as f:
                data = json.load(f)
                for webhook_data in data.get('webhooks', []):
                    webhook = WebhookConfig(**webhook_data)
                    self.webhooks[webhook.id] = webhook
            
            logger.info(f"Loaded {len(self.webhooks)} webhooks from {self.database_file}")
        
        except FileNotFoundError:
            logger.info("No existing webhook database found")
        except Exception as e:
            logger.error(f"Error loading webhooks: {e}")
    
    def _save_webhooks(self):
        """Save webhook configurations to file"""
        try:
            data = {
                'webhooks': [asdict(wh) for wh in self.webhooks.values()]
            }
            
            with open(self.database_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug("Saved webhooks to database")
        
        except Exception as e:
            logger.error(f"Error saving webhooks: {e}")
    
    def register_webhook(
        self,
        webhook_id: str,
        url: str,
        events: List[str],
        secret: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        camera_ids: Optional[List[str]] = None,
        max_retries: int = 3,
        retry_delay: int = 5,
        timeout: int = 10
    ) -> WebhookConfig:
        """
        Register a new webhook
        
        Args:
            webhook_id: Unique identifier for webhook
            url: Target URL for webhook
            events: List of event types to subscribe to
            secret: Secret key for HMAC signature (optional)
            headers: Additional HTTP headers
            camera_ids: Filter by specific cameras (None = all)
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries (seconds)
            timeout: Request timeout (seconds)
            
        Returns:
            WebhookConfig object
        """
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme in ['http', 'https']:
            raise ValueError(f"Invalid URL scheme: {parsed.scheme}")
        
        # Validate events
        valid_events = {e.value for e in WebhookEvent}
        for event in events:
            if event not in valid_events:
                raise ValueError(f"Invalid event type: {event}")
        
        webhook = WebhookConfig(
            id=webhook_id,
            url=url,
            events=events,
            secret=secret,
            headers=headers or {},
            camera_ids=camera_ids,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout
        )
        
        self.webhooks[webhook_id] = webhook
        self._save_webhooks()
        
        logger.info(f"Registered webhook: {webhook_id} -> {url}")
        return webhook
    
    def unregister_webhook(self, webhook_id: str):
        """Unregister a webhook"""
        if webhook_id in self.webhooks:
            del self.webhooks[webhook_id]
            self._save_webhooks()
            logger.info(f"Unregistered webhook: {webhook_id}")
    
    def get_webhook(self, webhook_id: str) -> Optional[WebhookConfig]:
        """Get webhook configuration"""
        return self.webhooks.get(webhook_id)
    
    def list_webhooks(self) -> List[WebhookConfig]:
        """List all registered webhooks"""
        return list(self.webhooks.values())
    
    def update_webhook(
        self,
        webhook_id: str,
        active: Optional[bool] = None,
        url: Optional[str] = None,
        events: Optional[List[str]] = None
    ):
        """Update webhook configuration"""
        webhook = self.webhooks.get(webhook_id)
        if not webhook:
            raise ValueError(f"Webhook not found: {webhook_id}")
        
        if active is not None:
            webhook.active = active
        if url is not None:
            webhook.url = url
        if events is not None:
            webhook.events = events
        
        self._save_webhooks()
        logger.info(f"Updated webhook: {webhook_id}")
    
    def _should_trigger(
        self,
        webhook: WebhookConfig,
        event_type: str,
        camera_id: str
    ) -> bool:
        """
        Check if webhook should be triggered for event
        
        Args:
            webhook: Webhook configuration
            event_type: Type of event
            camera_id: Camera that triggered event
            
        Returns:
            True if webhook should be triggered
        """
        # Check if webhook is active
        if not webhook.active:
            return False
        
        # Check event type filter
        if WebhookEvent.ALL.value not in webhook.events and event_type not in webhook.events:
            return False
        
        # Check camera filter
        if webhook.camera_ids is not None and camera_id not in webhook.camera_ids:
            return False
        
        return True
    
    def _generate_signature(self, payload: str, secret: str) -> str:
        """
        Generate HMAC signature for payload
        
        Args:
            payload: JSON payload string
            secret: Secret key
            
        Returns:
            Hex digest of HMAC-SHA256
        """
        signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    async def _deliver_webhook(
        self,
        webhook: WebhookConfig,
        payload: WebhookPayload,
        retry_count: int = 0
    ) -> WebhookDelivery:
        """
        Deliver webhook to endpoint
        
        Args:
            webhook: Webhook configuration
            payload: Event payload
            retry_count: Current retry attempt
            
        Returns:
            WebhookDelivery record
        """
        await self._ensure_session()
        
        # Prepare payload
        payload_json = payload.to_json()
        
        # Prepare headers
        headers = webhook.headers.copy()
        headers['Content-Type'] = 'application/json'
        headers['User-Agent'] = 'OpenCV-Surveillance-Webhook/1.0'
        headers['X-Webhook-Event'] = payload.event_type
        headers['X-Webhook-Timestamp'] = payload.timestamp
        
        # Add signature if secret is configured
        if webhook.secret:
            signature = self._generate_signature(payload_json, webhook.secret)
            headers['X-Webhook-Signature'] = f"sha256={signature}"
        
        # Record delivery attempt
        delivery = WebhookDelivery(
            webhook_id=webhook.id,
            event_type=payload.event_type,
            timestamp=datetime.now().isoformat(),
            success=False,
            retry_count=retry_count
        )
        
        try:
            start_time = time.time()
            
            async with self.session.post(
                webhook.url,
                data=payload_json,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=webhook.timeout)
            ) as response:
                delivery.status_code = response.status
                delivery.response_time = (time.time() - start_time) * 1000
                
                # Consider 2xx status codes as success
                if 200 <= response.status < 300:
                    delivery.success = True
                    webhook.total_deliveries += 1
                    webhook.last_triggered = datetime.now().isoformat()
                    logger.info(
                        f"Webhook {webhook.id} delivered successfully "
                        f"(status: {response.status}, time: {delivery.response_time:.2f}ms)"
                    )
                else:
                    delivery.error = f"HTTP {response.status}"
                    webhook.failed_deliveries += 1
                    logger.warning(
                        f"Webhook {webhook.id} failed with status {response.status}"
                    )
        
        except asyncio.TimeoutError:
            delivery.error = "Request timeout"
            webhook.failed_deliveries += 1
            logger.error(f"Webhook {webhook.id} timed out")
        
        except Exception as e:
            delivery.error = str(e)
            webhook.failed_deliveries += 1
            logger.error(f"Webhook {webhook.id} delivery error: {e}")
        
        # Save delivery history
        self.delivery_history.append(delivery)
        self._save_webhooks()
        
        # Retry if failed and retries remaining
        if not delivery.success and retry_count < webhook.max_retries:
            logger.info(
                f"Retrying webhook {webhook.id} "
                f"(attempt {retry_count + 1}/{webhook.max_retries})"
            )
            await asyncio.sleep(webhook.retry_delay)
            return await self._deliver_webhook(webhook, payload, retry_count + 1)
        
        return delivery
    
    async def trigger_event(
        self,
        event_type: str,
        camera_id: str,
        data: Dict[str, Any]
    ):
        """
        Trigger webhooks for an event
        
        Args:
            event_type: Type of event
            camera_id: Camera identifier
            data: Event data
        """
        payload = WebhookPayload(
            event_type=event_type,
            camera_id=camera_id,
            timestamp=datetime.now().isoformat(),
            data=data
        )
        
        # Find matching webhooks
        matching_webhooks = [
            webhook for webhook in self.webhooks.values()
            if self._should_trigger(webhook, event_type, camera_id)
        ]
        
        if not matching_webhooks:
            logger.debug(f"No webhooks registered for event {event_type} on {camera_id}")
            return
        
        logger.info(
            f"Triggering {len(matching_webhooks)} webhooks for "
            f"{event_type} on {camera_id}"
        )
        
        # Deliver webhooks in parallel
        tasks = [
            self._deliver_webhook(webhook, payload)
            for webhook in matching_webhooks
        ]
        
        await asyncio.gather(*tasks)
    
    async def trigger_motion_detected(
        self,
        camera_id: str,
        confidence: float,
        zones: List[str] = None
    ):
        """Convenience method for motion detection event"""
        await self.trigger_event(
            WebhookEvent.MOTION_DETECTED.value,
            camera_id,
            {
                "confidence": confidence,
                "zones": zones or []
            }
        )
    
    async def trigger_face_detected(
        self,
        camera_id: str,
        face_name: str,
        confidence: float,
        location: Dict[str, int] = None
    ):
        """Convenience method for face detection event"""
        await self.trigger_event(
            WebhookEvent.FACE_DETECTED.value,
            camera_id,
            {
                "face_name": face_name,
                "confidence": confidence,
                "location": location or {}
            }
        )
    
    def get_delivery_stats(self, webhook_id: str) -> Dict[str, Any]:
        """
        Get delivery statistics for a webhook
        
        Args:
            webhook_id: Webhook identifier
            
        Returns:
            Dictionary with statistics
        """
        webhook = self.webhooks.get(webhook_id)
        if not webhook:
            return {}
        
        deliveries = [d for d in self.delivery_history if d.webhook_id == webhook_id]
        
        successful = sum(1 for d in deliveries if d.success)
        failed = sum(1 for d in deliveries if not d.success)
        
        avg_response_time = 0
        if deliveries:
            response_times = [d.response_time for d in deliveries if d.response_time]
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
        
        return {
            "webhook_id": webhook_id,
            "total_deliveries": webhook.total_deliveries,
            "failed_deliveries": webhook.failed_deliveries,
            "success_rate": (successful / len(deliveries) * 100) if deliveries else 0,
            "avg_response_time_ms": avg_response_time,
            "last_triggered": webhook.last_triggered
        }
    
    async def close(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()


# Example webhook receiver (for testing)
from aiohttp import web

async def webhook_receiver(request):
    """Simple webhook receiver for testing"""
    # Verify signature if secret is provided
    signature = request.headers.get('X-Webhook-Signature')
    event_type = request.headers.get('X-Webhook-Event')
    
    payload = await request.text()
    
    print(f"\n{'='*60}")
    print(f"Received webhook: {event_type}")
    print(f"Signature: {signature}")
    print(f"Payload: {payload}")
    print(f"{'='*60}\n")
    
    return web.Response(text="OK")


# Example usage
async def main():
    """Example usage of webhook system"""
    logging.basicConfig(level=logging.INFO)
    
    # Initialize webhook manager
    manager = WebhookManager()
    
    # Register webhooks
    manager.register_webhook(
        webhook_id="webhook_1",
        url="http://localhost:8080/webhook",
        events=[WebhookEvent.MOTION_DETECTED.value, WebhookEvent.FACE_DETECTED.value],
        secret="my_secret_key",
        camera_ids=["camera_1", "camera_2"]
    )
    
    manager.register_webhook(
        webhook_id="webhook_2",
        url="http://example.com/notifications",
        events=[WebhookEvent.ALL.value],  # All events
        headers={"Authorization": "Bearer token123"}
    )
    
    # Trigger some events
    await manager.trigger_motion_detected(
        camera_id="camera_1",
        confidence=0.95,
        zones=["zone_1"]
    )
    
    await manager.trigger_face_detected(
        camera_id="camera_1",
        face_name="John Doe",
        confidence=0.92,
        location={"x": 100, "y": 150, "width": 200, "height": 250}
    )
    
    # Get stats
    stats = manager.get_delivery_stats("webhook_1")
    print(f"\nWebhook Stats: {json.dumps(stats, indent=2)}")
    
    # Cleanup
    await manager.close()


if __name__ == "__main__":
    asyncio.run(main())