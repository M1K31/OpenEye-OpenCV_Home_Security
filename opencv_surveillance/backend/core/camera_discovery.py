# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Camera Discovery Service
Discovers RTSP/IP/ONVIF cameras on the network and USB cameras connected to the system.
Supports macOS, Linux, Windows, and containerized environments.
"""
import asyncio
import glob
import ipaddress
import json
import logging
import os
import platform
import re
import socket
import subprocess
import time
from datetime import datetime
import ipaddress
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import cv2

from backend.core.camera_security import (
    decrypt_camera_source,
    inject_rtsp_credentials,
    redact_url_credentials,
)

import psutil
from backend.core.capture_backend import open_local_device

logger = logging.getLogger(__name__)

# Virtual, loopback, tunnel, and container bridge interfaces that should not be
# swept during automatic LAN camera discovery.
IGNORED_INTERFACE_PREFIXES = (
    "lo",
    "utun",
    "tun",
    "tap",
    "bridge",
    "vmenet",
    "docker",
    "br-",
    "veth",
    "awdl",
    "llw",
    "anpi",
    "gif",
    "stf",
    "ap",
    "nan",
    "wg",
    "tailscale",
    "wsl",
    "vethernet",
    "virbr",
    "vmnet",
    " vboxnet",
)

# CGNAT / Tailscale range (100.64.0.0/10)
CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")


class CameraDiscovery:
    """
    Service for discovering cameras on the network and connected hardware.
    """

    # Highest camera index probed during USB discovery (0..N-1)
    MAX_CAMERA_INDEX = 11

    # How long to keep asking a device for its first frame once it has opened.
    FIRST_FRAME_TIMEOUT = float(os.environ.get("OPENEYE_FIRST_FRAME_TIMEOUT", "12"))
    FIRST_FRAME_TIMEOUT_SWEEP = float(
        os.environ.get("OPENEYE_FIRST_FRAME_TIMEOUT_SWEEP", "1.5")
    )
    FIRST_FRAME_POLL_INTERVAL = 0.25

    SLOW_START_THRESHOLD = 0.75
    DEVICE_LIST_TTL = float(os.environ.get("OPENEYE_DEVICE_LIST_TTL", "10"))

    # Network scan tuning
    NETWORK_SCAN_CONCURRENCY = int(
        os.environ.get("OPENEYE_NETWORK_SCAN_CONCURRENCY", "64")
    )
    ARP_HOST_TIMEOUT = float(os.environ.get("OPENEYE_ARP_PROBE_TIMEOUT", "1.5"))
    SWEEP_HOST_TIMEOUT = float(os.environ.get("OPENEYE_SWEEP_PROBE_TIMEOUT", "0.55"))

    def __init__(self):
        self.discovered_cameras: List[Dict] = []
        self.scanning = False
        self._authorization_primed = False
        self._macos_camera_cache = None
        self._macos_camera_cache_at = 0.0
        # uids seen to need a long warm-up, so later sweeps stay patient with them
        self._slow_start_uids = set()

    def _enumerate_platform_cameras(self) -> List[Dict]:
        """
        Ask the operating system which video devices are attached.

        This is deliberately independent of OpenCV. The OS will list a device
        even when it refuses to let this process open it, which is what lets
        discovery tell "nothing plugged in" apart from "access denied".

        Returns:
            List of {"name", "index"} dicts; empty if enumeration is
            unavailable on this platform.
        """
        system = platform.system()

        try:
            if system == "Darwin":
                output = subprocess.run(
                    ["system_profiler", "-json", "SPCameraDataType"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                ).stdout
                entries = json.loads(output).get("SPCameraDataType", [])
                return [
                    {"name": e.get("_name", f"Camera {i}"), "index": i}
                    for i, e in enumerate(entries)
                ]

            if system == "Linux":
                nodes = sorted(glob.glob("/dev/video*"))
                return [
                    {
                        "name": f"Video device {node}",
                        "index": int(node.rsplit("video", 1)[-1]),
                    }
                    for node in nodes
                    if node.rsplit("video", 1)[-1].isdigit()
                ]

            if system == "Windows":
                return self._list_windows_cameras()

        except Exception as e:
            logger.debug(f"Platform camera enumeration unavailable: {e}")

        return []

    def _list_windows_cameras(self) -> List[Dict]:
        """
        Names of the video devices Windows knows about.

        Windows returned nothing at all before this: the branches above covered
        macOS and Linux, so discovery reported "no cameras" on Windows whether
        one was attached or not — and could not tell that apart from a device it
        was refused access to, which is the whole reason this method exists.

        Get-PnpDevice rather than a Python dependency. It is built into Windows
        8 and later, needs nothing installed, and matches how the other two
        branches work — a subprocess asking the operating system. The
        alternative, pygrabber, would add a package for one call.

        A CAVEAT that matters, and which the macOS branch shares: PnP
        enumeration order is not guaranteed to match the DirectShow index order
        OpenCV uses. The names here are reliable; pairing name to index is a
        best guess. Probing is the authority — discover_usb_cameras opens each
        index and reports what actually answered — so a wrong pairing shows up
        as a name against the wrong camera, not as a missing or phantom device.

        The `Image` class is queried alongside `Camera` because some UVC webcams
        still enumerate there on Windows 10. Scanners live in `Image` too, so a
        flatbed may appear in this list; it will simply fail to open when probed,
        which costs one attempt and no correctness.
        """
        script = (
            "$ErrorActionPreference='SilentlyContinue';"
            "Get-PnpDevice -Class Camera,Image -PresentOnly"
            " | Where-Object { $_.Status -eq 'OK' }"
            " | Select-Object -ExpandProperty FriendlyName"
        )
        completed = subprocess.run(
            # powershell.exe, not pwsh: 5.1 ships with Windows, PowerShell 7 is
            # an optional install. -NoProfile keeps a user's profile out of it
            # and is faster; -NonInteractive means it can never sit waiting for
            # input inside a background service.
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=20,
        )

        names = [line.strip() for line in completed.stdout.splitlines() if line.strip()]

        if not names:
            logger.info(
                "Windows reports no video devices. If a camera is attached, "
                "check Settings > Privacy & security > Camera."
            )

        return [{"name": name, "index": i} for i, name in enumerate(names)]

    def _prime_macos_authorization(self) -> None:
        """
        Give macOS one chance to raise the camera permission dialog.
        """
        self._authorization_primed = True

        if platform.system() != "Darwin":
            return

        try:
            cap = open_local_device(0)
            authorized = cap.isOpened()
            cap.release()
            if not authorized:
                logger.debug(
                    "macOS did not grant camera access on the priming probe"
                )
        except Exception as e:
            logger.debug(f"Camera authorization priming failed: {e}")

    def _probe_index(self, index: int, patient: bool = False) -> Optional[Dict]:
        """
        Blocking probe of a single camera index. Runs in a worker thread.
        """
        cap = None
        identity = self._describe_device(index)
        label = identity.get("name") or f"index {index}"
        uid = identity.get("uid")

        if uid and uid in self._slow_start_uids:
            patient = True
        budget = (
            self.FIRST_FRAME_TIMEOUT
            if patient
            else self.FIRST_FRAME_TIMEOUT_SWEEP
        )
        try:
            cap = open_local_device(index)
            if not cap.isOpened():
                logger.info(
                    "Camera probe: index %s (%s) is listed by the OS but "
                    "VideoCapture could not open it",
                    index,
                    label,
                )
                return None
            logger.info("Camera probe: index %s (%s) opened", index, label)

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))

            deadline = time.monotonic() + budget
            first_frame_after = None
            started = time.monotonic()
            while True:
                ret, frame = cap.read()
                if ret and frame is not None:
                    first_frame_after = time.monotonic() - started
                    break
                if time.monotonic() >= deadline:
                    logger.info(
                        "Camera probe: index %s (%s) opened but produced no frame "
                        "within %.1fs%s",
                        index,
                        label,
                        budget,
                        ""
                        if patient
                        else " (sweep budget; a slow device is "
                        "retried patiently when added)",
                    )
                    return None
                time.sleep(self.FIRST_FRAME_POLL_INTERVAL)

            if uid and first_frame_after >= self.SLOW_START_THRESHOLD:
                self._slow_start_uids.add(uid)

            if frame is not None and getattr(frame, "shape", None):
                height, width = frame.shape[0], frame.shape[1]

            return {
                "type": "usb",
                "index": index,
                "name": identity.get("name") or f"USB Camera {index}",
                "device_uid": identity.get("uid"),
                "device_path": self._get_device_path(index),
                "resolution": f"{width}x{height}",
                "fps": fps if fps > 0 else 30,
                "status": "available",
                "warmup_seconds": round(first_frame_after, 2),
                "slow_start": first_frame_after >= self.SLOW_START_THRESHOLD,
                "auto_config": {
                    "camera_id": f"usb_camera_{index}",
                    "camera_type": "usb",
                    "source": str(index),
                    "device_uid": identity.get("uid"),
                    "device_name": identity.get("name"),
                    "enabled": True,
                },
                "discovered_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.debug(f"No camera at index {index}: {e}")
            return None
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    async def discover_usb_cameras_detailed(self) -> Dict:
        """
        Discover USB and built-in cameras, reporting why a device was missed.
        """
        logger.info("Starting USB camera discovery...")

        loop = asyncio.get_event_loop()
        platform_cameras = await loop.run_in_executor(
            None, self._enumerate_platform_cameras
        )
        if platform_cameras:
            logger.info(
                "OS reports %d attached camera(s): %s",
                len(platform_cameras),
                ", ".join(c["name"] for c in platform_cameras),
            )

        if platform_cameras and not self._authorization_primed:
            self._prime_macos_authorization()

        if platform_cameras:
            indices = [c["index"] for c in platform_cameras]
        else:
            indices = list(range(self.MAX_CAMERA_INDEX))

        results = await asyncio.gather(
            *(loop.run_in_executor(None, self._probe_index, i) for i in indices)
        )
        usb_cameras = [cam for cam in results if cam]

        warnings: List[str] = []
        permission_denied = bool(platform_cameras) and not usb_cameras

        if permission_denied:
            names = ", ".join(c["name"] for c in platform_cameras)
            warnings.append(
                f"The system reports {len(platform_cameras)} attached camera(s) "
                f"({names}) but none could be opened. This is almost always an "
                f"operating-system camera permission denial, not a hardware "
                f"fault. {self._permission_hint()}"
            )
            logger.warning(warnings[-1])

        for cam in usb_cameras:
            logger.info(
                f"Found USB camera at index {cam['index']}: "
                f"{cam['resolution']} @ {cam['fps']}fps"
            )

        logger.info(
            f"USB camera discovery complete. Found {len(usb_cameras)} cameras"
        )

        return {
            "cameras": usb_cameras,
            "warnings": warnings,
            "permission_denied": permission_denied,
            "platform_cameras": platform_cameras,
        }

    async def discover_usb_cameras(self) -> List[Dict]:
        """Backwards-compatible wrapper returning only the camera list."""
        result = await self.discover_usb_cameras_detailed()
        return result["cameras"]

    def _permission_hint(self) -> str:
        """Platform-specific guidance for granting camera access."""
        system = platform.system()
        if system == "Darwin":
            return (
                "On macOS, grant camera access in System Settings > Privacy & "
                "Security > Camera. Note that a background service started by "
                "launchd cannot display a permission prompt and is denied "
                "silently; run the server from a terminal once to trigger the "
                "prompt, and grant the permission to that terminal application."
            )
        if system == "Linux":
            return (
                "On Linux, ensure the service account is a member of the "
                "'video' group and that /dev/video* is readable."
            )
        if system == "Windows":
            return (
                "On Windows, allow camera access in Settings > Privacy & "
                "security > Camera, and make sure 'Let desktop apps access "
                "your camera' is on — that second switch is separate and is "
                "what blocks a Python process even when the first is enabled."
            )
        return "Check the operating system's camera privacy settings."

    def _list_macos_cameras(self) -> List[Dict]:
        """
        Names and unique IDs of every camera macOS knows about, in system order.
        """
        if (
            self._macos_camera_cache is not None
            and (time.monotonic() - self._macos_camera_cache_at)
            < self.DEVICE_LIST_TTL
        ):
            return self._macos_camera_cache

        cameras: List[Dict] = []
        if platform.system() == "Darwin":
            try:
                out = subprocess.run(
                    ["system_profiler", "SPCameraDataType", "-json"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                ).stdout
                for entry in json.loads(out).get("SPCameraDataType", []):
                    cameras.append(
                        {
                            "name": entry.get("_name"),
                            "uid": entry.get("spcamera_unique-id"),
                            "model": entry.get("spcamera_model-id"),
                        }
                    )
            except Exception as e:
                logger.debug("Could not enumerate macOS cameras: %s", e)

        self._macos_camera_cache = cameras
        self._macos_camera_cache_at = time.monotonic()
        return cameras

    def _describe_device(self, index: int) -> Dict:
        """Best-effort real name and unique ID for an OpenCV camera index."""
        cameras = self._list_macos_cameras()
        if 0 <= index < len(cameras):
            return cameras[index]
        return {"name": None, "uid": None, "model": None}

    def _get_device_path(self, index: int) -> str:
        """Get the device path for a camera index (platform-specific)"""
        system = platform.system()
        if system == "Linux":
            return f"/dev/video{index}"
        elif system == "Darwin":  # macOS
            return f"AVFoundation:{index}"
        elif system == "Windows":
            return f"DirectShow:{index}"
        else:
            return f"index:{index}"

    async def discover_network_cameras(
        self, subnet: Optional[str] = None, timeout: int = 60
    ) -> List[Dict]:
        """
        Discover RTSP/IP/ONVIF cameras on the local network.

        Uses a two-phase architecture:
          1. ARP/neighbor cache priority probe (finds active cameras in <1s).
          2. Semaphore-bounded subnet sweep for any silent/uncached hosts.

        Updates `self.discovered_cameras` incrementally as devices respond so
        `/api/cameras/discover/status` always reflects live progress.
        """
        logger.info(
            f"Starting network camera discovery... (timeout: {timeout}s)"
        )
        self.scanning = True
        network_cameras: List[Dict] = []
        self.discovered_cameras = network_cameras
        seen_endpoints: Set[Tuple[str, int]] = set()
        own_ips = self._get_own_ips()

        async def _record_result(result: Optional[Dict]) -> None:
            if not result or isinstance(result, Exception):
                return
            key = (result["ip"], int(result["port"]))
            if key in seen_endpoints:
                return
            seen_endpoints.add(key)
            network_cameras.append(result)
            logger.info(
                "Found %s at %s:%s",
                result.get("name", "camera"),
                result["ip"],
                result["port"],
            )

        async def _do_scan():
            try:
                subnets = [subnet] if subnet else self._get_local_subnets()
                logger.info(f"Scanning subnets: {subnets}")

                rtsp_ports = [554, 8554, 8080, 88]
                semaphore = asyncio.Semaphore(self.NETWORK_SCAN_CONCURRENCY)

                async def _bounded_check(
                    ip_str: str, port: int, probe_timeout: float
                ) -> Optional[Dict]:
                    if not self.scanning:
                        return None
                    async with semaphore:
                        if not self.scanning:
                            return None
                        res = await self._check_rtsp_port(
                            ip_str, port, timeout=probe_timeout
                        )
                        if res:
                            await _record_result(res)
                        return res

                for subnet_cidr in subnets:
                    if not self.scanning:
                        break
                    network = ipaddress.ip_network(subnet_cidr, strict=False)

                    # If a /16 or /20 was passed directly, narrow to a /24
                    if network.num_addresses > 256:
                        logger.warning(
                            f"Subnet {subnet_cidr} too large, skipping"
                        )
                        continue

                    all_hosts = [
                        str(ip)
                        for ip in network.hosts()
                        if str(ip) not in own_ips
                    ]

                    # Phase 1: Probe ARP-known active hosts first (e.g. 192.168.50.135)
                    arp_ips = await self._get_arp_priority_ips(network, own_ips)
                    if arp_ips:
                        logger.info(
                            "Phase 1: Probing %d ARP-active host(s) in %s first",
                            len(arp_ips),
                            subnet_cidr,
                        )
                        phase1_coros = [
                            _bounded_check(ip_str, port, self.ARP_HOST_TIMEOUT)
                            for ip_str in arp_ips
                            for port in rtsp_ports
                        ]
                        await asyncio.gather(
                            *phase1_coros, return_exceptions=True
                        )

                    # Phase 2: Sweep remaining hosts in the subnet
                    arp_set = set(arp_ips)
                    remaining_hosts = [
                        ip_str for ip_str in all_hosts if ip_str not in arp_set
                    ]
                    if remaining_hosts and self.scanning:
                        phase2_coros = [
                            _bounded_check(
                                ip_str, port, self.SWEEP_HOST_TIMEOUT
                            )
                            for ip_str in remaining_hosts
                            for port in rtsp_ports
                        ]
                        await asyncio.gather(
                            *phase2_coros, return_exceptions=True
                        )

            except Exception as e:
                logger.error(f"Error during network discovery: {e}")

        try:
            await asyncio.wait_for(_do_scan(), timeout=timeout)
            logger.info(
                f"Network camera discovery complete. Found {len(network_cameras)} cameras"
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Network scan timed out after {timeout}s. "
                f"Returning {len(network_cameras)} cameras found so far"
            )
        except Exception as e:
            logger.error(f"Unexpected error during network discovery: {e}")
        finally:
            self.scanning = False

        return network_cameras

    def _get_own_ips(self) -> Set[str]:
        """Return set of IPv4 addresses assigned to this host (via psutil)."""
        ips: Set[str] = {"127.0.0.1"}
        try:
            for _iface, addresses in psutil.net_if_addrs().items():
                for addr in addresses:
                    if addr.family == socket.AF_INET and addr.address:
                        ips.add(addr.address)
        except Exception:
            pass
        return ips

    def _get_primary_lan_ip(self) -> Optional[str]:
        """
        Determine the primary outbound LAN IPv4 address via a non-transmitting
        UDP socket connect across macOS, Linux, and Windows.
        """
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass
        finally:
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
        return None

    def _get_local_subnets(self) -> List[str]:
        """
        Get deduplicated physical/LAN subnets to scan across macOS, Linux, and Windows.

        Uses psutil rather than netifaces. netifaces was unmaintained from 2021
        and published no Windows wheel past CPython 3.8, so on 3.12 pip had to
        build it with MSVC. psutil returns the same interface addresses and
        netmasks, is already a required dependency, and ships wheels for every
        platform this project supports.

        Places the primary outbound LAN subnet first and excludes virtual bridges,
        VPN tunnels, link-local, and CGNAT ranges.
        """
        subnets: List[str] = []
        seen: Set[str] = set()

        def _add_subnet(ip_str: str, netmask_str: str) -> None:
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                if (
                    ip_obj.is_loopback
                    or ip_obj.is_link_local
                    or ip_obj in CGNAT_NETWORK
                ):
                    return
                network = ipaddress.ip_network(
                    f"{ip_str}/{netmask_str}", strict=False
                )
                if network.num_addresses <= 2:
                    return
                if network.num_addresses > 256:
                    network = ipaddress.ip_network(f"{ip_str}/24", strict=False)
                cidr = str(network)
                if cidr not in seen:
                    seen.add(cidr)
                    subnets.append(cidr)
            except Exception:
                pass

        primary_ip = self._get_primary_lan_ip()
        if primary_ip:
            _add_subnet(primary_ip, "255.255.255.0")

        try:
            for interface, addresses in psutil.net_if_addrs().items():
                if interface.lower().startswith(IGNORED_INTERFACE_PREFIXES):
                    continue
                for addr in addresses:
                    if addr.family != socket.AF_INET:
                        continue
                    ip, netmask = addr.address, addr.netmask
                    if ip and netmask and not ip.startswith("127."):
                        _add_subnet(ip, netmask)
        except Exception as e:
            logger.error("Could not enumerate network interfaces: %s", e)

        if not subnets:
            subnets = ["192.168.1.0/24"]

        return subnets

    async def _get_arp_priority_ips(
        self, network: ipaddress.IPv4Network, own_ips: Set[str]
    ) -> List[str]:
        """
        Extract reachable IPv4 hosts in `network` from the OS ARP/neighbor cache.
        Supports Linux (/proc/net/arp + ip neigh), macOS (arp -a), and Windows (arp -a).
        """
        found: List[str] = []
        seen: Set[str] = set()

        def _consider(ip_candidate: str) -> None:
            if ip_candidate in seen or ip_candidate in own_ips:
                return
            try:
                ip_obj = ipaddress.ip_address(ip_candidate)
                if ip_obj in network and ip_obj != network.broadcast_address and ip_obj != network.network_address:
                    seen.add(ip_candidate)
                    found.append(ip_candidate)
            except ValueError:
                pass

        # Fast path on Linux: /proc/net/arp
        proc_arp = Path("/proc/net/arp")
        if proc_arp.is_file():
            try:
                for line in proc_arp.read_text(errors="ignore").splitlines()[1:]:
                    parts = line.split()
                    # Flags 0x0 means incomplete; 0x2 means complete
                    if len(parts) >= 4 and parts[2] != "0x0" and parts[3] != "00:00:00:00:00:00":
                        _consider(parts[0])
            except Exception:
                pass

        # Cross-platform `arp -a` (macOS, Windows, Linux fallback)
        try:
            proc = await asyncio.create_subprocess_exec(
                "arp",
                "-a",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=2.5)
            for line in stdout.decode("utf-8", "replace").splitlines():
                lower = line.lower()
                if "incomplete" in lower or "ff:ff:ff:ff:ff:ff" in lower or "ff-ff-ff-ff-ff-ff" in lower:
                    continue
                # Match macOS/Linux `(192.168.50.135) at 18:69:45:a6:ea:c9` or
                # Windows `192.168.50.135   18-69-45-a6-ea-c9   dynamic`
                ip_match = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", line)
                mac_match = re.search(
                    r"\b([0-9a-fA-F]{1,2}(?:[:-][0-9a-fA-F]{1,2}){5})\b", line
                )
                if ip_match and mac_match:
                    _consider(ip_match.group(1))
        except Exception as e:
            logger.debug(f"ARP table lookup skipped: {e}")

        return found

    async def _check_tcp_port_open(
        self, ip: str, port: int, timeout: float = 0.8
    ) -> bool:
        """Quick check whether a TCP port is open on `ip`."""
        writer = None
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port), timeout=timeout
            )
            return True
        except Exception:
            return False
        finally:
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    def _identify_rtsp_vendor(
        self, ip: str, port: int, response_text: str, onvif_2020_open: bool = False
    ) -> Dict:
        """
        Identify camera manufacturer, model family, and optimal stream URLs
        from RTSP headers (`WWW-Authenticate` realm, `Server`) and open ports.
        """
        realm_match = re.search(
            r'realm="([^"]+)"', response_text, re.IGNORECASE
        )
        server_match = re.search(
            r"^Server:\s*(.+)$", response_text, re.IGNORECASE | re.MULTILINE
        )
        realm = realm_match.group(1).strip() if realm_match else ""
        server = server_match.group(1).strip() if server_match else ""
        fingerprint = f"{realm} {server}".lower()

        if "tp-link" in fingerprint or "tapo" in fingerprint or onvif_2020_open:
            manufacturer = "TP-Link Tapo"
            name = f"TP-Link Tapo Camera ({ip})"
            urls = [
                f"rtsp://{ip}:{port}/stream1",
                f"rtsp://{ip}:{port}/stream2",
                f"rtsp://{ip}:{port}/live",
            ]
            auth_hint = (
                "Enter the Camera Account username & password created in the "
                "Tapo app (Camera Settings → Advanced Settings → Camera Account)."
            )
        elif any(k in fingerprint for k in ("hikvision", "dvrdvs", "app-webs", "hik")):
            manufacturer = "Hikvision"
            name = f"Hikvision Camera ({ip})"
            urls = [
                f"rtsp://{ip}:{port}/Streaming/Channels/101",
                f"rtsp://{ip}:{port}/Streaming/Channels/102",
                f"rtsp://{ip}:{port}/h264/ch1/main/av_stream",
                f"rtsp://{ip}:{port}/stream1",
            ]
            auth_hint = "Enter your Hikvision camera admin username and password."
        elif any(k in fingerprint for k in ("dahua", "amcrest", "lorex")):
            manufacturer = "Dahua / Amcrest"
            name = f"Dahua/Amcrest Camera ({ip})"
            urls = [
                f"rtsp://{ip}:{port}/cam/realmonitor?channel=1&subtype=0",
                f"rtsp://{ip}:{port}/cam/realmonitor?channel=1&subtype=1",
                f"rtsp://{ip}:{port}/live",
                f"rtsp://{ip}:{port}/stream1",
            ]
            auth_hint = "Enter your Dahua/Amcrest camera username and password."
        elif "reolink" in fingerprint:
            manufacturer = "Reolink"
            name = f"Reolink Camera ({ip})"
            urls = [
                f"rtsp://{ip}:{port}/h264Preview_01_main",
                f"rtsp://{ip}:{port}/h264Preview_01_sub",
                f"rtsp://{ip}:{port}/Preview_01_main",
                f"rtsp://{ip}:{port}/stream1",
            ]
            auth_hint = "Enter your Reolink camera username and password."
        elif "axis" in fingerprint:
            manufacturer = "Axis"
            name = f"Axis Camera ({ip})"
            urls = [
                f"rtsp://{ip}:{port}/axis-media/media.amp",
                f"rtsp://{ip}:{port}/mpeg4/media.amp",
                f"rtsp://{ip}:{port}/stream1",
            ]
            auth_hint = "Enter your Axis camera ONVIF/RTSP credentials."
        elif "unifi" in fingerprint or "ubnt" in fingerprint or "ubiquiti" in fingerprint:
            manufacturer = "Ubiquiti UniFi"
            name = f"UniFi Camera ({ip})"
            urls = [
                f"rtsp://{ip}:{port}/s0",
                f"rtsp://{ip}:{port}/s1",
                f"rtsp://{ip}:{port}/live",
            ]
            auth_hint = "Use the RTSP stream URL enabled in UniFi Protect."
        elif "foscam" in fingerprint:
            manufacturer = "Foscam"
            name = f"Foscam Camera ({ip})"
            urls = [
                f"rtsp://{ip}:{port}/videoMain",
                f"rtsp://{ip}:{port}/videoSub",
                f"rtsp://{ip}:{port}/stream1",
            ]
            auth_hint = "Enter your Foscam camera username and password."
        else:
            manufacturer = realm or server or "Generic RTSP / ONVIF"
            name = f"IP Camera at {ip}"
            urls = [
                f"rtsp://{ip}:{port}/stream1",
                f"rtsp://{ip}:{port}/stream2",
                f"rtsp://{ip}:{port}/stream",
                f"rtsp://{ip}:{port}/h264",
                f"rtsp://{ip}:{port}/live",
                f"rtsp://{ip}:{port}/Streaming/Channels/101",
                f"rtsp://{ip}:{port}/cam/realmonitor?channel=1&subtype=0",
                f"rtsp://{ip}:{port}/h264Preview_01_main",
            ]
            auth_hint = (
                "Enter the camera's RTSP/ONVIF username and password if "
                "authentication is required."
            )

        return {
            "manufacturer": manufacturer,
            "name": name,
            "urls": urls,
            "realm": realm or None,
            "server": server or None,
            "auth_hint": auth_hint,
        }

    async def _check_rtsp_port(
        self, ip: str, port: int, timeout: float = 1.0
    ) -> Optional[Dict]:
        """
        Check if an IP:port combination responds to RTSP and fingerprint its vendor.

        Args:
            ip: IP address to check
            port: Port to check
            timeout: Connection timeout in seconds

        Returns:
            Camera info dict if RTSP service found, None otherwise
        """
        try:
            response = await self._rtsp_options_probe(ip, port, timeout)

            # An open port proves nothing: 88 and 8080 are overwhelmingly HTTP
            # admin panels. Only a device that answers the RTSP handshake is a
            # camera, so anything else is discarded rather than guessed at.
            if not response or not response.startswith(b"RTSP/"):
                if response:
                    logger.debug(
                        f"{ip}:{port} is open but does not speak RTSP; ignoring"
                    )
                return None

            response_text = response.decode("ascii", "replace")
            status_line = response_text.split("\r\n", 1)[0]
            requires_auth = (
                b" 401 " in response
                or b" 403 " in response
                or b"WWW-Authenticate:" in response
            )

            # Check if Tapo/ONVIF port 2020 is open when realm wasn't already explicit
            onvif_2020_open = False
            if "tp-link" not in response_text.lower() and port == 554:
                onvif_2020_open = await self._check_tcp_port_open(
                    ip, 2020, timeout=0.4
                )

            vendor_info = self._identify_rtsp_vendor(
                ip, port, response_text, onvif_2020_open=onvif_2020_open
            )
            common_urls = vendor_info["urls"]

            note = (
                f"RTSP server confirmed ({vendor_info['manufacturer']}). "
                f"{vendor_info['auth_hint']}"
                if requires_auth
                else "RTSP server confirmed. Select a stream path and enter credentials if required."
            )

            return {
                "type": "rtsp",
                "ip": ip,
                "port": port,
                "onvif_port": 2020 if (onvif_2020_open or vendor_info["manufacturer"] == "TP-Link Tapo") else None,
                "manufacturer": vendor_info["manufacturer"],
                "realm": vendor_info["realm"],
                "name": vendor_info["name"],
                "urls": common_urls,
                "status": "available",
                "requires_auth": requires_auth,
                "auth_hint": vendor_info["auth_hint"],
                "rtsp_response": status_line,
                "auto_config": {
                    "camera_id": f'rtsp_camera_{ip.replace(".", "_")}',
                    "camera_type": "rtsp",
                    "source": common_urls[0],
                    "enabled": True,
                },
                "discovered_at": datetime.now().isoformat(),
                "note": note,
            }

        except Exception as e:
            logger.debug(f"Error checking {ip}:{port}: {e}")

        return None

    async def _curl_rtsp_fallback(
        self, ip: str, port: int, timeout: float = 2.0
    ) -> Optional[bytes]:
        """
        macOS Local Network TCC / ARP fallback using Apple's signed /usr/bin/curl.

        When OpenEye runs under launchd on macOS Sequoia without an .app bundle,
        third-party Python binaries can receive EHOSTUNREACH (Errno 65) on LAN
        sockets while system binaries like /usr/bin/curl are permitted.
        """
        if platform.system() != "Darwin":
            return None
        try:
            max_time = str(max(1, int(round(timeout))))
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/curl",
                "-is",
                "--max-time",
                max_time,
                f"rtsp://{ip}:{port}/",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=timeout + 1.0
            )
            if not stdout or not stdout.startswith(b"RTSP/"):
                return None

            if b" 401 " in stdout or b" 403 " in stdout:
                return stdout

            # Follow up with DESCRIBE via curl to capture 401 + WWW-Authenticate realm
            proc_desc = await asyncio.create_subprocess_exec(
                "/usr/bin/curl",
                "-is",
                "--max-time",
                max_time,
                "-X",
                "DESCRIBE",
                f"rtsp://{ip}:{port}/stream1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            desc_out, _ = await asyncio.wait_for(
                proc_desc.communicate(), timeout=timeout + 1.0
            )
            if desc_out:
                return stdout + b"\r\n" + desc_out
            return stdout
        except Exception:
            return None

    async def _rtsp_options_probe(
        self, ip: str, port: int, timeout: float = 2.0
    ) -> Optional[bytes]:
        """
        Send an RTSP OPTIONS request (followed by DESCRIBE if OPTIONS returns 200 OK)
        and return the raw reply bytes.

        Many spec-compliant cameras (such as TP-Link Tapo) answer `OPTIONS` with
        `RTSP/1.0 200 OK` without requiring credentials, and only challenge with
        `401 Unauthorized` + `WWW-Authenticate: Basic realm="TP-LINK IP-Camera"`
        when a client sends `DESCRIBE`. Combining both responses accurately detects
        both authentication requirements and the device's vendor realm.
        """
        import errno

        writer = None
        try:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port), timeout=timeout
                )
            except OSError as first_err:
                # On macOS, a cold ARP entry or multi-NIC subnet can raise
                # EHOSTUNREACH (Errno 65) on the first SYN while ARP resolves.
                if getattr(first_err, "errno", None) in (
                    errno.EHOSTUNREACH,
                    errno.ENETUNREACH,
                    65,
                ):
                    await asyncio.sleep(0.15)
                    try:
                        reader, writer = await asyncio.wait_for(
                            asyncio.open_connection(ip, port), timeout=timeout
                        )
                    except OSError:
                        return await self._curl_rtsp_fallback(ip, port, timeout)
                else:
                    return None

            request = (
                f"OPTIONS rtsp://{ip}:{port} RTSP/1.0\r\n"
                f"CSeq: 1\r\n"
                f"User-Agent: OpenEye-Discovery\r\n"
                f"\r\n"
            ).encode("ascii")
            writer.write(request)
            await writer.drain()
            opt_resp = await asyncio.wait_for(
                reader.read(1024), timeout=max(timeout, 1.0)
            )
            if not opt_resp or not opt_resp.startswith(b"RTSP/"):
                return opt_resp

            # If OPTIONS already revealed 401/403, no second round-trip is needed
            if b" 401 " in opt_resp or b" 403 " in opt_resp:
                return opt_resp

            # Send DESCRIBE to detect stream-level authentication & vendor realm
            desc_req = (
                f"DESCRIBE rtsp://{ip}:{port}/stream1 RTSP/1.0\r\n"
                f"CSeq: 2\r\n"
                f"Accept: application/sdp\r\n"
                f"User-Agent: OpenEye-Discovery\r\n"
                f"\r\n"
            ).encode("ascii")
            try:
                writer.write(desc_req)
                await writer.drain()
                desc_resp = await asyncio.wait_for(
                    reader.read(1024), timeout=max(timeout, 1.0)
                )
                if desc_resp:
                    return opt_resp + b"\r\n" + desc_resp
            except Exception:
                pass

            return opt_resp
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return None
        finally:
            if writer is not None:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    async def _test_rtsp_stream(self, url: str, timeout: float = 2.0) -> bool:
        """
        Test if an RTSP URL is valid by attempting to open it with OpenCV.
        Runs in a thread pool to avoid blocking the event loop.
        """
        def _blocking_test():
            try:
                os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|stimeout;5000000")
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(timeout * 1000))
                is_opened = cap.isOpened()
                cap.release()
                return is_opened
            except Exception as e:
                logger.debug(
                    f"Error testing RTSP stream {redact_url_credentials(url)}: {e}"
                )
                return False

        try:
            loop = asyncio.get_event_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, _blocking_test),
                timeout=timeout + 1.0,
            )
        except asyncio.TimeoutError:
            logger.debug(
                f"RTSP stream test timed out: {redact_url_credentials(url)}"
            )
            return False
        except Exception as e:
            logger.debug(
                f"Error testing RTSP stream {redact_url_credentials(url)}: {e}"
            )
            return False

    async def test_camera_connection(self, camera_config: Dict) -> Dict:
        """
        Test if a camera configuration works.

        Runs blocking OpenCV capture operations in a thread pool executor so the
        FastAPI event loop remains responsive during RTSP handshakes.
        """
        try:
            camera_type = camera_config.get(
                "camera_type", camera_config.get("type")
            )
            source = camera_config.get("source")
            username = camera_config.get("username")
            password = camera_config.get("password")

            if not source:
                return {"success": False, "error": "No source specified"}

            if camera_type == "usb":
                resolved_source = int(source)
            else:
                resolved_source = decrypt_camera_source(str(source))
                if username or password:
                    resolved_source = inject_rtsp_credentials(
                        resolved_source, username=username, password=password
                    )

            def _blocking_probe() -> Dict:
                cap = None
                try:
                    if camera_type == "usb":
                        cap = cv2.VideoCapture(resolved_source)
                    else:
                        os.environ.setdefault(
                            "OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp"
                        )
                        cap = cv2.VideoCapture(resolved_source, cv2.CAP_FFMPEG)

                    if not cap or not cap.isOpened():
                        return {
                            "success": False,
                            "error": (
                                "Failed to open camera stream. Verify the stream URL "
                                "and camera username/password."
                                if camera_type != "usb"
                                else "Failed to open camera"
                            ),
                        }

                    deadline = time.monotonic() + self.FIRST_FRAME_TIMEOUT
                    started = time.monotonic()
                    frame = None
                    while True:
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            break
                        if time.monotonic() >= deadline:
                            return {
                                "success": False,
                                "error": (
                                    f"Opened the camera but received no frame within "
                                    f"{self.FIRST_FRAME_TIMEOUT:.0f}s"
                                ),
                            }
                        time.sleep(self.FIRST_FRAME_POLL_INTERVAL)

                    warmup = time.monotonic() - started
                    return {
                        "success": True,
                        "message": "Camera connection successful",
                        "resolution": f"{frame.shape[1]}x{frame.shape[0]}",
                        "warmup_seconds": round(warmup, 2),
                    }
                finally:
                    if cap is not None:
                        try:
                            cap.release()
                        except Exception:
                            pass

            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _blocking_probe)

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_discovery_status(self) -> Dict:
        """Get current discovery status"""
        return {
            "scanning": self.scanning,
            "cameras_found": len(self.discovered_cameras),
        }


# Global discovery service instance
discovery_service = CameraDiscovery()
