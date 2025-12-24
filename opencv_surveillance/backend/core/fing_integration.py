"""
Fing Agent Integration Module

Provides network discovery capabilities via Fing agent when available,
with fallback to simulated network scanning using ARP/nmap.

Features:
- Fing agent API integration (port 49090)
- Network device discovery
- Device classification
- Presence detection
- Speed testing
- Fallback simulation when Fing unavailable
"""

import asyncio
import json
import logging
import os
import platform
import re
import socket
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class DeviceType(str, Enum):
    """Device type classification"""
    ROUTER = "router"
    PHONE = "phone"
    LAPTOP = "laptop"
    DESKTOP = "desktop"
    TABLET = "tablet"
    TV = "tv"
    SPEAKER = "speaker"
    CAMERA = "camera"
    IOT = "iot"
    PRINTER = "printer"
    GAMING = "gaming"
    WEARABLE = "wearable"
    NAS = "nas"
    SERVER = "server"
    UNKNOWN = "unknown"


@dataclass
class NetworkDevice:
    """Represents a discovered network device"""
    mac_address: str
    ip_address: str
    hostname: Optional[str] = None
    vendor: Optional[str] = None
    device_type: DeviceType = DeviceType.UNKNOWN
    is_online: bool = True
    is_gateway: bool = False
    last_seen: datetime = field(default_factory=datetime.utcnow)
    first_seen: datetime = field(default_factory=datetime.utcnow)
    open_ports: List[int] = field(default_factory=list)
    custom_name: Optional[str] = None
    is_known: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        result = asdict(self)
        result['device_type'] = self.device_type.value
        result['last_seen'] = self.last_seen.isoformat()
        result['first_seen'] = self.first_seen.isoformat()
        return result


@dataclass
class SpeedTestResult:
    """Speed test result"""
    download_mbps: float
    upload_mbps: Optional[float] = None
    ping_ms: Optional[float] = None
    server: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


