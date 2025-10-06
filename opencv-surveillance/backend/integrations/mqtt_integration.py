"""
MQTT Integration Module
Generic MQTT client for publishing camera events and receiving commands

This module provides a flexible MQTT interface for publishing camera events,
motion detection, face recognition results, and receiving control commands.
Compatible with any MQTT broker (Mosquitto, HiveMQ, etc.)
"""

import json
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import paho.mqtt.client as mqtt
from dataclasses import dataclass, asdict
import time

logger = logging.getLogger(__name__)


class QoS(Enum):
    """MQTT Quality of Service levels"""
    AT_MOST_ONCE = 0
    AT_LEAST_ONCE = 1
    EXACTLY_ONCE = 2


@dataclass
class MQTTConfig:
    """MQTT connection configuration"""
    host: str = "localhost"
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: str = "opencv_surveillance"
    keepalive: int = 60
    clean_session: bool = True
    
    # TLS/SSL configuration
    use_tls: bool = False
    ca_certs: Optional[str] = None
    certfile: Optional[str] = None
    keyfile: Optional[str] = None
    
    # Topic configuration
    base_topic: str = "surveillance"
    status_topic: str = "surveillance/status"
    command_topic: str = "surveillance/command"


@dataclass
class CameraEvent:
    """Camera event data structure"""
    camera_id: str
    event_type: str  # motion, face_detected, recording_started, etc.
    timestamp: str
    data: Dict[str, Any]
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(asdict(self))


