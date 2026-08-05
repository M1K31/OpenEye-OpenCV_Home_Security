# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Camera Discovery Service
Discovers RTSP/IP cameras on network and USB cameras connected to the system.
"""
import cv2
import glob
import json
import os
import socket
import platform
import logging
import asyncio
import subprocess
import time
from typing import List, Dict, Optional
from datetime import datetime
import netifaces
import ipaddress

logger = logging.getLogger(__name__)


class CameraDiscovery:
    """
    Service for discovering cameras on the network and connected hardware.
    """

    # Highest camera index probed during USB discovery (0..N-1)
    MAX_CAMERA_INDEX = 11

    # How long to keep asking a device for its first frame once it has opened.
    #
    # A webcam delivers on the first read. An iPhone used as a Continuity Camera
    # does not: opening the device only *starts* the handshake — the phone shows
    # its "camera in use" notice and takes seconds to begin streaming. The probe
    # used to call read() exactly once, get False, and release the device, which
    # dropped the phone right as it was waking up.
    #
    # Only devices that OPEN but do not immediately produce a frame pay this cost,
    # so ordinary webcams are unaffected and empty slots (which fail to open at
    # all) are still rejected instantly.
    FIRST_FRAME_TIMEOUT = float(os.environ.get("OPENEYE_FIRST_FRAME_TIMEOUT", "12"))
    FIRST_FRAME_POLL_INTERVAL = 0.25

    def __init__(self):
        self.discovered_cameras = []
        self.scanning = False
        self._authorization_primed = False
        self._macos_camera_cache = None

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
                    capture_output=True, text=True, timeout=15,
                ).stdout
                entries = json.loads(output).get("SPCameraDataType", [])
                return [
                    {"name": e.get("_name", f"Camera {i}"), "index": i}
                    for i, e in enumerate(entries)
                ]

            if system == "Linux":
                nodes = sorted(glob.glob("/dev/video*"))
                return [
                    {"name": f"Video device {node}",
                     "index": int(node.rsplit("video", 1)[-1])}
                    for node in nodes
                    if node.rsplit("video", 1)[-1].isdigit()
                ]

        except Exception as e:
            logger.debug(f"Platform camera enumeration unavailable: {e}")

        return []

    def _prime_macos_authorization(self) -> None:
        """
        Give macOS one chance to raise the camera permission dialog.

        AVFoundation refuses to request authorization from a worker thread
        ("can not spin main run loop from other thread"), so this runs inline
        on the calling thread. It is attempted once per process and is a no-op
        off macOS. Whether a dialog actually appears is up to the OS: a process
        with no application bundle, or one started by launchd, is denied
        without any prompt, which is why discovery still reports the denial
        explicitly rather than relying on this succeeding.
        """
        self._authorization_primed = True

        if platform.system() != "Darwin":
            return

        try:
            cap = cv2.VideoCapture(0)
            authorized = cap.isOpened()
            cap.release()
            if not authorized:
                logger.debug(
                    "macOS did not grant camera access on the priming probe")
        except Exception as e:
            logger.debug(f"Camera authorization priming failed: {e}")

    def _probe_index(self, index: int) -> Optional[Dict]:
        """
        Blocking probe of a single camera index. Runs in a worker thread.

        Returns camera info if the index yields a readable frame, else None.
        """
        cap = None
        identity = self._describe_device(index)
        label = identity.get("name") or f"index {index}"
        try:
            cap = cv2.VideoCapture(index)
            if not cap.isOpened():
                # Logged at INFO, not DEBUG: when a camera the OS clearly lists
                # cannot be opened, that fact is the whole diagnosis and it needs
                # to be visible in the normal log. Silence here is what made an
                # earlier camera outage so slow to pin down.
                logger.info(
                    "Camera probe: index %s (%s) is listed by the OS but "
                    "VideoCapture could not open it", index, label)
                return None
            logger.info("Camera probe: index %s (%s) opened", index, label)

            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))

            # Wait for the first frame rather than demanding one immediately. See
            # FIRST_FRAME_TIMEOUT: a Continuity Camera opens straight away but only
            # starts streaming once the phone has woken, so a single read() rejected
            # it every time. Anything that opens deserves the chance to warm up.
            deadline = time.monotonic() + self.FIRST_FRAME_TIMEOUT
            first_frame_after = None
            started = time.monotonic()
            while True:
                ret, frame = cap.read()
                if ret and frame is not None:
                    first_frame_after = time.monotonic() - started
                    break
                if time.monotonic() >= deadline:
                    logger.debug(
                        "Index %s opened but produced no frame within %.0fs",
                        index, self.FIRST_FRAME_TIMEOUT)
                    return None
                time.sleep(self.FIRST_FRAME_POLL_INTERVAL)

            # Re-read the geometry from the delivered frame. A device that is still
            # negotiating reports placeholder dimensions, so the CAP_PROP values
            # taken before the first frame can be wrong (or 0x0).
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
                # A device that needed a noticeable warm-up is almost certainly a
                # Continuity Camera; surface it so the UI can explain the delay.
                "slow_start": first_frame_after > 1.5,
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

        OpenCV reports a permission denial exactly the same way it reports an
        empty slot: VideoCapture.isOpened() returns False and nothing is
        raised. Cross-referencing against the OS device list turns that silent
        failure into an actionable message.

        Returns:
            {"cameras": [...], "warnings": [...], "permission_denied": bool}
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

        # AVFoundation can only raise its permission dialog from the thread
        # running the main loop, so the very first probe is deliberately not
        # sent to the executor. Skipping this would mean the prompt could
        # never appear, even when the process is entitled to show one.
        if platform_cameras and not self._authorization_primed:
            self._prime_macos_authorization()

        # Prefer the indices the OS actually reported. Blind-probing 0..10
        # costs seconds per absent index and, on macOS, emits a stream of
        # AVFoundation authorization warnings for slots that never existed.
        if platform_cameras:
            indices = [c["index"] for c in platform_cameras]
        else:
            indices = list(range(self.MAX_CAMERA_INDEX))

        # Probe off the event loop; VideoCapture blocks for seconds per index
        # and would otherwise stall every other request, including WebSocket
        # handshakes.
        results = await asyncio.gather(
            *(loop.run_in_executor(None, self._probe_index, i)
              for i in indices)
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
                f"{cam['resolution']} @ {cam['fps']}fps")

        logger.info(
            f"USB camera discovery complete. Found {len(usb_cameras)} cameras")

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
        return "Check the operating system's camera privacy settings."

    def _list_macos_cameras(self) -> List[Dict]:
        """
        Names and unique IDs of every camera macOS knows about, in system order.

        Cached for the life of the service: system_profiler takes ~1s, and probing
        calls this once per index.
        """
        if getattr(self, "_macos_camera_cache", None) is not None:
            return self._macos_camera_cache

        cameras: List[Dict] = []
        if platform.system() == "Darwin":
            try:
                out = subprocess.run(
                    ["system_profiler", "SPCameraDataType", "-json"],
                    capture_output=True, text=True, timeout=15,
                ).stdout
                for entry in json.loads(out).get("SPCameraDataType", []):
                    cameras.append({
                        "name": entry.get("_name"),
                        "uid": entry.get("spcamera_unique-id"),
                        "model": entry.get("spcamera_model-id"),
                    })
            except Exception as e:
                logger.debug("Could not enumerate macOS cameras: %s", e)

        self._macos_camera_cache = cameras
        return cameras

    def _describe_device(self, index: int) -> Dict:
        """
        Best-effort real name and unique ID for an OpenCV camera index.

        IMPORTANT — this is a positional guess, not an exact mapping. OpenCV's
        AVFoundation backend addresses cameras by index and exposes no identifier,
        so the only thing available is to line its indices up against the order
        system_profiler reports. That order has matched in practice, but nothing
        guarantees it, which is why the uid is recorded as a *hint* for detecting
        drift rather than as something to open a camera by.

        Returns empty values when the platform is not macOS or the lookup fails;
        callers fall back to the index-based label.
        """
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
        Discover RTSP/IP cameras on the local network.

        Args:
            subnet: Optional subnet to scan (e.g., '192.168.1.0/24')
                   If None, will scan all local subnets
            timeout: Maximum time in seconds for the entire scan (default: 60)

        Returns:
            List of discovered network cameras (returns partial results if timeout)
        """
        logger.info(
            f"Starting network camera discovery... (timeout: {timeout}s)")
        self.scanning = True
        network_cameras = []

        async def _do_scan():
            """Inner function to perform the actual scan"""
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
                        logger.warning(
                            f"Subnet {subnet_cidr} too large, skipping")
                        continue

                    # Scan each IP in the subnet
                    tasks = []
                    for ip in network.hosts():
                        for port in rtsp_ports:
                            tasks.append(self._check_rtsp_port(str(ip), port))

                    # Run scans concurrently (in batches to avoid overwhelming
                    # network)
                    batch_size = 50
                    for i in range(0, len(tasks), batch_size):
                        batch = tasks[i: i + batch_size]
                        results = await asyncio.gather(*batch, return_exceptions=True)

                        for result in results:
                            if result and not isinstance(result, Exception):
                                network_cameras.append(result)
                                logger.info(f"Found camera at {result['ip']}:{result['port']}")

            except Exception as e:
                logger.error(f"Error during network discovery: {e}")

        try:
            # Run scan with timeout
            await asyncio.wait_for(_do_scan(), timeout=timeout)
            logger.info(f"Network camera discovery complete. Found {len(network_cameras)} cameras")
        except asyncio.TimeoutError:
            logger.warning(f"Network scan timed out after {timeout}s. Returning {len(network_cameras)} cameras found so far")
        except Exception as e:
            logger.error(f"Unexpected error during network discovery: {e}")
        finally:
            self.scanning = False

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
                        ip = addr_info.get("addr")
                        netmask = addr_info.get("netmask")

                        if ip and netmask and not ip.startswith("127."):
                            # Calculate subnet
                            network = ipaddress.ip_network(
                                f"{ip}/{netmask}", strict=False
                            )
                            subnets.append(str(network))

        except Exception as e:
            logger.error(f"Error getting local subnets: {e}")
            # Fallback to common subnet
            subnets = ["192.168.1.0/24"]

        return subnets

    async def _check_rtsp_port(
        self, ip: str, port: int, timeout: float = 1.0
    ) -> Optional[Dict]:
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
            response = await self._rtsp_options_probe(ip, port, timeout)

            # An open port proves nothing: 88 and 8080 are overwhelmingly HTTP
            # admin panels. Only a device that answers the RTSP handshake is a
            # camera, so anything else is discarded rather than guessed at.
            if not response or not response.startswith(b"RTSP/"):
                if response:
                    logger.debug(
                        f"{ip}:{port} is open but does not speak RTSP; ignoring")
                return None

            status_line = response.split(b"\r\n", 1)[0].decode(
                "ascii", "replace")
            requires_auth = b" 401 " in response or b" 403 " in response

            common_urls = [
                f"rtsp://{ip}:{port}/stream",
                f"rtsp://{ip}:{port}/stream1",
                f"rtsp://{ip}:{port}/h264",
                f"rtsp://{ip}:{port}/live",
                f"rtsp://{ip}:{port}/cam/realmonitor?channel=1&subtype=0",
            ]

            note = (
                "RTSP server confirmed. Credentials are required; enter the "
                "camera's username and password when adding it."
                if requires_auth
                else "RTSP server confirmed. The stream path may still need "
                     "adjusting for this camera model."
            )

            return {
                "type": "rtsp",
                "ip": ip,
                "port": port,
                "name": f"IP Camera at {ip}",
                "urls": common_urls,
                "status": "available",
                "requires_auth": requires_auth,
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

    async def _rtsp_options_probe(
        self, ip: str, port: int, timeout: float = 2.0
    ) -> Optional[bytes]:
        """
        Send an RTSP OPTIONS request and return the raw reply.

        A genuine RTSP server answers with a "RTSP/1.0 <code>" status line even
        when it rejects the request for lack of credentials, which is what
        distinguishes a camera from any other service on the same port.

        Returns:
            Raw response bytes, or None if the port is closed or silent.
        """
        writer = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port), timeout=timeout
            )
            request = (
                f"OPTIONS rtsp://{ip}:{port} RTSP/1.0\r\n"
                f"CSeq: 1\r\n"
                f"User-Agent: OpenEye-Discovery\r\n"
                f"\r\n"
            ).encode("ascii")
            writer.write(request)
            await writer.drain()
            return await asyncio.wait_for(reader.read(1024), timeout=timeout)
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

        Args:
            url: RTSP URL to test
            timeout: Timeout in seconds

        Returns:
            True if stream is accessible, False otherwise
        """
        def _blocking_test():
            try:
                cap = cv2.VideoCapture(url)
                cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(timeout * 1000))
                is_opened = cap.isOpened()
                cap.release()
                return is_opened
            except Exception as e:
                logger.debug(f"Error testing RTSP stream {url}: {e}")
                return False

        try:
            # Run blocking OpenCV operation in thread pool
            loop = asyncio.get_event_loop()
            return await asyncio.wait_for(
                loop.run_in_executor(None, _blocking_test),
                timeout=timeout + 1.0  # Extra second for executor overhead
            )
        except asyncio.TimeoutError:
            logger.debug(f"RTSP stream test timed out: {url}")
            return False
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
            camera_type = camera_config.get(
                "camera_type", camera_config.get("type"))
            source = camera_config.get("source")

            if not source:
                return {"success": False, "error": "No source specified"}

            # Convert source to appropriate type
            if camera_type == "usb":
                source = int(source)

            # Try to open the camera
            cap = cv2.VideoCapture(source)

            if not cap.isOpened():
                cap.release()
                return {"success": False, "error": "Failed to open camera"}

            # Try to read a frame
            ret, frame = cap.read()
            cap.release()

            if not ret:
                return {
                    "success": False,
                    "error": "Failed to read from camera"}

            return {
                "success": True,
                "message": "Camera connection successful",
                "resolution": f"{frame.shape[1]}x{frame.shape[0]}",
            }

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
