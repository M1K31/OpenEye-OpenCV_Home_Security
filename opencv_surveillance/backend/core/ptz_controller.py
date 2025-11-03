# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
PTZ Controller Module
Handles Pan-Tilt-Zoom camera control operations
Supports ONVIF protocol and direct PTZ commands
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import asyncio
import threading
import time


class PTZController:
    """
    PTZ Camera Controller
    Handles camera movement, presets, and patrol patterns
    """

    def __init__(self, camera_id: str, ptz_type: str = "onvif"):
        """
        Initialize PTZ controller

        Args:
            camera_id: Unique camera identifier
            ptz_type: PTZ protocol type ("onvif", "pelco-d", "pelco-p", "visca")
        """
        self.camera_id = camera_id
        self.ptz_type = ptz_type
        self.onvif_device = None
        self.ptz_service = None
        self.media_profile = None
        self.is_connected = False

        # Movement limits (normalized -1.0 to 1.0)
        self.pan_min = -1.0
        self.pan_max = 1.0
        self.tilt_min = -1.0
        self.tilt_max = 1.0
        self.zoom_min = 0.0
        self.zoom_max = 1.0

        # Current position cache
        self.current_position = {
            "pan": 0.0,
            "tilt": 0.0,
            "zoom": 0.0
        }

    async def connect(self, camera_ip: str, port: int = 80, username: str = "", password: str = "") -> bool:
        """
        Connect to PTZ camera via ONVIF

        Args:
            camera_ip: Camera IP address
            port: ONVIF port (default 80)
            username: Camera username
            password: Camera password

        Returns:
            True if connection successful, False otherwise
        """
        if self.ptz_type == "onvif":
            try:
                from onvif import ONVIFCamera

                # Create ONVIF camera instance
                self.onvif_device = ONVIFCamera(
                    camera_ip,
                    port,
                    username,
                    password
                )

                # Get PTZ service
                self.ptz_service = self.onvif_device.create_ptz_service()

                # Get media service and profile
                media_service = self.onvif_device.create_media_service()
                profiles = media_service.GetProfiles()

                if profiles:
                    self.media_profile = profiles[0]
                    self.is_connected = True
                    print(f"PTZ connected to camera {self.camera_id} at {camera_ip}")
                    return True
                else:
                    print(f"No media profiles found for camera {self.camera_id}")
                    return False

            except Exception as e:
                print(f"Failed to connect to PTZ camera {self.camera_id}: {e}")
                self.is_connected = False
                return False
        else:
            # Other PTZ types not yet implemented
            print(f"PTZ type {self.ptz_type} not yet supported")
            return False

    def disconnect(self):
        """Disconnect from PTZ camera"""
        self.onvif_device = None
        self.ptz_service = None
        self.media_profile = None
        self.is_connected = False

    async def move_absolute(self, pan: float, tilt: float, zoom: float, speed: float = 0.5) -> bool:
        """
        Move camera to absolute position

        Args:
            pan: Pan position (-1.0 to 1.0)
            tilt: Tilt position (-1.0 to 1.0)
            zoom: Zoom level (0.0 to 1.0)
            speed: Movement speed (0.0 to 1.0)

        Returns:
            True if command sent successfully
        """
        if not self.is_connected or not self.ptz_service:
            print(f"PTZ not connected for camera {self.camera_id}")
            return False

        try:
            # Clamp values to valid ranges
            pan = max(self.pan_min, min(self.pan_max, pan))
            tilt = max(self.tilt_min, min(self.tilt_max, tilt))
            zoom = max(self.zoom_min, min(self.zoom_max, zoom))

            # Create absolute move request
            request = self.ptz_service.create_type('AbsoluteMove')
            request.ProfileToken = self.media_profile.token

            # Set position
            request.Position = {
                'PanTilt': {'x': pan, 'y': tilt},
                'Zoom': {'x': zoom}
            }

            # Set speed
            request.Speed = {
                'PanTilt': {'x': speed, 'y': speed},
                'Zoom': {'x': speed}
            }

            # Send command
            self.ptz_service.AbsoluteMove(request)

            # Update position cache
            self.current_position = {"pan": pan, "tilt": tilt, "zoom": zoom}

            return True

        except Exception as e:
            print(f"PTZ absolute move failed for camera {self.camera_id}: {e}")
            return False

    async def move_relative(self, pan_delta: float, tilt_delta: float, zoom_delta: float, speed: float = 0.5) -> bool:
        """
        Move camera relative to current position

        Args:
            pan_delta: Pan movement (-1.0 to 1.0)
            tilt_delta: Tilt movement (-1.0 to 1.0)
            zoom_delta: Zoom change (-1.0 to 1.0)
            speed: Movement speed (0.0 to 1.0)

        Returns:
            True if command sent successfully
        """
        if not self.is_connected or not self.ptz_service:
            return False

        try:
            request = self.ptz_service.create_type('RelativeMove')
            request.ProfileToken = self.media_profile.token

            # Set translation
            request.Translation = {
                'PanTilt': {'x': pan_delta, 'y': tilt_delta},
                'Zoom': {'x': zoom_delta}
            }

            # Set speed
            request.Speed = {
                'PanTilt': {'x': speed, 'y': speed},
                'Zoom': {'x': speed}
            }

            # Send command
            self.ptz_service.RelativeMove(request)

            return True

        except Exception as e:
            print(f"PTZ relative move failed for camera {self.camera_id}: {e}")
            return False

    async def move_continuous(self, pan_velocity: float, tilt_velocity: float, zoom_velocity: float) -> bool:
        """
        Start continuous camera movement

        Args:
            pan_velocity: Pan velocity (-1.0 to 1.0)
            tilt_velocity: Tilt velocity (-1.0 to 1.0)
            zoom_velocity: Zoom velocity (-1.0 to 1.0)

        Returns:
            True if command sent successfully
        """
        if not self.is_connected or not self.ptz_service:
            return False

        try:
            request = self.ptz_service.create_type('ContinuousMove')
            request.ProfileToken = self.media_profile.token

            # Set velocity
            request.Velocity = {
                'PanTilt': {'x': pan_velocity, 'y': tilt_velocity},
                'Zoom': {'x': zoom_velocity}
            }

            # Send command
            self.ptz_service.ContinuousMove(request)

            return True

        except Exception as e:
            print(f"PTZ continuous move failed for camera {self.camera_id}: {e}")
            return False

    async def stop(self) -> bool:
        """
        Stop all camera movement

        Returns:
            True if command sent successfully
        """
        if not self.is_connected or not self.ptz_service:
            return False

        try:
            request = self.ptz_service.create_type('Stop')
            request.ProfileToken = self.media_profile.token
            request.PanTilt = True
            request.Zoom = True

            # Send command
            self.ptz_service.Stop(request)

            return True

        except Exception as e:
            print(f"PTZ stop failed for camera {self.camera_id}: {e}")
            return False

    async def goto_preset(self, preset_number: int, speed: float = 0.5) -> bool:
        """
        Move camera to saved preset position

        Args:
            preset_number: Preset slot number (1-255)
            speed: Movement speed (0.0 to 1.0)

        Returns:
            True if command sent successfully
        """
        if not self.is_connected or not self.ptz_service:
            return False

        try:
            request = self.ptz_service.create_type('GotoPreset')
            request.ProfileToken = self.media_profile.token
            request.PresetToken = str(preset_number)
            request.Speed = {
                'PanTilt': {'x': speed, 'y': speed},
                'Zoom': {'x': speed}
            }

            # Send command
            self.ptz_service.GotoPreset(request)

            return True

        except Exception as e:
            print(f"PTZ goto preset failed for camera {self.camera_id}: {e}")
            return False

    async def set_preset(self, preset_number: int, preset_name: str = "") -> bool:
        """
        Save current position as preset

        Args:
            preset_number: Preset slot number (1-255)
            preset_name: Optional preset name

        Returns:
            True if command sent successfully
        """
        if not self.is_connected or not self.ptz_service:
            return False

        try:
            request = self.ptz_service.create_type('SetPreset')
            request.ProfileToken = self.media_profile.token
            request.PresetToken = str(preset_number)
            if preset_name:
                request.PresetName = preset_name

            # Send command
            self.ptz_service.SetPreset(request)

            return True

        except Exception as e:
            print(f"PTZ set preset failed for camera {self.camera_id}: {e}")
            return False

    async def get_status(self) -> Optional[Dict[str, Any]]:
        """
        Get current PTZ status including position

        Returns:
            Dictionary with PTZ status or None if failed
        """
        if not self.is_connected or not self.ptz_service:
            return None

        try:
            request = self.ptz_service.create_type('GetStatus')
            request.ProfileToken = self.media_profile.token

            status = self.ptz_service.GetStatus(request)

            if status.Position:
                pan = status.Position.PanTilt.x if status.Position.PanTilt else 0.0
                tilt = status.Position.PanTilt.y if status.Position.PanTilt else 0.0
                zoom = status.Position.Zoom.x if status.Position.Zoom else 0.0

                # Update cache
                self.current_position = {"pan": pan, "tilt": tilt, "zoom": zoom}

                return {
                    "pan": pan,
                    "tilt": tilt,
                    "zoom": zoom,
                    "moving": status.MoveStatus is not None
                }

            return self.current_position

        except Exception as e:
            print(f"PTZ get status failed for camera {self.camera_id}: {e}")
            return self.current_position


# Global registry of PTZ controllers
_ptz_controllers: Dict[str, PTZController] = {}


def get_ptz_controller(camera_id: str, ptz_type: str = "onvif") -> PTZController:
    """
    Get or create PTZ controller for a camera

    Args:
        camera_id: Camera identifier
        ptz_type: PTZ protocol type

    Returns:
        PTZController instance
    """
    if camera_id not in _ptz_controllers:
        _ptz_controllers[camera_id] = PTZController(camera_id, ptz_type)

    return _ptz_controllers[camera_id]


def remove_ptz_controller(camera_id: str):
    """
    Remove PTZ controller from registry

    Args:
        camera_id: Camera identifier
    """
    if camera_id in _ptz_controllers:
        controller = _ptz_controllers[camera_id]
        controller.disconnect()
        del _ptz_controllers[camera_id]
