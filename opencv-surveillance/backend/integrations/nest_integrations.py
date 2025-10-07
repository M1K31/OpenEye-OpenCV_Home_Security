# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Nest/Google Smart Device Integration Module
Integrates with Google Smart Device Management (SDM) API for Nest devices

This module enables integration with Nest cameras, doorbells, and other devices
through the Google SDM API. Supports event streaming, camera control, and
sending notifications to Nest Hub displays.
"""

import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
import aiohttp
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
import base64

logger = logging.getLogger(__name__)


class NestDevice:
    """Represents a Nest device"""
    
    def __init__(self, device_id: str, device_data: Dict):
        self.device_id = device_id
        self.name = device_data.get('traits', {}).get('sdm.devices.traits.Info', {}).get('customName', 'Unknown')
        self.type = device_data.get('type', 'Unknown')
        self.traits = device_data.get('traits', {})
        self.parent_relations = device_data.get('parentRelations', [])
        self.raw_data = device_data
    
    @property
    def is_camera(self) -> bool:
        """Check if device is a camera"""
        return 'sdm.devices.types.CAMERA' in self.type or 'sdm.devices.types.DOORBELL' in self.type
    
    @property
    def is_doorbell(self) -> bool:
        """Check if device is a doorbell"""
        return 'sdm.devices.types.DOORBELL' in self.type
    
    def has_trait(self, trait: str) -> bool:
        """Check if device has specific trait"""
        return trait in self.traits


class NestIntegration:
    """
    Main Nest/Google SDM integration class
    
    Handles OAuth authentication, device management, and event streaming
    with Google Smart Device Management API.
    """
    
    # Google SDM API endpoints
    SDM_API_BASE = "https://smartdevicemanagement.googleapis.com/v1"
    
    def __init__(
        self,
        project_id: str,
        client_id: str,
        client_secret: str,
        credentials_file: str = "nest_credentials.json",
        redirect_uri: str = "http://localhost:8080/oauth/callback"
    ):
        """
        Initialize Nest integration
        
        Args:
            project_id: Google Cloud project ID with SDM API enabled
            client_id: OAuth 2.0 client ID
            client_secret: OAuth 2.0 client secret
            credentials_file: File to store OAuth credentials
            redirect_uri: OAuth redirect URI
        """
        self.project_id = project_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.credentials_file = credentials_file
        self.redirect_uri = redirect_uri
        
        self.credentials: Optional[Credentials] = None
        self.devices: Dict[str, NestDevice] = {}
        self.event_callbacks: List[Callable] = []
        
        # Load existing credentials if available
        self._load_credentials()
    
    def _load_credentials(self):
        """Load OAuth credentials from file"""
        try:
            with open(self.credentials_file, 'r') as f:
                cred_data = json.load(f)
                self.credentials = Credentials.from_authorized_user_info(cred_data)
                logger.info("Loaded existing Nest credentials")
        except FileNotFoundError:
            logger.info("No existing credentials found")
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
    
    def _save_credentials(self):
        """Save OAuth credentials to file"""
        try:
            cred_data = {
                'token': self.credentials.token,
                'refresh_token': self.credentials.refresh_token,
                'token_uri': self.credentials.token_uri,
                'client_id': self.credentials.client_id,
                'client_secret': self.credentials.client_secret,
                'scopes': self.credentials.scopes
            }
            
            with open(self.credentials_file, 'w') as f:
                json.dump(cred_data, f)
            
            logger.info("Saved Nest credentials")
        except Exception as e:
            logger.error(f"Error saving credentials: {e}")
    
    def authorize(self):
        """
        Start OAuth authorization flow
        
        Returns URL for user to authorize application
        """
        # Scopes required for SDM API
        scopes = [
            'https://www.googleapis.com/auth/sdm.service',
            'https://www.googleapis.com/auth/pubsub'
        ]
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uris": [self.redirect_uri],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            scopes=scopes,
            redirect_uri=self.redirect_uri
        )
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        logger.info(f"Authorization URL: {auth_url}")
        return auth_url, flow
    
    def complete_authorization(self, flow: Flow, authorization_response: str):
        """
        Complete OAuth authorization with response
        
        Args:
            flow: OAuth flow object from authorize()
            authorization_response: Full callback URL with auth code
        """
        flow.fetch_token(authorization_response=authorization_response)
        self.credentials = flow.credentials
        self._save_credentials()
        logger.info("Authorization completed successfully")
    
    def _refresh_credentials(self):
        """Refresh OAuth credentials if expired"""
        if self.credentials and self.credentials.expired:
            try:
                self.credentials.refresh(Request())
                self._save_credentials()
                logger.info("Refreshed Nest credentials")
            except Exception as e:
                logger.error(f"Error refreshing credentials: {e}")
                raise
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Dict:
        """
        Make authenticated API request
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: Request body data
            
        Returns:
            Response JSON
        """
        self._refresh_credentials()
        
        url = f"{self.SDM_API_BASE}/{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.credentials.token}',
            'Content-Type': 'application/json'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method,
                url,
                headers=headers,
                json=data
            ) as response:
                response.raise_for_status()
                return await response.json()
    
    async def list_devices(self) -> List[NestDevice]:
        """
        List all devices in the project
        
        Returns:
            List of NestDevice objects
        """
        endpoint = f"enterprises/{self.project_id}/devices"
        
        try:
            response = await self._make_request('GET', endpoint)
            devices_data = response.get('devices', [])
            
            self.devices.clear()
            for device_data in devices_data:
                device_id = device_data['name']
                device = NestDevice(device_id, device_data)
                self.devices[device_id] = device
                
                logger.info(f"Found device: {device.name} ({device.type})")
            
            return list(self.devices.values())
        
        except Exception as e:
            logger.error(f"Error listing devices: {e}")
            raise
    
    async def get_camera_stream_url(self, device_id: str) -> Optional[str]:
        """
        Get RTSP stream URL for camera
        
        Args:
            device_id: Nest device ID
            
        Returns:
            RTSP stream URL or None
        """
        device = self.devices.get(device_id)
        if not device or not device.is_camera:
            logger.error(f"Device {device_id} is not a camera")
            return None
        
        endpoint = f"{device_id}:executeCommand"
        command_data = {
            "command": "sdm.devices.commands.CameraLiveStream.GenerateRtspStream"
        }
        
        try:
            response = await self._make_request('POST', endpoint, command_data)
            results = response.get('results', {})
            stream_urls = results.get('streamUrls', {})
            rtsp_url = stream_urls.get('rtspUrl')
            
            # Stream URLs expire after a certain time
            expires_at = results.get('expiresAt')
            logger.info(f"Generated stream URL (expires at {expires_at})")
            
            return rtsp_url
        
        except Exception as e:
            logger.error(f"Error getting stream URL: {e}")
            return None
    
    async def get_camera_image(self, device_id: str) -> Optional[bytes]:
        """
        Get latest camera image
        
        Args:
            device_id: Nest device ID
            
        Returns:
            JPEG image bytes or None
        """
        device = self.devices.get(device_id)
        if not device or not device.is_camera:
            logger.error(f"Device {device_id} is not a camera")
            return None
        
        endpoint = f"{device_id}:executeCommand"
        command_data = {
            "command": "sdm.devices.commands.CameraLiveStream.GenerateImage"
        }
        
        try:
            response = await self._make_request('POST', endpoint, command_data)
            results = response.get('results', {})
            
            # Image is returned as base64 or URL
            if 'url' in results:
                # Download image from URL
                async with aiohttp.ClientSession() as session:
                    async with session.get(results['url']) as img_response:
                        return await img_response.read()
            elif 'imageData' in results:
                # Decode base64 image
                return base64.b64decode(results['imageData'])
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting camera image: {e}")
            return None
    
    async def subscribe_to_events(self, pubsub_topic: str):
        """
        Subscribe to device events via Google Pub/Sub
        
        Args:
            pubsub_topic: Pub/Sub topic name for events
        """
        # This is a simplified version
        # Full implementation requires Google Cloud Pub/Sub client
        
        from google.cloud import pubsub_v1
        
        subscriber = pubsub_v1.SubscriberClient()
        subscription_path = subscriber.subscription_path(
            self.project_id,
            'opencv-surveillance-events'
        )
        
        def callback(message):
            """Process incoming event message"""
            try:
                event_data = json.loads(message.data.decode('utf-8'))
                self._handle_event(event_data)
                message.ack()
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                message.nack()
        
        streaming_pull_future = subscriber.subscribe(
            subscription_path,
            callback=callback
        )
        
        logger.info(f"Subscribed to events on {subscription_path}")
        
        try:
            streaming_pull_future.result()
        except Exception as e:
            streaming_pull_future.cancel()
            logger.error(f"Event subscription error: {e}")
    
    def _handle_event(self, event_data: Dict):
        """
        Handle incoming device event
        
        Args:
            event_data: Event payload
        """
        event_type = event_data.get('eventType')
        device_id = event_data.get('resourceUpdate', {}).get('name')
        timestamp = event_data.get('timestamp')
        
        logger.info(f"Event: {event_type} from {device_id} at {timestamp}")
        
        # Call registered callbacks
        for callback in self.event_callbacks:
            try:
                callback(event_data)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")
    
    def register_event_callback(self, callback: Callable):
        """
        Register callback for device events
        
        Args:
            callback: Function to call with event data
        """
        self.event_callbacks.append(callback)
    
    async def send_notification_to_display(
        self,
        display_device_id: str,
        title: str,
        body: str,
        image_url: Optional[str] = None
    ):
        """
        Send notification to Nest Hub display
        
        Args:
            display_device_id: Nest Hub device ID
            title: Notification title
            body: Notification body text
            image_url: Optional image URL to display
        """
        # Note: This requires the Nest Hub to support notifications
        # Implementation depends on available API capabilities
        
        logger.info(f"Sending notification to {display_device_id}: {title}")
        
        # This is a placeholder - actual implementation depends on
        # available SDM API features for displays
        pass


# Example usage and testing
async def main():
    """Example usage of Nest integration"""
    
    # Initialize integration
    # You need to create a Google Cloud project and enable SDM API
    # Get credentials from Google Cloud Console
    nest = NestIntegration(
        project_id="your-project-id",
        client_id="your-client-id.apps.googleusercontent.com",
        client_secret="your-client-secret"
    )
    
    # First time setup - authorize with Google
    if not nest.credentials:
        auth_url, flow = nest.authorize()
        print(f"Please visit this URL to authorize: {auth_url}")
        
        # After user authorizes, you'll receive a callback
        # authorization_response = input("Paste the full callback URL here: ")
        # nest.complete_authorization(flow, authorization_response)
    
    # List devices
    devices = await nest.list_devices()
    print(f"\nFound {len(devices)} devices:")
    for device in devices:
        print(f"  - {device.name} ({device.type})")
    
    # Get camera stream for first camera
    camera_devices = [d for d in devices if d.is_camera]
    if camera_devices:
        camera = camera_devices[0]
        stream_url = await nest.get_camera_stream_url(camera.device_id)
        print(f"\nStream URL for {camera.name}:")
        print(f"  {stream_url}")
        
        # Get snapshot
        image_bytes = await nest.get_camera_image(camera.device_id)
        if image_bytes:
            # Save snapshot
            with open(f"nest_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg", 'wb') as f:
                f.write(image_bytes)
            print(f"  Saved snapshot ({len(image_bytes)} bytes)")
    
    # Register event callback
    def on_event(event_data):
        print(f"Event received: {event_data.get('eventType')}")
    
    nest.register_event_callback(on_event)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())