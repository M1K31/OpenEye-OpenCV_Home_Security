# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Camera Discovery Service
Discovers RTSP/IP cameras on network and USB cameras connected to the system.
"""
import cv2
import socket
import subprocess
import platform
import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
import netifaces
import ipaddress

logger = logging.getLogger(__name__)


class CameraDiscovery:
    """
    Service for discovering cameras on the network and connected hardware.
    """
    
    def __init__(self):
        self.discovered_cameras = []
        self.scanning = False
        
    async def discover_usb_cameras(self) -> List[Dict]:
        """
        Discover USB and built-in cameras connected to the system.
        
        Returns:
            List of discovered USB cameras with their properties
        """
        logger.info("Starting USB camera discovery...")
        usb_cameras = []
        
        # Test camera indices 0-10
        for index in range(11):
            try:
                cap = cv2.VideoCapture(index)
                if cap.isOpened():
                    # Get camera properties
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps = int(cap.get(cv2.CAP_PROP_FPS))
                    
                    # Try to read a frame to verify camera works
                    ret, frame = cap.read()
                    
                    if ret:
                        camera_info = {
                            'type': 'usb',
                            'index': index,
                            'name': f'USB Camera {index}',
                            'device_path': self._get_device_path(index),
                            'resolution': f'{width}x{height}',
                            'fps': fps if fps > 0 else 30,
                            'status': 'available',
                            'auto_config': {
                                'camera_id': f'usb_camera_{index}',
                                'camera_type': 'usb',
                                'source': str(index),
                                'enabled': True
                            },
                            'discovered_at': datetime.now().isoformat()
                        }
                        
                        usb_cameras.append(camera_info)
                        logger.info(f"Found USB camera at index {index}: {width}x{height} @ {fps}fps")
                    
                    cap.release()
                    
            except Exception as e:
                logger.debug(f"No camera at index {index}: {e}")
                continue
        
        logger.info(f"USB camera discovery complete. Found {len(usb_cameras)} cameras")
        return usb_cameras
    
    def _get_device_path(self, index: int) -> str:
        """Get the device path for a camera index (platform-specific)"""
        system = platform.system()
        if system == 'Linux':
            return f'/dev/video{index}'
        elif system == 'Darwin':  # macOS
            return f'AVFoundation:{index}'
        elif system == 'Windows':
            return f'DirectShow:{index}'
        else:
            return f'index:{index}'
    
    async def discover_network_cameras(self, subnet: Optional[str] = None) -> List[Dict]:
        """
        Discover RTSP/IP cameras on the local network.
        
        Args:
            subnet: Optional subnet to scan (e.g., '192.168.1.0/24')
                   If None, will scan all local subnets
        
        Returns:
            List of discovered network cameras
        """
        logger.info("Starting network camera discovery...")
        self.scanning = True
        network_cameras = []
        
        try:
            # Get local subnets if none specified
            if subnet is None:
                subnets = self._get_local_subnets()
            else:
                subnets = [subnet]
            
            logger.info(f"Scanning subnets: {subnets}")
            
            # Common RTSP ports
            rtsp_ports = [554, 8554, 8080, 88]
            
            for subnet_cidr in subnets:
                network = ipaddress.ip_network(subnet_cidr, strict=False)
                
                # Limit scanning to reasonable subnet sizes
                if network.num_addresses > 256:
                    logger.warning(f"Subnet {subnet_cidr} too large, skipping")
                    continue
                
                # Scan each IP in the subnet
                tasks = []
                for ip in network.hosts():
                    for port in rtsp_ports:
                        tasks.append(self._check_rtsp_port(str(ip), port))
                
                # Run scans concurrently (in batches to avoid overwhelming network)
                batch_size = 50
                for i in range(0, len(tasks), batch_size):
                    batch = tasks[i:i + batch_size]
                    results = await asyncio.gather(*batch, return_exceptions=True)
                    
                    for result in results:
                        if result and not isinstance(result, Exception):
                            network_cameras.append(result)
                            logger.info(f"Found camera at {result['ip']}:{result['port']}")
        
        except Exception as e:
            logger.error(f"Error during network discovery: {e}")
        
        finally:
            self.scanning = False
        
        logger.info(f"Network camera discovery complete. Found {len(network_cameras)} cameras")
        return network_cameras
    
    def _get_local_subnets(self) -> List[str]:
        """Get all local subnets to scan"""
        subnets = []
        
        try:
            # Get all network interfaces
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                
                # Get IPv4 addresses
                if netifaces.AF_INET in addrs:
                    for addr_info in addrs[netifaces.AF_INET]:
                        ip = addr_info.get('addr')
                        netmask = addr_info.get('netmask')
                        
                        if ip and netmask and not ip.startswith('127.'):
                            # Calculate subnet
                            network = ipaddress.ip_network(f'{ip}/{netmask}', strict=False)
                            subnets.append(str(network))
        
        except Exception as e:
            logger.error(f"Error getting local subnets: {e}")
            # Fallback to common subnet
            subnets = ['192.168.1.0/24']
        
        return subnets
    
    async def _check_rtsp_port(self, ip: str, port: int, timeout: float = 1.0) -> Optional[Dict]:
        """
        Check if an IP:port combination responds to RTSP.
        
        Args:
            ip: IP address to check
            port: Port to check
            timeout: Connection timeout in seconds
        
        Returns:
            Camera info dict if RTSP service found, None otherwise
        """
        try:
            # Try to connect to the port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            
            if result == 0:
                # Port is open, try common RTSP URLs
                common_urls = [
                    f'rtsp://{ip}:{port}/stream',
                    f'rtsp://{ip}:{port}/stream1',
                    f'rtsp://{ip}:{port}/h264',
                    f'rtsp://{ip}:{port}/live',
                    f'rtsp://{ip}:{port}/cam/realmonitor?channel=1&subtype=0',
                ]
                
                # Test first URL to verify it's actually RTSP
                test_url = common_urls[0]
                if await self._test_rtsp_stream(test_url):
                    camera_info = {
                        'type': 'rtsp',
                        'ip': ip,
                        'port': port,
                        'name': f'IP Camera at {ip}',
                        'urls': common_urls,
                        'status': 'available',
                        'requires_auth': True,  # Most cameras require auth
                        'auto_config': {
                            'camera_id': f'rtsp_camera_{ip.replace(".", "_")}',
                            'camera_type': 'rtsp',
                            'source': test_url,
                            'enabled': True
                        },
                        'discovered_at': datetime.now().isoformat(),
                        'note': 'May require username/password. Try common credentials: admin/admin, admin/12345'
                    }
                    return camera_info
        
        except Exception as e:
            logger.debug(f"Error checking {ip}:{port}: {e}")
        
        return None
    
    async def _test_rtsp_stream(self, url: str, timeout: float = 2.0) -> bool:
        """
        Test if an RTSP URL is valid by attempting to open it with OpenCV.
        
        Args:
            url: RTSP URL to test
            timeout: Timeout in seconds
        
        Returns:
            True if stream is accessible, False otherwise
        """
        try:
            cap = cv2.VideoCapture(url)
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(timeout * 1000))
            
            is_opened = cap.isOpened()
            cap.release()
            
            return is_opened
        
        except Exception as e:
            logger.debug(f"Error testing RTSP stream {url}: {e}")
            return False
    
    async def test_camera_connection(self, camera_config: Dict) -> Dict:
        """
        Test if a camera configuration works.
        
        Args:
            camera_config: Camera configuration dict with 'type' and 'source'
        
        Returns:
            Test result with status and details
        """
        try:
            camera_type = camera_config.get('camera_type', camera_config.get('type'))
            source = camera_config.get('source')
            
            if not source:
                return {
                    'success': False,
                    'error': 'No source specified'
                }
            
            # Convert source to appropriate type
            if camera_type == 'usb':
                source = int(source)
            
            # Try to open the camera
            cap = cv2.VideoCapture(source)
            
            if not cap.isOpened():
                cap.release()
                return {
                    'success': False,
                    'error': 'Failed to open camera'
                }
            
            # Try to read a frame
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                return {
                    'success': False,
                    'error': 'Failed to read from camera'
                }
            
            return {
                'success': True,
                'message': 'Camera connection successful',
                'resolution': f'{frame.shape[1]}x{frame.shape[0]}'
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_discovery_status(self) -> Dict:
        """Get current discovery status"""
        return {
            'scanning': self.scanning,
            'cameras_found': len(self.discovered_cameras)
        }


# Global discovery service instance
discovery_service = CameraDiscovery()
