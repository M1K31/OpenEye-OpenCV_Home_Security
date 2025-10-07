# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Home Assistant Integration Module
Provides MQTT discovery, entity management, and event publishing for Home Assistant

This module enables automatic discovery of cameras and sensors in Home Assistant
using MQTT discovery protocol. It creates camera entities, motion sensors, and
publishes events for automation triggers.
"""

import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
import paho.mqtt.client as mqtt
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class HADevice:
    """Home Assistant device information"""
    identifiers: List[str]
    name: str
    manufacturer: str = "OpenCV Surveillance"
    model: str = "Security Camera"
    sw_version: str = "1.0.0"


@dataclass
class HACamera:
    """Home Assistant camera entity configuration"""
    name: str
    unique_id: str
    topic: str
    device: HADevice
    availability_topic: Optional[str] = None
    icon: str = "mdi:cctv"
    

@dataclass
class HABinarySensor:
    """Home Assistant binary sensor configuration (motion detection)"""
    name: str
    unique_id: str
    state_topic: str
    device_class: str
    device: HADevice
    availability_topic: Optional[str] = None
    payload_on: str = "ON"
    payload_off: str = "OFF"


class HomeAssistantIntegration:
    """
    Main Home Assistant integration class
    
    Handles MQTT connection, discovery, and state publishing for all
    camera entities, motion sensors, and events.
    """
    
    def __init__(
        self,
        mqtt_host: str = "localhost",
        mqtt_port: int = 1883,
        mqtt_username: Optional[str] = None,
        mqtt_password: Optional[str] = None,
        discovery_prefix: str = "homeassistant",
        state_prefix: str = "opencv_surveillance"
    ):
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_username = mqtt_username
        self.mqtt_password = mqtt_password
        self.discovery_prefix = discovery_prefix
        self.state_prefix = state_prefix
        
        # MQTT client setup
        self.client = mqtt.Client(client_id="opencv_surveillance")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        if mqtt_username and mqtt_password:
            self.client.username_pw_set(mqtt_username, mqtt_password)
        
        self.connected = False
        self.registered_entities: Dict[str, Dict] = {}
        
    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.client.connect(self.mqtt_host, self.mqtt_port, 60)
            self.client.loop_start()
            logger.info(f"Connecting to MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Disconnected from MQTT broker")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.connected = True
            logger.info("Successfully connected to MQTT broker")
            # Resubscribe to topics if needed
            self.client.subscribe(f"{self.state_prefix}/+/command")
        else:
            logger.error(f"Failed to connect to MQTT broker with code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.connected = False
        logger.warning(f"Disconnected from MQTT broker with code: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Callback for incoming MQTT messages"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            logger.debug(f"Received message on topic {topic}: {payload}")
            
            # Handle camera commands from Home Assistant
            if "/command" in topic:
                camera_id = topic.split('/')[1]
                self._handle_camera_command(camera_id, payload)
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def _handle_camera_command(self, camera_id: str, command: str):
        """Handle commands sent from Home Assistant"""
        logger.info(f"Camera {camera_id} received command: {command}")
        # Implement command handling (start recording, snapshot, etc.)
        # This would integrate with your camera manager
    
    def register_camera(
        self,
        camera_id: str,
        camera_name: str,
        stream_url: str
    ):
        """
        Register a camera with Home Assistant via MQTT discovery
        
        Args:
            camera_id: Unique identifier for the camera
            camera_name: Friendly name for the camera
            stream_url: URL for camera stream (MJPEG or HLS)
        """
        device = HADevice(
            identifiers=[f"opencv_surveillance_{camera_id}"],
            name=camera_name
        )
        
        # Camera entity discovery
        camera_config = {
            "name": camera_name,
            "unique_id": f"opencv_surveillance_camera_{camera_id}",
            "topic": f"{self.state_prefix}/{camera_id}/image",
            "availability_topic": f"{self.state_prefix}/{camera_id}/availability",
            "device": asdict(device),
            "icon": "mdi:cctv"
        }
        
        # If stream URL is available, use stream component
        if stream_url:
            camera_config["stream_source"] = stream_url
        
        discovery_topic = f"{self.discovery_prefix}/camera/{camera_id}/config"
        
        self.client.publish(
            discovery_topic,
            json.dumps(camera_config),
            retain=True
        )
        
        # Set camera as available
        self.client.publish(
            f"{self.state_prefix}/{camera_id}/availability",
            "online",
            retain=True
        )
        
        self.registered_entities[camera_id] = camera_config
        logger.info(f"Registered camera {camera_name} with Home Assistant")
        
        # Also register motion sensor for this camera
        self.register_motion_sensor(camera_id, camera_name)
    
    def register_motion_sensor(self, camera_id: str, camera_name: str):
        """
        Register a motion sensor for a camera
        
        Args:
            camera_id: Unique identifier for the camera
            camera_name: Friendly name for the camera
        """
        device = HADevice(
            identifiers=[f"opencv_surveillance_{camera_id}"],
            name=camera_name
        )
        
        sensor_config = {
            "name": f"{camera_name} Motion",
            "unique_id": f"opencv_surveillance_motion_{camera_id}",
            "state_topic": f"{self.state_prefix}/{camera_id}/motion",
            "device_class": "motion",
            "device": asdict(device),
            "availability_topic": f"{self.state_prefix}/{camera_id}/availability",
            "payload_on": "ON",
            "payload_off": "OFF"
        }
        
        discovery_topic = f"{self.discovery_prefix}/binary_sensor/{camera_id}_motion/config"
        
        self.client.publish(
            discovery_topic,
            json.dumps(sensor_config),
            retain=True
        )
        
        logger.info(f"Registered motion sensor for {camera_name}")
    
    def publish_motion_event(self, camera_id: str, motion_detected: bool):
        """
        Publish motion detection state
        
        Args:
            camera_id: Camera identifier
            motion_detected: True if motion detected, False otherwise
        """
        state = "ON" if motion_detected else "OFF"
        topic = f"{self.state_prefix}/{camera_id}/motion"
        
        self.client.publish(topic, state, retain=False)
        logger.debug(f"Published motion state for {camera_id}: {state}")
    
    def publish_face_detected_event(
        self,
        camera_id: str,
        face_name: str,
        confidence: float,
        timestamp: datetime
    ):
        """
        Publish face detection event
        
        Args:
            camera_id: Camera identifier
            face_name: Name of recognized face or "unknown"
            confidence: Confidence score (0-1)
            timestamp: When face was detected
        """
        event_data = {
            "camera_id": camera_id,
            "face_name": face_name,
            "confidence": confidence,
            "timestamp": timestamp.isoformat(),
            "event_type": "face_detected"
        }
        
        topic = f"{self.state_prefix}/events/face_detected"
        
        self.client.publish(topic, json.dumps(event_data), retain=False)
        logger.info(f"Published face detection event for {camera_id}: {face_name}")
    
    def publish_camera_snapshot(self, camera_id: str, image_bytes: bytes):
        """
        Publish camera snapshot as JPEG
        
        Args:
            camera_id: Camera identifier
            image_bytes: JPEG encoded image bytes
        """
        topic = f"{self.state_prefix}/{camera_id}/image"
        self.client.publish(topic, image_bytes, retain=False)
    
    def set_camera_availability(self, camera_id: str, available: bool):
        """
        Update camera availability status
        
        Args:
            camera_id: Camera identifier
            available: True if camera is available
        """
        state = "online" if available else "offline"
        topic = f"{self.state_prefix}/{camera_id}/availability"
        
        self.client.publish(topic, state, retain=True)
        logger.info(f"Set camera {camera_id} availability to {state}")
    
    def unregister_camera(self, camera_id: str):
        """
        Unregister a camera from Home Assistant
        
        Args:
            camera_id: Camera identifier
        """
        # Send empty config to remove from Home Assistant
        camera_topic = f"{self.discovery_prefix}/camera/{camera_id}/config"
        motion_topic = f"{self.discovery_prefix}/binary_sensor/{camera_id}_motion/config"
        
        self.client.publish(camera_topic, "", retain=True)
        self.client.publish(motion_topic, "", retain=True)
        
        if camera_id in self.registered_entities:
            del self.registered_entities[camera_id]
        
        logger.info(f"Unregistered camera {camera_id} from Home Assistant")
    
    def publish_system_sensor(self, sensor_name: str, state: Any, unit: str = None):
        """
        Publish system-level sensor (CPU usage, storage, etc.)
        
        Args:
            sensor_name: Name of the sensor
            state: Current state/value
            unit: Unit of measurement (optional)
        """
        sensor_id = sensor_name.lower().replace(" ", "_")
        
        # Register sensor if not already registered
        if sensor_id not in self.registered_entities:
            device = HADevice(
                identifiers=["opencv_surveillance_system"],
                name="OpenCV Surveillance System"
            )
            
            sensor_config = {
                "name": sensor_name,
                "unique_id": f"opencv_surveillance_{sensor_id}",
                "state_topic": f"{self.state_prefix}/system/{sensor_id}",
                "device": asdict(device)
            }
            
            if unit:
                sensor_config["unit_of_measurement"] = unit
            
            discovery_topic = f"{self.discovery_prefix}/sensor/{sensor_id}/config"
            self.client.publish(discovery_topic, json.dumps(sensor_config), retain=True)
            self.registered_entities[sensor_id] = sensor_config
        
        # Publish state
        topic = f"{self.state_prefix}/system/{sensor_id}"
        self.client.publish(topic, str(state), retain=True)


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Initialize Home Assistant integration
    ha = HomeAssistantIntegration(
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_username="homeassistant",
        mqtt_password="password"
    )
    
    # Connect to MQTT broker
    ha.connect()
    
    # Wait for connection
    import time
    time.sleep(2)
    
    # Register cameras
    ha.register_camera(
        camera_id="camera_1",
        camera_name="Front Door Camera",
        stream_url="http://localhost:8081/camera/1/stream"
    )
    
    ha.register_camera(
        camera_id="camera_2",
        camera_name="Backyard Camera",
        stream_url="http://localhost:8081/camera/2/stream"
    )
    
    # Simulate motion detection
    ha.publish_motion_event("camera_1", True)
    time.sleep(5)
    ha.publish_motion_event("camera_1", False)
    
    # Simulate face detection
    ha.publish_face_detected_event(
        camera_id="camera_1",
        face_name="John Doe",
        confidence=0.95,
        timestamp=datetime.now()
    )
    
    # Publish system sensors
    ha.publish_system_sensor("CPU Usage", 45.2, "%")
    ha.publish_system_sensor("Storage Used", 125.5, "GB")
    
    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        ha.disconnect()