class FingIntegration:
    """
    Fing Agent Integration with Fallback Simulation

    Connects to local Fing agent when available, otherwise uses
    ARP/nmap-based network discovery.
    """

    # Fing agent default port
    FING_PORT = 49090
    FING_API_BASE = "/api/v1"

    # Common OUI (MAC vendor) prefixes
    VENDOR_OUI = {
        "00:1a:2b": "Apple",
        "00:03:93": "Apple",
        "f8:ff:c2": "Apple",
        "dc:a6:32": "Raspberry Pi",
        "b8:27:eb": "Raspberry Pi",
        "e4:5f:01": "Raspberry Pi",
        "28:cd:c1": "Raspberry Pi",
        "00:50:56": "VMware",
        "00:0c:29": "VMware",
        "08:00:27": "VirtualBox",
        "52:54:00": "QEMU/KVM",
        "00:15:5d": "Microsoft Hyper-V",
        "74:d4:35": "Amazon",
        "fc:65:de": "Amazon",
        "a0:02:dc": "Amazon",
        "88:71:b1": "Amazon",
        "34:d2:70": "Amazon",
        "3c:5a:b4": "Google",
        "f4:f5:d8": "Google",
        "54:60:09": "Google",
        "94:eb:2c": "Google",
        "cc:f4:11": "Google",
        "20:df:b9": "Google",
        "cc:50:e3": "Amazon Echo",
        "00:71:47": "Amazon Alexa",
        "38:2c:4a": "ASUSTek",
        "88:d7:f6": "ASUSTek",
        "60:45:cb": "ASUSTek",
        "d4:5d:64": "ASUSTek",
        "30:85:a9": "ASUSTek",
        "d8:bb:c1": "Samsung",
        "50:01:bb": "Samsung",
        "94:b8:6d": "Samsung",
        "f4:7b:09": "Samsung",
        "d0:17:c2": "Samsung",
        "70:3a:cb": "Samsung",
        "78:d2:94": "Samsung",
        "e4:7c:f9": "Samsung",
        "48:44:f7": "Samsung",
        "6c:2f:2c": "Samsung",
        "18:3a:2d": "Samsung",
        "ac:5f:3e": "Samsung",
        "b4:79:c8": "Samsung",
        "8c:77:12": "Samsung",
        "00:1e:c9": "Dell",
        "00:06:5b": "Dell",
        "b8:ac:6f": "Dell",
        "18:db:f2": "Dell",
        "00:1c:23": "Dell",
        "f0:1f:af": "Dell",
        "00:14:22": "Dell",
        "00:21:9b": "Dell",
        "3c:d9:2b": "HP",
        "00:1e:0b": "HP",
        "d8:9d:67": "HP",
        "10:1f:74": "HP",
        "00:1a:4b": "HP",
        "00:17:a4": "HP",
        "00:30:c1": "HP",
        "00:1c:c4": "HP",
    }

    # Device type inference based on vendor/hostname patterns
    DEVICE_TYPE_PATTERNS = {
        DeviceType.PHONE: ["iphone", "android", "galaxy", "pixel", "oneplus", "xiaomi", "huawei", "samsung-sm"],
        DeviceType.TABLET: ["ipad", "tablet", "galaxy-tab", "fire-hd", "surface"],
        DeviceType.LAPTOP: ["macbook", "laptop", "notebook", "thinkpad", "dell-xps", "hp-elitebook"],
        DeviceType.TV: ["tv", "roku", "firetv", "chromecast", "apple-tv", "smart-tv", "samsung-un", "lg-oled"],
        DeviceType.SPEAKER: ["echo", "homepod", "google-home", "sonos", "alexa", "nest-audio"],
        DeviceType.CAMERA: ["camera", "cam", "wyze", "ring", "nest-cam", "blink", "openeye", "hikvision", "dahua"],
        DeviceType.ROUTER: ["router", "gateway", "unifi", "netgear", "asus-rt", "linksys", "tp-link"],
        DeviceType.PRINTER: ["printer", "epson", "brother", "canon-mg", "hp-deskjet", "hp-officejet", "hp-laserjet"],
        DeviceType.GAMING: ["playstation", "ps4", "ps5", "xbox", "nintendo", "switch", "steam"],
        DeviceType.NAS: ["nas", "synology", "qnap", "drobo", "freenas", "truenas"],
        DeviceType.SERVER: ["server", "proxmox", "esxi", "unraid", "docker"],
        DeviceType.WEARABLE: ["watch", "fitbit", "garmin", "whoop", "oura"],
        DeviceType.IOT: ["nest", "hue", "wemo", "smart", "iot", "sensor", "thermostat", "lock"],
    }

    def __init__(self, fing_host: str = "localhost", fing_port: int = None):
        """
        Initialize Fing integration.

        Args:
            fing_host: Fing agent hostname (default: localhost)
            fing_port: Fing agent port (default: 49090)
        """
        self.fing_host = fing_host
        self.fing_port = fing_port or self.FING_PORT
        self.fing_available = False
        self.devices: Dict[str, NetworkDevice] = {}
        self._client: Optional[httpx.AsyncClient] = None
        self._scan_lock = asyncio.Lock()

    @property
    def fing_base_url(self) -> str:
        return f"http://{self.fing_host}:{self.fing_port}{self.FING_API_BASE}"

    async def initialize(self) -> bool:
        """
        Initialize and check Fing availability.

        Returns:
            True if Fing agent is available
        """
        self._client = httpx.AsyncClient(timeout=10.0)
        self.fing_available = await self._check_fing_available()

        if self.fing_available:
            logger.info("Fing agent connected successfully")
        else:
            logger.info("Fing agent not available, using fallback simulation")

        return self.fing_available

    async def _check_fing_available(self) -> bool:
        """Check if Fing agent is available"""
        try:
            response = await self._client.get(f"{self.fing_base_url}/status")
            return response.status_code == 200
        except Exception:
            return False

    async def discover_devices(self) -> List[NetworkDevice]:
        """
        Discover network devices.

        Uses Fing agent if available, otherwise falls back to ARP scanning.

        Returns:
            List of discovered devices
        """
        async with self._scan_lock:
            if self.fing_available:
                return await self._discover_via_fing()
            else:
                return await self._discover_via_simulation()

    async def _discover_via_fing(self) -> List[NetworkDevice]:
        """Discover devices via Fing agent API"""
        try:
            response = await self._client.get(f"{self.fing_base_url}/devices")
            if response.status_code != 200:
                logger.warning("Fing API error, falling back to simulation")
                return await self._discover_via_simulation()

            fing_devices = response.json()
            devices = []

            for fd in fing_devices.get("devices", []):
                device = NetworkDevice(
                    mac_address=fd.get("mac", "").lower(),
                    ip_address=fd.get("ip", ""),
                    hostname=fd.get("hostname"),
                    vendor=fd.get("vendor"),
                    device_type=self._classify_device(
                        fd.get("vendor", ""),
                        fd.get("hostname", ""),
                        fd.get("type", "")
                    ),
                    is_online=fd.get("state", "up") == "up",
                    is_gateway=fd.get("is_gateway", False),
                )
                devices.append(device)
                self.devices[device.mac_address] = device

            return devices

        except Exception as e:
            logger.error(f"Fing discovery error: {e}")
            return await self._discover_via_simulation()

    async def _discover_via_simulation(self) -> List[NetworkDevice]:
        """
        Fallback network discovery using ARP/nmap.

        Simulates Fing functionality when agent is unavailable.
        """
        devices = []

        try:
            # Determine scan method based on platform
            if platform.system() == "Linux":
                devices = await self._scan_arp_linux()
            elif platform.system() == "Darwin":
                devices = await self._scan_arp_macos()
            else:
                devices = await self._scan_arp_generic()

            # Enrich device data
            for device in devices:
                # Lookup vendor from MAC
                if not device.vendor:
                    device.vendor = self._lookup_vendor(device.mac_address)

                # Classify device type
                device.device_type = self._classify_device(
                    device.vendor or "",
                    device.hostname or "",
                    ""
                )

                # Store in cache
                if device.mac_address in self.devices:
                    # Update existing device
                    old_device = self.devices[device.mac_address]
                    device.first_seen = old_device.first_seen
                    device.custom_name = old_device.custom_name
                    device.is_known = old_device.is_known

                self.devices[device.mac_address] = device

            # Mark offline devices
            current_macs = {d.mac_address for d in devices}
            for mac, device in self.devices.items():
                if mac not in current_macs:
                    device.is_online = False

            return devices

        except Exception as e:
            logger.error(f"Simulation discovery error: {e}")
            return []

    async def _scan_arp_linux(self) -> List[NetworkDevice]:
        """ARP scan on Linux using arp-scan or fallback methods"""
        devices = []

        try:
            # Try arp-scan first (most accurate)
            result = await asyncio.create_subprocess_exec(
                "sudo", "arp-scan", "--localnet", "--quiet",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()

            if result.returncode == 0:
                for line in stdout.decode().split('\n'):
                    match = re.match(r'^(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:]{17})\s+(.*)$', line)
                    if match:
                        devices.append(NetworkDevice(
                            ip_address=match.group(1),
                            mac_address=match.group(2).lower(),
                            vendor=match.group(3) or None
                        ))
                return devices
        except Exception:
            pass

        # Fallback to nmap
        try:
            result = await asyncio.create_subprocess_exec(
                "nmap", "-sn", "-oG", "-", self._get_network_cidr(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()

            for line in stdout.decode().split('\n'):
                if "Host:" in line:
                    ip_match = re.search(r'Host:\s+(\d+\.\d+\.\d+\.\d+)', line)
                    if ip_match:
                        devices.append(NetworkDevice(
                            ip_address=ip_match.group(1),
                            mac_address=await self._get_mac_for_ip(ip_match.group(1)) or ""
                        ))
            return devices
        except Exception:
            pass

        # Final fallback: arp -a
        return await self._scan_arp_generic()

    async def _scan_arp_macos(self) -> List[NetworkDevice]:
        """ARP scan on macOS"""
        devices = []

        try:
            result = await asyncio.create_subprocess_exec(
                "arp", "-a",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()

            for line in stdout.decode().split('\n'):
                # Format: hostname (ip) at mac on interface
                match = re.match(r'^(\S+)\s+\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-fA-F:]{17})', line)
                if match:
                    hostname = match.group(1) if match.group(1) != "?" else None
                    devices.append(NetworkDevice(
                        ip_address=match.group(2),
                        mac_address=match.group(3).lower(),
                        hostname=hostname
                    ))

            return devices
        except Exception as e:
            logger.error(f"macOS ARP scan error: {e}")
            return []

    async def _scan_arp_generic(self) -> List[NetworkDevice]:
        """Generic ARP scan using arp command"""
        devices = []

        try:
            result = await asyncio.create_subprocess_exec(
                "arp", "-a",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()

            for line in stdout.decode().split('\n'):
                # Try different formats
                ip_match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)', line)
                mac_match = re.search(r'([0-9a-fA-F:]{17}|[0-9a-fA-F-]{17})', line)

                if ip_match and mac_match:
                    mac = mac_match.group(1).replace("-", ":").lower()
                    # Skip broadcast and multicast
                    if mac != "ff:ff:ff:ff:ff:ff" and not mac.startswith("01:00:5e"):
                        devices.append(NetworkDevice(
                            ip_address=ip_match.group(1),
                            mac_address=mac
                        ))

            return devices
        except Exception as e:
            logger.error(f"Generic ARP scan error: {e}")
            return []

    async def _get_mac_for_ip(self, ip: str) -> Optional[str]:
        """Get MAC address for an IP using ARP"""
        try:
            result = await asyncio.create_subprocess_exec(
                "arp", "-n", ip,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            mac_match = re.search(r'([0-9a-fA-F:]{17})', stdout.decode())
            return mac_match.group(1).lower() if mac_match else None
        except Exception:
            return None

    def _get_network_cidr(self) -> str:
        """Get local network CIDR"""
        try:
            # Get default gateway interface
            if platform.system() == "Linux":
                result = subprocess.run(
                    ["ip", "route", "get", "8.8.8.8"],
                    capture_output=True, text=True
                )
                match = re.search(r'src\s+(\d+\.\d+\.\d+)\.\d+', result.stdout)
                if match:
                    return f"{match.group(1)}.0/24"
            elif platform.system() == "Darwin":
                result = subprocess.run(
                    ["route", "-n", "get", "default"],
                    capture_output=True, text=True
                )
                for line in result.stdout.split('\n'):
                    if 'gateway:' in line:
                        gateway = line.split(':')[1].strip()
                        parts = gateway.rsplit('.', 1)
                        return f"{parts[0]}.0/24"
        except Exception:
            pass

        return "192.168.1.0/24"

    def _lookup_vendor(self, mac: str) -> Optional[str]:
        """Lookup vendor from MAC address OUI"""
        if not mac:
            return None

        # Get OUI (first 3 bytes)
        oui = mac[:8].lower()

        for prefix, vendor in self.VENDOR_OUI.items():
            if oui.startswith(prefix.lower()):
                return vendor

        return None

    def _classify_device(self, vendor: str, hostname: str, fing_type: str) -> DeviceType:
        """Classify device type based on available information"""
        search_string = f"{vendor} {hostname} {fing_type}".lower()

        for device_type, patterns in self.DEVICE_TYPE_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in search_string:
                    return device_type

        # Try to infer from vendor
        vendor_lower = vendor.lower() if vendor else ""
        if "apple" in vendor_lower:
            if "iphone" in search_string or "ipad" in search_string:
                return DeviceType.PHONE if "iphone" in search_string else DeviceType.TABLET
        elif "samsung" in vendor_lower:
            return DeviceType.PHONE  # Most likely
        elif "amazon" in vendor_lower:
            if "echo" in search_string or "alexa" in search_string:
                return DeviceType.SPEAKER
            return DeviceType.IOT
        elif "google" in vendor_lower:
            if "home" in search_string or "nest" in search_string:
                return DeviceType.SPEAKER
            return DeviceType.IOT

        return DeviceType.UNKNOWN

    async def run_speed_test(self) -> Optional[SpeedTestResult]:
        """
        Run internet speed test.

        Uses Fing agent if available, otherwise uses speedtest-cli or curl fallback.
        """
        if self.fing_available:
            try:
                response = await self._client.post(
                    f"{self.fing_base_url}/speedtest",
                    timeout=120.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return SpeedTestResult(
                        download_mbps=data.get("download", 0) / 1_000_000,
                        upload_mbps=data.get("upload", 0) / 1_000_000,
                        ping_ms=data.get("ping"),
                        server=data.get("server")
                    )
            except Exception as e:
                logger.warning(f"Fing speed test failed: {e}, using fallback")

        # Fallback to speedtest-cli
        try:
            result = await asyncio.create_subprocess_exec(
                "speedtest-cli", "--json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(
                result.communicate(),
                timeout=120.0
            )

            if result.returncode == 0:
                data = json.loads(stdout.decode())
                return SpeedTestResult(
                    download_mbps=data.get("download", 0) / 1_000_000,
                    upload_mbps=data.get("upload", 0) / 1_000_000,
                    ping_ms=data.get("ping"),
                    server=data.get("server", {}).get("sponsor")
                )
        except Exception as e:
            logger.warning(f"speedtest-cli failed: {e}, using curl fallback")

        # Curl-based download test
        try:
            import time
            start = time.time()
            result = await asyncio.create_subprocess_exec(
                "curl", "-o", "/dev/null", "-w", "%{speed_download}",
                "http://speedtest.tele2.net/1MB.zip",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(
                result.communicate(),
                timeout=60.0
            )

            bytes_per_sec = float(stdout.decode().strip())
            mbps = (bytes_per_sec * 8) / 1_000_000

            return SpeedTestResult(
                download_mbps=mbps,
                upload_mbps=None,
                ping_ms=None,
                server="speedtest.tele2.net"
            )
        except Exception as e:
            logger.error(f"All speed tests failed: {e}")
            return None

    async def check_connectivity(self, hosts: List[str] = None) -> bool:
        """
        Check internet connectivity.

        Args:
            hosts: List of hosts to ping (default: Google DNS, Cloudflare)

        Returns:
            True if any host is reachable
        """
        hosts = hosts or ["8.8.8.8", "1.1.1.1", "208.67.222.222"]

        for host in hosts:
            try:
                ping_cmd = ["ping", "-c", "1", "-W", "2", host]
                if platform.system() == "Windows":
                    ping_cmd = ["ping", "-n", "1", "-w", "2000", host]

                result = await asyncio.create_subprocess_exec(
                    *ping_cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await asyncio.wait_for(result.communicate(), timeout=5.0)

                if result.returncode == 0:
                    return True
            except Exception:
                continue

        return False

    async def get_device_ports(self, ip: str, ports: List[int] = None) -> List[int]:
        """
        Scan common ports on a device.

        Args:
            ip: Target IP address
            ports: List of ports to scan (default: common ports)

        Returns:
            List of open ports
        """
        ports = ports or [22, 80, 443, 8000, 8080, 8443, 554, 9000]
        open_ports = []

        async def check_port(port: int) -> bool:
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=1.0
                )
                writer.close()
                await writer.wait_closed()
                return True
            except Exception:
                return False

        # Check ports concurrently
        results = await asyncio.gather(
            *[check_port(p) for p in ports],
            return_exceptions=True
        )

        for port, is_open in zip(ports, results):
            if is_open is True:
                open_ports.append(port)

        return open_ports

    async def get_gateway_info(self) -> Optional[NetworkDevice]:
        """Get information about the network gateway"""
        devices = await self.discover_devices()
        for device in devices:
            if device.is_gateway:
                return device

        # Try to find gateway by IP pattern
        for device in devices:
            if device.ip_address.endswith(".1"):
                device.is_gateway = True
                return device

        return None

    def get_all_devices(self) -> List[NetworkDevice]:
        """Get all cached devices"""
        return list(self.devices.values())

    def get_online_devices(self) -> List[NetworkDevice]:
        """Get only online devices"""
        return [d for d in self.devices.values() if d.is_online]

    def get_device_by_mac(self, mac: str) -> Optional[NetworkDevice]:
        """Get device by MAC address"""
        return self.devices.get(mac.lower())

    def set_device_name(self, mac: str, name: str) -> bool:
        """Set custom name for a device"""
        device = self.devices.get(mac.lower())
        if device:
            device.custom_name = name
            device.is_known = True
            return True
        return False

    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()


# Singleton instance
_fing_instance: Optional[FingIntegration] = None


async def get_fing_integration() -> FingIntegration:
    """Get or create Fing integration singleton"""
    global _fing_instance

    if _fing_instance is None:
        _fing_instance = FingIntegration(
            fing_host=os.getenv("FING_HOST", "localhost"),
            fing_port=int(os.getenv("FING_PORT", "49090"))
        )
        await _fing_instance.initialize()

    return _fing_instance
