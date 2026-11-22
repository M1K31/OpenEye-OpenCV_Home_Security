# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Optional RTSP / WebRTC Stream Relay Manager (go2rtc & MediaMTX Integration)

Sits between IP cameras (such as TP-Link Tapo, Hikvision, Dahua, Reolink) and
OpenEye's OpenCV capture pipeline + browser dashboard:
  - Prevents camera connection exhaustion (most consumer cameras only allow 1-2
    simultaneous RTSP sessions) by multiplexing a single upstream camera connection
    to multiple local consumers (OpenCV motion/face detector, FFmpeg recorder, and
    browser WebRTC/MSE live streams).
  - Supports both `go2rtc` (MIT, port 1984 API / 8554 RTSP) and `MediaMTX`
    (MIT, port 9997 API / 8554 RTSP) with `sourceOnDemand` resource conservation.
  - Automatically infers low-CPU sub-stream URLs (e.g. Tapo `/stream2`, Hikvision
    `Channels/102`, Dahua `subtype=1`, Reolink `_sub`) alongside high-res main streams.
  - Degrades gracefully to direct OpenCV RTSP connection when no relay sidecar or
    binary is present, so OpenEye works standalone with zero hard dependencies.
"""

import logging
import os
import shutil
import socket
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import json

from backend.core.camera_security import (
    decrypt_camera_source,
    redact_url_credentials,
)

logger = logging.getLogger(__name__)


@dataclass
class RelayedStreamInfo:
    """Metadata for a camera registered with the stream relay."""

    camera_id: str
    backend: str  # "go2rtc", "mediamtx", or "direct"
    upstream_main: str
    upstream_sub: Optional[str] = None
    rtsp_main_url: str = ""
    rtsp_sub_url: Optional[str] = None
    webrtc_url: Optional[str] = None
    mse_url: Optional[str] = None
    mjpeg_url: Optional[str] = None
    source_on_demand: bool = True

    def to_public_dict(self) -> Dict:
        """Return safe dictionary with upstream and direct credentials redacted."""
        return {
            "camera_id": self.camera_id,
            "backend": self.backend,
            "upstream_main": redact_url_credentials(self.upstream_main),
            "upstream_sub": redact_url_credentials(self.upstream_sub)
            if self.upstream_sub
            else None,
            "rtsp_main_url": redact_url_credentials(self.rtsp_main_url),
            "rtsp_sub_url": redact_url_credentials(self.rtsp_sub_url)
            if self.rtsp_sub_url
            else None,
            "webrtc_url": self.webrtc_url,
            "mse_url": self.mse_url,
            "mjpeg_url": self.mjpeg_url,
            "source_on_demand": self.source_on_demand,
        }


def infer_sub_stream_url(main_url: str) -> Optional[str]:
    """
    Infer a camera's low-resolution secondary stream URL from its primary RTSP URL.

    Used to offload continuous OpenCV motion/face detection onto a 360p/480p
    sub-stream (~75% lower CPU/RAM usage) while keeping the 1080p/2K main stream
    for recordings and HD viewing.
    """
    if not main_url or not isinstance(main_url, str):
        return None
    decrypted = decrypt_camera_source(main_url)
    if not decrypted.startswith(("rtsp://", "rtsps://")):
        return None

    # TP-Link Tapo: /stream1 -> /stream2
    if decrypted.endswith("/stream1"):
        return decrypted[:-8] + "/stream2"
    # Hikvision / Annke: /Streaming/Channels/101 -> /Streaming/Channels/102
    if "/Streaming/Channels/101" in decrypted:
        return decrypted.replace(
            "/Streaming/Channels/101", "/Streaming/Channels/102", 1
        )
    # Dahua / Amcrest / Lorex: subtype=0 -> subtype=1
    if "subtype=0" in decrypted:
        return decrypted.replace("subtype=0", "subtype=1", 1)
    # Reolink: _main -> _sub
    if "_main" in decrypted:
        return decrypted.replace("_main", "_sub", 1)
    # Foscam: /videoMain -> /videoSub
    if decrypted.endswith("/videoMain"):
        return decrypted[:-10] + "/videoSub"
    # Ubiquiti UniFi: /s0 -> /s1
    if decrypted.endswith("/s0"):
        return decrypted[:-3] + "/s1"

    return None


class StreamRelayManager:
    """
    Manages optional `go2rtc` or `MediaMTX` RTSP/WebRTC relay integration.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._streams: Dict[str, RelayedStreamInfo] = {}
        self._process: Optional[subprocess.Popen] = None
        self._detected_backend: Optional[str] = None

        self.mode = os.getenv("OPENEYE_STREAM_RELAY", "auto").strip().lower()
        self.go2rtc_api = os.getenv(
            "OPENEYE_GO2RTC_API_URL", "http://127.0.0.1:1984"
        ).rstrip("/")
        self.go2rtc_rtsp = os.getenv(
            "OPENEYE_GO2RTC_RTSP_URL", "rtsp://127.0.0.1:8554"
        ).rstrip("/")
        self.mediamtx_api = os.getenv(
            "OPENEYE_MEDIAMTX_API_URL", "http://127.0.0.1:9997"
        ).rstrip("/")
        self.mediamtx_rtsp = os.getenv(
            "OPENEYE_MEDIAMTX_RTSP_URL", "rtsp://127.0.0.1:8554"
        ).rstrip("/")
        self.prefer_substream_for_opencv = (
            os.getenv("OPENEYE_RELAY_USE_SUBSTREAM", "false").lower() == "true"
        )

    def _http_request(
        self,
        method: str,
        url: str,
        payload: Optional[Dict] = None,
        timeout: float = 1.5,
    ) -> Tuple[int, bytes]:
        """Lightweight stdlib HTTP helper (avoids async/sync loop conflicts)."""
        data = None
        headers = {"User-Agent": "OpenEye-StreamRelay"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = Request(url, data=data, headers=headers, method=method)
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()

    def _probe_go2rtc(self, timeout: float = 0.6) -> bool:
        """Return True if a go2rtc API server is reachable."""
        try:
            status, _ = self._http_request(
                "GET", f"{self.go2rtc_api}/api", timeout=timeout
            )
            return 200 <= status < 300
        except Exception:
            return False

    def _probe_mediamtx(self, timeout: float = 0.6) -> bool:
        """Return True if a MediaMTX v3 API server is reachable."""
        try:
            status, _ = self._http_request(
                "GET", f"{self.mediamtx_api}/v3/config/global/get", timeout=timeout
            )
            return 200 <= status < 300
        except Exception:
            return False

    def detect_active_backend(self, force_refresh: bool = False) -> str:
        """
        Detect whether `go2rtc` or `mediamtx` is available, or return `"direct"`.
        """
        if self.mode in ("disabled", "off", "false", "direct"):
            self._detected_backend = "direct"
            return "direct"

        if self._detected_backend and not force_refresh:
            return self._detected_backend

        if self.mode in ("auto", "go2rtc") and self._probe_go2rtc():
            self._detected_backend = "go2rtc"
            return "go2rtc"

        if self.mode in ("auto", "mediamtx") and self._probe_mediamtx():
            self._detected_backend = "mediamtx"
            return "mediamtx"

        self._detected_backend = "direct"
        return "direct"

    def register_camera(
        self,
        camera_id: str,
        source: str,
        sub_source: Optional[str] = None,
        source_on_demand: bool = True,
    ) -> RelayedStreamInfo:
        """
        Register a camera's RTSP stream(s) with the active relay (if available)
        or return direct stream info when running without a relay.
        """
        clean_source = decrypt_camera_source(source)
        if not clean_source or not str(clean_source).startswith(
            ("rtsp://", "rtsps://", "rtmp://")
        ):
            info = RelayedStreamInfo(
                camera_id=camera_id,
                backend="direct",
                upstream_main=str(clean_source or source),
                rtsp_main_url=str(clean_source or source),
            )
            with self._lock:
                self._streams[camera_id] = info
            return info

        inferred_sub = decrypt_camera_source(sub_source) if sub_source else infer_sub_stream_url(clean_source)
        backend = self.detect_active_backend()

        if backend == "go2rtc":
            info = self._register_go2rtc(
                camera_id, clean_source, inferred_sub, source_on_demand
            )
        elif backend == "mediamtx":
            info = self._register_mediamtx(
                camera_id, clean_source, inferred_sub, source_on_demand
            )
        else:
            info = RelayedStreamInfo(
                camera_id=camera_id,
                backend="direct",
                upstream_main=clean_source,
                upstream_sub=inferred_sub,
                rtsp_main_url=clean_source,
                rtsp_sub_url=inferred_sub,
                source_on_demand=source_on_demand,
            )

        with self._lock:
            self._streams[camera_id] = info
        return info

    def _register_go2rtc(
        self,
        camera_id: str,
        main_source: str,
        sub_source: Optional[str],
        source_on_demand: bool,
    ) -> RelayedStreamInfo:
        """Register main (and optional sub) stream in go2rtc via PUT /api/streams."""
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", camera_id)
        try:
            query_main = urlencode({"name": safe_id, "src": main_source})
            self._http_request(
                "PUT", f"{self.go2rtc_api}/api/streams?{query_main}"
            )

            rtsp_sub_url = None
            if sub_source:
                sub_id = f"{safe_id}_sub"
                query_sub = urlencode({"name": sub_id, "src": sub_source})
                self._http_request(
                    "PUT", f"{self.go2rtc_api}/api/streams?{query_sub}"
                )
                rtsp_sub_url = f"{self.go2rtc_rtsp}/{sub_id}"

            logger.info(
                "Registered camera '%s' with go2rtc relay (%s)",
                camera_id,
                redact_url_credentials(main_source),
            )
            return RelayedStreamInfo(
                camera_id=camera_id,
                backend="go2rtc",
                upstream_main=main_source,
                upstream_sub=sub_source,
                rtsp_main_url=f"{self.go2rtc_rtsp}/{safe_id}",
                rtsp_sub_url=rtsp_sub_url,
                webrtc_url=f"{self.go2rtc_api}/api/webrtc?src={quote(safe_id)}",
                mse_url=f"{self.go2rtc_api}/api/stream.mp4?src={quote(safe_id)}",
                mjpeg_url=f"{self.go2rtc_api}/api/stream.mjpeg?src={quote(safe_id)}",
                source_on_demand=source_on_demand,
            )
        except Exception as e:
            logger.warning(
                "go2rtc registration failed for '%s' (%s); falling back to direct RTSP",
                camera_id,
                e,
            )
            self._detected_backend = "direct"
            return RelayedStreamInfo(
                camera_id=camera_id,
                backend="direct",
                upstream_main=main_source,
                upstream_sub=sub_source,
                rtsp_main_url=main_source,
                rtsp_sub_url=sub_source,
                source_on_demand=source_on_demand,
            )

    def _register_mediamtx(
        self,
        camera_id: str,
        main_source: str,
        sub_source: Optional[str],
        source_on_demand: bool,
    ) -> RelayedStreamInfo:
        """
        Register main (and optional sub) stream in MediaMTX via v3 REST API
        with `sourceOnDemand` enabled for resource conservation.
        """
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", camera_id)
        try:
            payload_main = {
                "source": main_source,
                "sourceOnDemand": bool(source_on_demand),
                "sourceProtocol": "tcp",
            }
            try:
                self._http_request(
                    "POST",
                    f"{self.mediamtx_api}/v3/config/paths/add/{quote(safe_id)}",
                    payload=payload_main,
                )
            except Exception:
                # Path may already exist; patch it
                self._http_request(
                    "PATCH",
                    f"{self.mediamtx_api}/v3/config/paths/patch/{quote(safe_id)}",
                    payload=payload_main,
                )

            rtsp_sub_url = None
            if sub_source:
                sub_id = f"{safe_id}_sub"
                payload_sub = {
                    "source": sub_source,
                    "sourceOnDemand": True,
                    "sourceProtocol": "tcp",
                }
                try:
                    self._http_request(
                        "POST",
                        f"{self.mediamtx_api}/v3/config/paths/add/{quote(sub_id)}",
                        payload=payload_sub,
                    )
                except Exception:
                    self._http_request(
                        "PATCH",
                        f"{self.mediamtx_api}/v3/config/paths/patch/{quote(sub_id)}",
                        payload=payload_sub,
                    )
                rtsp_sub_url = f"{self.mediamtx_rtsp}/{sub_id}"

            logger.info(
                "Registered camera '%s' with MediaMTX relay (sourceOnDemand=%s)",
                camera_id,
                source_on_demand,
            )
            return RelayedStreamInfo(
                camera_id=camera_id,
                backend="mediamtx",
                upstream_main=main_source,
                upstream_sub=sub_source,
                rtsp_main_url=f"{self.mediamtx_rtsp}/{safe_id}",
                rtsp_sub_url=rtsp_sub_url,
                webrtc_url=f"http://127.0.0.1:8889/{quote(safe_id)}/whep",
                source_on_demand=source_on_demand,
            )
        except Exception as e:
            logger.warning(
                "MediaMTX registration failed for '%s' (%s); falling back to direct RTSP",
                camera_id,
                e,
            )
            self._detected_backend = "direct"
            return RelayedStreamInfo(
                camera_id=camera_id,
                backend="direct",
                upstream_main=main_source,
                upstream_sub=sub_source,
                rtsp_main_url=main_source,
                rtsp_sub_url=sub_source,
                source_on_demand=source_on_demand,
            )

    def unregister_camera(self, camera_id: str) -> None:
        """Remove a camera's streams from the relay when deleted/stopped."""
        with self._lock:
            info = self._streams.pop(camera_id, None)
        if not info or info.backend == "direct":
            return

        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", camera_id)
        try:
            if info.backend == "go2rtc":
                self._http_request(
                    "DELETE",
                    f"{self.go2rtc_api}/api/streams?src={quote(safe_id)}",
                )
            elif info.backend == "mediamtx":
                self._http_request(
                    "DELETE",
                    f"{self.mediamtx_api}/v3/config/paths/delete/{quote(safe_id)}",
                )
        except Exception as e:
            logger.debug("Relay unregister for '%s' ignored: %s", camera_id, e)

    def resolve_capture_source(self, camera_id: str, raw_source: str) -> str:
        """
        Return the optimal RTSP URL for OpenCV VideoCapture:
        - If a relay (`go2rtc` or `MediaMTX`) is active, registers the stream and
          returns the local relayed RTSP URL (`rtsp://127.0.0.1:8554/...`).
        - If `OPENEYE_RELAY_USE_SUBSTREAM=true` and a sub-stream is available,
          returns the sub-stream URL for low-CPU OpenCV analysis.
        - Otherwise returns the decrypted direct camera source.
        """
        clean = decrypt_camera_source(raw_source)
        if not clean or not str(clean).startswith(("rtsp://", "rtsps://", "rtmp://")):
            return clean

        info = self.register_camera(camera_id or "camera", clean)
        if self.prefer_substream_for_opencv and info.rtsp_sub_url:
            return info.rtsp_sub_url
        return info.rtsp_main_url

    def get_status(self) -> Dict:
        """Return relay health, active backend, and registered camera streams."""
        backend = self.detect_active_backend(force_refresh=True)
        with self._lock:
            streams = [s.to_public_dict() for s in self._streams.values()]

        return {
            "mode": self.mode,
            "active_backend": backend,
            "relay_active": backend in ("go2rtc", "mediamtx"),
            "go2rtc_api_url": self.go2rtc_api,
            "mediamtx_api_url": self.mediamtx_api,
            "prefer_substream_for_opencv": self.prefer_substream_for_opencv,
            "registered_streams_count": len(streams),
            "streams": streams,
        }


import re  # noqa: E402

# Global singleton
stream_relay = StreamRelayManager()