class MQTTIntegration:
    """
    Main MQTT integration class
    
    Provides publish/subscribe functionality for camera events and commands.
    Supports automatic reconnection, QoS levels, and message persistence.
    """
    
    def __init__(self, config: MQTTConfig):
        """
        Initialize MQTT integration
        
        Args:
            config: MQTT configuration object
        """
        self.config = config
        self.client = mqtt.Client(
            client_id=config.client_id,
            clean_session=config.clean_session
        )
        
        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish
        self.client.on_subscribe = self._on_subscribe
        
        # Set authentication
        if config.username and config.password:
            self.client.username_pw_set(config.username, config.password)
        
        # Set TLS/SSL
        if config.use_tls:
            self.client.tls_set(
                ca_certs=config.ca_certs,
                certfile=config.certfile,
                keyfile=config.keyfile
            )
        
        self.connected = False
        self.subscriptions: Dict[str, Callable] = {}
        self._lock = threading.Lock()
        
        logger.info(f"MQTT client initialized: {config.client_id}")
    
    def connect(self) -> bool:
        """
        Connect to MQTT broker
        
        Returns:
            True if connection successful
        """
        try:
            logger.info(f"Connecting to MQTT broker at {self.config.host}:{self.config.port}")
            self.client.connect(
                self.config.host,
                self.config.port,
                self.config.keepalive
            )
            
            # Start network loop
            self.client.loop_start()
            
            # Wait for connection (with timeout)
            timeout = 10
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if self.connected:
                logger.info("Successfully connected to MQTT broker")
                return True
            else:
                logger.error("Connection timeout")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Disconnected from MQTT broker")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")
            
            # Publish online status
            self.publish_status("online")
            
            # Resubscribe to all topics
            self._resubscribe()
        else:
            error_messages = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized"
            }
            logger.error(f"Connection failed: {error_messages.get(rc, f'Unknown error {rc}')}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker (code: {rc})")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """Callback for incoming messages"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            logger.debug(f"Received message on topic '{topic}': {payload}")
            
            # Call registered callback for this topic
            with self._lock:
                for pattern, callback in self.subscriptions.items():
                    if mqtt.topic_matches_sub(pattern, topic):
                        try:
                            callback(topic, payload)
                        except Exception as e:
                            logger.error(f"Error in message callback: {e}")
        
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _on_publish(self, client, userdata, mid):
        """Callback when message is published"""
        logger.debug(f"Message published (mid: {mid})")
    
    def _on_subscribe(self, client, userdata, mid, granted_qos):
        """Callback when subscription is confirmed"""
        logger.debug(f"Subscription confirmed (mid: {mid}, QoS: {granted_qos})")
    
    def _resubscribe(self):
        """Resubscribe to all topics after reconnection"""
        with self._lock:
            for topic in self.subscriptions.keys():
                self.client.subscribe(topic)
                logger.debug(f"Resubscribed to topic: {topic}")
    
    def publish(
        self,
        topic: str,
        payload: Any,
        qos: QoS = QoS.AT_MOST_ONCE,
        retain: bool = False
    ) -> bool:
        """
        Publish message to topic
        
        Args:
            topic: Topic to publish to
            payload: Message payload (str, dict, or bytes)
            qos: Quality of Service level
            retain: Whether to retain message
            
        Returns:
            True if publish successful
        """
        try:
            # Convert payload to string if dict
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            
            result = self.client.publish(
                topic,
                payload,
                qos=qos.value,
                retain=retain
            )
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Published to {topic}: {payload}")
                return True
            else:
                logger.error(f"Failed to publish to {topic}: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return False
    
    def subscribe(
        self,
        topic: str,
        callback: Callable[[str, str], None],
        qos: QoS = QoS.AT_MOST_ONCE
    ):
        """
        Subscribe to topic with callback
        
        Args:
            topic: Topic pattern to subscribe to (supports wildcards)
            callback: Function to call with (topic, payload)
            qos: Quality of Service level
        """
        with self._lock:
            self.subscriptions[topic] = callback
        
        self.client.subscribe(topic, qos=qos.value)
        logger.info(f"Subscribed to topic: {topic}")
    
    def unsubscribe(self, topic: str):
        """Unsubscribe from topic"""
        with self._lock:
            if topic in self.subscriptions:
                del self.subscriptions[topic]
        
        self.client.unsubscribe(topic)
        logger.info(f"Unsubscribed from topic: {topic}")
    
    def publish_status(self, status: str):
        """Publish system status"""
        self.publish(
            self.config.status_topic,
            {"status": status, "timestamp": datetime.now().isoformat()},
            retain=True
        )
    
    def publish_camera_event(
        self,
        camera_id: str,
        event_type: str,
        data: Dict[str, Any]
    ):
        """
        Publish camera event
        
        Args:
            camera_id: Camera identifier
            event_type: Type of event
            data: Event data
        """
        event = CameraEvent(
            camera_id=camera_id,
            event_type=event_type,
            timestamp=datetime.now().isoformat(),
            data=data
        )
        
        topic = f"{self.config.base_topic}/camera/{camera_id}/event"
        self.publish(topic, event.to_json(), qos=QoS.AT_LEAST_ONCE)
    
    def publish_motion_detected(
        self,
        camera_id: str,
        detected: bool,
        confidence: float = 1.0,
        zones: List[str] = None
    ):
        """Publish motion detection event"""
        data = {
            "detected": detected,
            "confidence": confidence,
            "zones": zones or []
        }
        
        # Publish to motion-specific topic
        topic = f"{self.config.base_topic}/camera/{camera_id}/motion"
        self.publish(topic, "ON" if detected else "OFF", retain=True)
        
        # Also publish as event
        if detected:
            self.publish_camera_event(camera_id, "motion_detected", data)
    
    def publish_face_detected(
        self,
        camera_id: str,
        face_name: str,
        confidence: float,
        location: Dict[str, int] = None
    ):
        """Publish face detection event"""
        data = {
            "face_name": face_name,
            "confidence": confidence,
            "location": location or {}
        }
        
        self.publish_camera_event(camera_id, "face_detected", data)
    
    def publish_recording_event(
        self,
        camera_id: str,
        recording: bool,
        filename: str = None
    ):
        """Publish recording start/stop event"""
        data = {
            "recording": recording,
            "filename": filename
        }
        
        event_type = "recording_started" if recording else "recording_stopped"
        self.publish_camera_event(camera_id, event_type, data)
    
    def publish_snapshot(
        self,
        camera_id: str,
        image_bytes: bytes,
        metadata: Dict[str, Any] = None
    ):
        """
        Publish camera snapshot
        
        Args:
            camera_id: Camera identifier
            image_bytes: JPEG image bytes
            metadata: Additional metadata
        """
        topic = f"{self.config.base_topic}/camera/{camera_id}/snapshot"
        self.publish(topic, image_bytes, qos=QoS.AT_MOST_ONCE)
        
        # Publish metadata separately
        if metadata:
            meta_topic = f"{self.config.base_topic}/camera/{camera_id}/snapshot/metadata"
            self.publish(meta_topic, metadata)
    
    def publish_system_metrics(
        self,
        cpu_percent: float,
        memory_percent: float,
        disk_usage_gb: float,
        active_cameras: int
    ):
        """Publish system performance metrics"""
        metrics = {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "disk_usage_gb": disk_usage_gb,
            "active_cameras": active_cameras,
            "timestamp": datetime.now().isoformat()
        }
        
        topic = f"{self.config.base_topic}/system/metrics"
        self.publish(topic, metrics, retain=True)
    
    def subscribe_to_commands(self, callback: Callable[[str, Dict], None]):
        """
        Subscribe to command topic
        
        Args:
            callback: Function to call with (camera_id, command_data)
        """
        def command_handler(topic: str, payload: str):
            try:
                # Extract camera_id from topic
                # Expected format: surveillance/command/camera_id
                parts = topic.split('/')
                if len(parts) >= 3:
                    camera_id = parts[2]
                    command_data = json.loads(payload)
                    callback(camera_id, command_data)
            except Exception as e:
                logger.error(f"Error handling command: {e}")
        
        command_topic = f"{self.config.command_topic}/+"
        self.subscribe(command_topic, command_handler, qos=QoS.AT_LEAST_ONCE)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Configure MQTT
    config = MQTTConfig(
        host="localhost",
        port=1883,
        username="surveillance",
        password="password",
        base_topic="surveillance"
    )
    
    # Initialize integration
    mqtt_integration = MQTTIntegration(config)
    
    # Define command handler
    def handle_command(camera_id: str, command: Dict):
        logger.info(f"Command for {camera_id}: {command}")
        
        cmd_type = command.get('type')
        
        if cmd_type == 'start_recording':
            logger.info(f"Starting recording on {camera_id}")
        elif cmd_type == 'stop_recording':
            logger.info(f"Stopping recording on {camera_id}")
        elif cmd_type == 'snapshot':
            logger.info(f"Taking snapshot on {camera_id}")
        elif cmd_type == 'enable_motion_detection':
            logger.info(f"Enabling motion detection on {camera_id}")
        elif cmd_type == 'disable_motion_detection':
            logger.info(f"Disabling motion detection on {camera_id}")
    
    # Connect to broker
    if mqtt_integration.connect():
        # Subscribe to commands
        mqtt_integration.subscribe_to_commands(handle_command)
        
        # Simulate publishing events
        import time
        
        try:
            while True:
                # Publish motion detection
                mqtt_integration.publish_motion_detected(
                    "camera_1",
                    True,
                    confidence=0.92,
                    zones=["zone_1", "zone_2"]
                )
                
                time.sleep(2)
                
                mqtt_integration.publish_motion_detected(
                    "camera_1",
                    False
                )
                
                # Publish face detection
                mqtt_integration.publish_face_detected(
                    "camera_1",
                    "John Doe",
                    confidence=0.95,
                    location={"x": 100, "y": 150, "width": 200, "height": 250}
                )
                
                # Publish system metrics
                mqtt_integration.publish_system_metrics(
                    cpu_percent=45.2,
                    memory_percent=62.8,
                    disk_usage_gb=125.5,
                    active_cameras=3
                )
                
                time.sleep(10)
                
        except KeyboardInterrupt:
            mqtt_integration.publish_status("offline")
            mqtt_integration.disconnect()