# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Multi-Vendor PTZ Controller Module
Handles Pan-Tilt-Zoom camera control operations across popular IP camera brands:
- Standard ONVIF Profile S (TP-Link Tapo on :2020, Hikvision, Dahua/Amcrest,
  Reolink on :8000, Axis, Uniview, Bosch, Generic ONVIF on :80/:8080/:8899)
  using both a zero-dependency SOAP 1.1/1.2 + WS-UsernameToken Digest engine
  (with camera clock-skew compensation and macOS /usr/bin/curl fallback) and
  optional `onvif-zeep`.
- Tapo Native Motor Control (`pytapo` / HTTPS `:443` `motor.move` / `movestep`)
  as an automatic secondary driver alongside ONVIF `:2020`.
- Vendor HTTP/CGI Fallbacks:
  - Hikvision ISAPI (`/ISAPI/PTZCtrl/channels/1/...`)
  - Dahua / Amcrest HTTP CGI (`/cgi-bin/ptz.cgi?...`)
  - Reolink HTTP JSON API (`/cgi-bin/api.cgi?cmd=PtzCtrl`)
  - Axis VAPIX (`/axis-cgi/com/ptz.cgi?...`)
- Fast, non-blocking timed velocity bursts with generation counters so rapid
  directional clicks move the camera briskly without canceling each other.
"""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import hashlib
import json
import logging
import math
import os
import re
import secrets
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)

# Common ONVIF ports across camera brands:
# - 2020: TP-Link Tapo / VIGI
# - 80:   Hikvision, Dahua, Amcrest, Axis, Bosch, Uniview
# - 8000: Reolink, Hikvision
# - 8080: Foscam, Generic ONVIF
# - 8899: Generic ONVIF / XMeye
# - 8090: Uniview / Generic
DEFAULT_ONVIF_PORTS: Tuple[int, ...] = (2020, 80, 8000, 8080, 8899, 8090)

VENDOR_PORT_PRIORITY: Dict[str, Tuple[int, ...]] = {
    "tapo": (2020, 80, 8000, 8080, 8899),
    "hikvision": (80, 8000, 2020, 8080, 8899),
    "dahua": (80, 8080, 2020, 8000, 8899),
    "reolink": (8000, 80, 2020, 8080, 8899),
    "axis": (80, 8080, 2020, 8000),
    "foscam": (88, 8080, 80, 2020, 8899),
    "generic": DEFAULT_ONVIF_PORTS,
}


def build_wsse_security_header(
    username: str, password: str, time_offset_seconds: float = 0.0
) -> str:
    """
    Build an OASIS WS-Security `UsernameToken` XML header with `PasswordDigest`.

    ONVIF specification requires:
        Digest = Base64(SHA-1(raw_nonce + utf8(created) + utf8(password)))
    """
    if not username:
        return ""
    raw_nonce = secrets.token_bytes(16)
    nonce_b64 = base64.b64encode(raw_nonce).decode("ascii")
    now_utc = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=time_offset_seconds)
    created = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    # SHA-1 is what ONVIF's WS-Security PasswordDigest is defined as; the
    # camera computes the same value to check it. Nothing is stored.
    digest_bytes = hashlib.sha1(
        raw_nonce + created.encode("utf-8") + (password or "").encode("utf-8")
    ).digest()
    digest_b64 = base64.b64encode(digest_bytes).decode("ascii")

    safe_user = (
        username.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

    return (
        '<s:Header>'
        '<Security s:mustUnderstand="1" '
        'xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">'
        '<UsernameToken>'
        f'<Username>{safe_user}</Username>'
        '<Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordDigest">'
        f'{digest_b64}</Password>'
        '<Nonce EncodingType="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-soap-message-security-1.0#Base64Binary">'
        f'{nonce_b64}</Nonce>'
        '<Created xmlns="http://docs.oasis-open.org/wss/2004/01/oasis-wssecurity-utility-1.0.xsd">'
        f'{created}</Created>'
        '</UsernameToken>'
        '</Security>'
        '</s:Header>'
    ).replace(
        "http://docs.oasis-open.org/wss/2004/01/oasis-wssecurity-utility-1.0.xsd",
        "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd",
    )


def build_soap_envelope(
    body_xml: str,
    username: str = "",
    password: str = "",
    time_offset_seconds: float = 0.0,
) -> str:
    """Wrap an ONVIF request body in a SOAP 1.2 envelope with optional WS-Security."""
    header_xml = (
        build_wsse_security_header(username, password, time_offset_seconds)
        if username
        else "<s:Header/>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope" '
        'xmlns:tds="http://www.onvif.org/ver10/device/wsdl" '
        'xmlns:trt="http://www.onvif.org/ver10/media/wsdl" '
        'xmlns:tptz="http://www.onvif.org/ver20/ptz/wsdl" '
        'xmlns:tev="http://www.onvif.org/ver10/events/wsdl" '
        'xmlns:timg="http://www.onvif.org/ver20/imaging/wsdl" '
        'xmlns:tt="http://www.onvif.org/ver10/schema">'
        f'{header_xml}'
        f'<s:Body>{body_xml}</s:Body>'
        '</s:Envelope>'
    )


def _rewrite_xaddr_host(xaddr: str, target_ip: str, fallback_port: int) -> str:
    """
    Ensure an XAddr returned by a camera points to `target_ip` rather than an
    internal/NAT/link-local address the camera might report in SOAP responses.
    """
    try:
        parts = urlsplit(xaddr.strip())
        if not parts.scheme or not parts.hostname:
            return xaddr
        port = parts.port or fallback_port
        netloc = f"{target_ip}:{port}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return xaddr


_HTTP_SESSION_POOL: Dict[Tuple[str, str, bool], Any] = {}


def _get_keepalive_session(origin: str, username: str, password: str, use_http_auth: bool):
    """Return a persistent HTTP keep-alive session per camera origin to avoid TCP handshake lag."""
    key = (origin, username or "", bool(use_http_auth))
    sess = _HTTP_SESSION_POOL.get(key)
    if sess is not None:
        return sess
    try:
        import requests
        from requests.auth import HTTPDigestAuth

        sess = requests.Session()
        sess.headers.update({"Connection": "keep-alive"})
        if username and use_http_auth:
            sess.auth = HTTPDigestAuth(username, password or "")
        _HTTP_SESSION_POOL[key] = sess
        return sess
    except Exception:
        return None


def send_http_or_soap_request(
    url: str,
    method: str = "POST",
    body: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    username: str = "",
    password: str = "",
    timeout: float = 2.5,
    use_http_auth: bool = True,
) -> Tuple[int, str]:
    """
    Send an HTTP/SOAP request with persistent HTTP keep-alive connection pooling,
    optional HTTP Digest/Basic auth, and a fast single-pass `/usr/bin/curl` fallback
    (resolves macOS Local Network privacy `EHOSTUNREACH` / `Errno 65` restrictions).
    """
    req_headers = dict(headers or {})
    data_bytes = body.encode("utf-8") if body is not None else None

    # Fast path: reuse persistent keep-alive TCP socket via requests.Session
    try:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        sess = _get_keepalive_session(origin, "", "", False)
        if sess is not None:
            resp = sess.request(
                method=method,
                url=url,
                data=data_bytes,
                headers=req_headers,
                timeout=timeout,
                verify=False,
            )
            if resp.status_code == 401 and username and use_http_auth:
                auth_sess = _get_keepalive_session(origin, username, password, True)
                if auth_sess is not None:
                    resp = auth_sess.request(
                        method=method,
                        url=url,
                        data=data_bytes,
                        headers=req_headers,
                        timeout=timeout,
                        verify=False,
                    )
            return int(resp.status_code), resp.text
    except Exception:
        pass

    try:
        if username and use_http_auth:
            pwd_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            pwd_mgr.add_password(None, url, username, password or "")
            digest_handler = urllib.request.HTTPDigestAuthHandler(pwd_mgr)
            basic_handler = urllib.request.HTTPBasicAuthHandler(pwd_mgr)
            opener = urllib.request.build_opener(digest_handler, basic_handler)
        else:
            opener = urllib.request.build_opener()

        req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method)
        with opener.open(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            text = resp.read().decode("utf-8", errors="replace")
            return status, text
    except urllib.error.HTTPError as http_err:
        try:
            err_body = http_err.read().decode("utf-8", errors="replace")
        except Exception:
            err_body = ""
        return http_err.code, err_body
    except Exception as exc:
        curl_bin = "/usr/bin/curl" if os.path.exists("/usr/bin/curl") else shutil.which("curl")
        if not curl_bin:
            # The URL is not logged at all: it can carry camera credentials.
            logger.debug("PTZ HTTP request failed and curl is unavailable: %s", type(exc).__name__)
            return 0, type(exc).__name__

        # Single-pass curl first (no --anyauth double-roundtrip penalty when
        # WS-UsernameToken is already embedded inside the SOAP XML body!)
        cmd = [
            curl_bin,
            "-sS",
            "-k",
            "--max-time",
            str(max(1, int(math.ceil(timeout)))),
            "-X",
            method,
            "-w",
            "\n__HTTP_STATUS__:%{http_code}",
        ]
        for k, v in req_headers.items():
            cmd.extend(["-H", f"{k}: {v}"])
        if body is not None:
            cmd.extend(["--data-raw", body])
        cmd.append(url)

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 1.5,
                check=False,
            )
            out = proc.stdout or ""
            code = 0
            content = out
            if "__HTTP_STATUS__:" in out:
                content, status_str = out.rsplit("__HTTP_STATUS__:", 1)
                try:
                    code = int(status_str.strip())
                except ValueError:
                    code = 0

            # Only retry with HTTP Digest/Basic auth if the server explicitly challenged with 401
            if code == 401 and username and use_http_auth:
                auth_cmd = [
                    curl_bin,
                    "-sS",
                    "-k",
                    "--max-time",
                    str(max(1, int(math.ceil(timeout)))),
                    "--anyauth",
                    "-u",
                    f"{username}:{password}",
                    "-X",
                    method,
                    "-w",
                    "\n__HTTP_STATUS__:%{http_code}",
                ]
                for k, v in req_headers.items():
                    auth_cmd.extend(["-H", f"{k}: {v}"])
                if body is not None:
                    auth_cmd.extend(["--data-raw", body])
                auth_cmd.append(url)
                proc2 = subprocess.run(
                    auth_cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout + 2.0,
                    check=False,
                )
                out2 = proc2.stdout or ""
                if "__HTTP_STATUS__:" in out2:
                    c2, s2 = out2.rsplit("__HTTP_STATUS__:", 1)
                    try:
                        return int(s2.strip()), c2.strip()
                    except ValueError:
                        pass
            return code, content.strip()
        except Exception as curl_exc:
            # The exception text can carry the curl command line, which includes
            # `--user user:password`: only its type is logged or returned.
            logger.debug("PTZ curl fallback failed: %s", type(curl_exc).__name__)
            return 0, type(curl_exc).__name__


def _redact_url(url: str) -> str:
    """`url` without any `user:password@` part, for logs."""
    try:
        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(str(url))
        if parts.username or parts.password:
            host = parts.hostname or ""
            if parts.port:
                host = f"{host}:{parts.port}"
            return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))
        return str(url)
    except Exception:
        return "<url>"


def send_onvif_soap(
    url: str,
    body_xml: str,
    username: str = "",
    password: str = "",
    soap_action: Optional[str] = None,
    timeout: float = 2.5,
    time_offset_seconds: float = 0.0,
) -> Tuple[int, str]:
    """
    Send an ONVIF SOAP 1.2 request with both `action=` in `Content-Type` and an
    explicit `SOAPAction` header so both SOAP 1.1 and SOAP 1.2 camera webservers
    route the PTZ command without delay.
    """
    envelope = build_soap_envelope(
        body_xml,
        username=username,
        password=password,
        time_offset_seconds=time_offset_seconds,
    )
    content_type = "application/soap+xml; charset=utf-8"
    headers: Dict[str, str] = {}
    if soap_action:
        content_type += f'; action="{soap_action}"'
        headers["SOAPAction"] = f'"{soap_action}"'
    headers["Content-Type"] = content_type
    return send_http_or_soap_request(
        url=url,
        method="POST",
        body=envelope,
        headers=headers,
        username=username,
        password=password,
        timeout=timeout,
    )


def _local_name(tag: str) -> str:
    """Strip XML namespace URI from an ElementTree tag."""
    return tag.split("}", 1)[1] if "}" in tag else tag


def _boost_motor_velocity(val: float, min_active: float = 0.8) -> float:
    """
    Ensure non-zero PTZ velocities overcome stepper motor deadzones on cameras
    like TP-Link Tapo, Reolink, and Amcrest (where velocities < 0.5 often produce
    zero movement or imperceptible micro-crawling).
    """
    if abs(val) < 1e-4:
        return 0.0
    sign = 1.0 if val > 0 else -1.0
    return sign * max(min_active, min(1.0, abs(val)))


class PTZController:
    """
    Multi-Vendor PTZ Camera Controller
    Handles camera movement, presets, home position, and patrol patterns across
    ONVIF (Tapo, Hikvision, Dahua, Amcrest, Reolink, Axis, Generic) and vendor HTTP APIs.
    """

    def __init__(self, camera_id: str, ptz_type: str = "auto"):
        self.camera_id = camera_id
        self.ptz_type = ptz_type or "auto"
        self.active_protocol: Optional[str] = None
        self.camera_ip: str = ""
        self.port: int = 2020
        self.username: str = ""
        self.password: str = ""
        self.vendor_hint: str = "generic"
        self.device_info: Dict[str, str] = {}
        self.time_offset_seconds: float = 0.0

        # ONVIF state
        self.onvif_device = None
        self.ptz_service = None
        self.media_profile = None
        self.device_xaddr: str = ""
        self.media_xaddr: str = ""
        self.ptz_xaddr: str = ""
        self.events_xaddr: str = ""
        self.imaging_xaddr: str = ""
        self.profile_token: str = "profile_1"

        # Capability flags discovered during connect()
        self.has_pan_tilt: bool = True
        self.has_zoom: bool = False
        self.supports_continuous_move: bool = True
        self.supports_relative_move: bool = True
        self.supports_absolute_move: bool = True
        self.supports_home_position: bool = True
        self.supports_presets: bool = True
        self.is_connected: bool = False
        self.last_error: Optional[str] = None

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
            "zoom": 0.0,
        }

        # Non-blocking burst generation counter & auto-stop task
        self._move_generation: int = 0
        self._auto_stop_task: Optional[asyncio.Task] = None
        # Cache which ContinuousMove XML variant the camera prefers to avoid double SOAP calls
        self._continuous_use_space_attr: Optional[bool] = None

    def _cancel_pending_auto_stop(self) -> int:
        """Increment movement generation and cancel any scheduled auto-stop task."""
        self._move_generation += 1
        if self._auto_stop_task and not self._auto_stop_task.done():
            self._auto_stop_task.cancel()
        self._auto_stop_task = None
        return self._move_generation

    def _schedule_auto_stop(self, duration_seconds: float) -> None:
        """Schedule a non-blocking `Stop` after `duration_seconds` unless superseded."""
        gen = self._cancel_pending_auto_stop()

        async def _delayed_stop():
            try:
                await asyncio.sleep(max(0.25, duration_seconds))
                if self._move_generation == gen and self.is_connected:
                    await self.stop(cancel_timer=False)
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.debug("Auto-stop after burst failed: %s", exc)

        try:
            loop = asyncio.get_running_loop()
            self._auto_stop_task = loop.create_task(_delayed_stop())
        except RuntimeError:
            pass

    async def auto_connect_from_source(
        self, source: Optional[str], preferred_port: Optional[int] = None
    ) -> bool:
        """
        Automatically extract IP and decrypted credentials from `Camera.source`
        and connect to the camera's PTZ service.
        """
        from backend.core.camera_security import extract_camera_connection_info

        info = extract_camera_connection_info(source)
        if not info.get("is_network_camera") or not info.get("camera_ip"):
            self.last_error = "Camera source does not contain a network IP address"
            return False

        self.vendor_hint = info.get("vendor_hint", "generic")
        return await self.connect(
            camera_ip=info["camera_ip"],
            port=preferred_port or 0,
            username=info.get("username", ""),
            password=info.get("password", ""),
            vendor_hint=self.vendor_hint,
        )

    async def connect(
        self,
        camera_ip: str,
        port: int = 0,
        username: str = "",
        password: str = "",
        vendor_hint: Optional[str] = None,
    ) -> bool:
        """
        Connect to PTZ camera via ONVIF (auto-probing common vendor ports such as
        2020 for Tapo, 80 for Hikvision/Dahua/Amcrest/Axis, 8000 for Reolink,
        8080/8899 for generic ONVIF) with fallback to vendor HTTP CGI protocols.
        """
        self.camera_ip = (camera_ip or "").strip()
        self.username = username or ""
        self.password = password or ""
        if vendor_hint:
            self.vendor_hint = vendor_hint

        if not self.camera_ip:
            self.last_error = "Camera IP address is required"
            self.is_connected = False
            return False

        priority_ports = list(
            VENDOR_PORT_PRIORITY.get(self.vendor_hint, DEFAULT_ONVIF_PORTS)
        )
        candidate_ports: List[int] = []
        if port and port not in (0, 80):
            candidate_ports.append(int(port))
        for p in priority_ports:
            if p not in candidate_ports:
                candidate_ports.append(p)
        if port == 80 and 80 not in candidate_ports:
            candidate_ports.insert(0, 80)

        # 1. Try built-in SOAP 1.2 ONVIF engine across candidate ports
        if self.ptz_type in ("auto", "onvif"):
            for candidate_port in candidate_ports:
                ok = await asyncio.to_thread(
                    self._connect_onvif_soap,
                    self.camera_ip,
                    candidate_port,
                    self.username,
                    self.password,
                )
                if ok:
                    self.port = candidate_port
                    self.active_protocol = "onvif_soap"
                    self.is_connected = True
                    self.last_error = None
                    logger.info(
                        "PTZ connected via ONVIF SOAP to camera %s at %s:%s (profile=%s, ptz_xaddr=%s, zoom=%s)",
                        self.camera_id,
                        self.camera_ip,
                        self.port,
                        self.profile_token,
                        self.ptz_xaddr,
                        self.has_zoom,
                    )
                    return True

            # 2. Try onvif-zeep if installed and SOAP probing didn't succeed
            for candidate_port in candidate_ports[:2]:
                ok = await asyncio.to_thread(
                    self._connect_onvif_zeep,
                    self.camera_ip,
                    candidate_port,
                    self.username,
                    self.password,
                )
                if ok:
                    self.port = candidate_port
                    self.active_protocol = "onvif_zeep"
                    self.is_connected = True
                    self.last_error = None
                    return True

        # 3. Try Vendor HTTP/CGI Fallbacks
        if self.ptz_type in (
            "auto",
            "onvif",
            "hikvision_isapi",
            "dahua_cgi",
            "reolink_api",
            "axis_vapix",
            "foscam_cgi",
        ):
            ok = await asyncio.to_thread(
                self._connect_vendor_http_fallback,
                self.camera_ip,
                port or 80,
                self.username,
                self.password,
            )
            if ok:
                self.is_connected = True
                self.last_error = None
                return True

        self.is_connected = False
        if not self.last_error:
            self.last_error = (
                f"Could not connect to ONVIF/PTZ service on {self.camera_ip} "
                f"(probed ports {candidate_ports}). Ensure ONVIF/Third-Party Compatibility "
                "is enabled in your camera app."
            )
        logger.warning("PTZ connection failed for %s: %s", self.camera_id, self.last_error)
        return False

    def _sync_camera_clock_offset(self, device_url: str) -> None:
        """
        Query unauthenticated `<tds:GetSystemDateAndTime/>` to compute any clock
        offset between the camera and the host, preventing WS-UsernameToken
        timestamp rejections when a camera's NTP clock is skewed.
        """
        status, xml_text = send_onvif_soap(
            device_url, "<tds:GetSystemDateAndTime/>", timeout=1.8
        )
        if status != 200 or "<" not in xml_text:
            return
        try:
            root = ET.fromstring(xml_text)
            for utc_el in root.iter():
                if _local_name(utc_el.tag) == "UTCDateTime":
                    vals: Dict[str, int] = {}
                    for child in utc_el.iter():
                        cname = _local_name(child.tag)
                        if cname in ("Year", "Month", "Day", "Hour", "Minute", "Second") and child.text:
                            vals[cname] = int(child.text.strip())
                    if len(vals) == 6:
                        cam_dt = dt.datetime(
                            vals["Year"],
                            vals["Month"],
                            vals["Day"],
                            vals["Hour"],
                            vals["Minute"],
                            vals["Second"],
                            tzinfo=dt.timezone.utc,
                        )
                        host_dt = dt.datetime.now(dt.timezone.utc)
                        diff = (cam_dt - host_dt).total_seconds()
                        if abs(diff) > 3.0:
                            self.time_offset_seconds = diff
                            logger.info(
                                "Adjusted ONVIF WS-Security clock offset for %s by %.1fs",
                                self.camera_ip,
                                diff,
                            )
                    break
        except Exception:
            pass

    def _connect_onvif_soap(
        self, camera_ip: str, port: int, username: str, password: str
    ) -> bool:
        """
        Connect and discover Media + PTZ service XAddrs and profile tokens via
        raw ONVIF SOAP 1.2 + WS-UsernameToken Digest.
        """
        device_url = f"http://{camera_ip}:{port}/onvif/device_service"
        self.device_xaddr = device_url
        self._sync_camera_clock_offset(device_url)

        cap_body = (
            '<tds:GetCapabilities>'
            '<tds:Category>All</tds:Category>'
            '</tds:GetCapabilities>'
        )
        status, xml_text = send_onvif_soap(
            device_url,
            cap_body,
            username=username,
            password=password,
            timeout=2.5,
            time_offset_seconds=self.time_offset_seconds,
        )
        if status == 0 or "<" not in xml_text:
            return False

        if "Envelope" not in xml_text and "onvif" not in xml_text.lower():
            return False

        self.media_xaddr = f"http://{camera_ip}:{port}/onvif/service"
        self.ptz_xaddr = f"http://{camera_ip}:{port}/onvif/service"
        self.events_xaddr = f"http://{camera_ip}:{port}/onvif/service"
        self.imaging_xaddr = f"http://{camera_ip}:{port}/onvif/service"

        try:
            root = ET.fromstring(xml_text)
            for elem in root.iter():
                lname = _local_name(elem.tag)
                if lname in ("Media", "PTZ", "Events", "Imaging", "Device"):
                    for child in elem.iter():
                        if _local_name(child.tag) == "XAddr" and child.text:
                            rewritten = _rewrite_xaddr_host(child.text, camera_ip, port)
                            if lname == "Media":
                                self.media_xaddr = rewritten
                            elif lname == "PTZ":
                                self.ptz_xaddr = rewritten
                            elif lname == "Events":
                                self.events_xaddr = rewritten
                            elif lname == "Imaging":
                                self.imaging_xaddr = rewritten
        except ET.ParseError:
            pass

        # Also check GetServices for explicit service XAddrs
        services_body = (
            '<tds:GetServices>'
            '<tds:IncludeCapability>true</tds:IncludeCapability>'
            '</tds:GetServices>'
        )
        s_status, s_xml = send_onvif_soap(
            device_url,
            services_body,
            username=username,
            password=password,
            timeout=2.5,
            time_offset_seconds=self.time_offset_seconds,
        )
        if s_status == 200 and "<" in s_xml:
            try:
                s_root = ET.fromstring(s_xml)
                for svc in s_root.iter():
                    if _local_name(svc.tag) == "Service":
                        ns = ""
                        xaddr = ""
                        for child in svc:
                            cname = _local_name(child.tag)
                            if cname == "Namespace" and child.text:
                                ns = child.text.lower()
                            elif cname == "XAddr" and child.text:
                                xaddr = _rewrite_xaddr_host(child.text, camera_ip, port)
                        if xaddr:
                            if "media" in ns:
                                self.media_xaddr = xaddr
                            elif "ptz" in ns:
                                self.ptz_xaddr = xaddr
                            elif "event" in ns:
                                self.events_xaddr = xaddr
                            elif "imaging" in ns:
                                self.imaging_xaddr = xaddr
            except ET.ParseError:
                pass

        # Query GetDeviceInformation
        info_body = "<tds:GetDeviceInformation/>"
        i_status, i_xml = send_onvif_soap(
            device_url,
            info_body,
            username=username,
            password=password,
            timeout=2.5,
            time_offset_seconds=self.time_offset_seconds,
        )
        if i_status == 200 and "<" in i_xml:
            try:
                i_root = ET.fromstring(i_xml)
                for elem in i_root.iter():
                    lname = _local_name(elem.tag)
                    if lname in ("Manufacturer", "Model", "FirmwareVersion", "SerialNumber", "HardwareId") and elem.text:
                        self.device_info[lname] = elem.text.strip()
            except ET.ParseError:
                pass
            mfg_str = f"{self.device_info.get('Manufacturer', '')} {self.device_info.get('Model', '')}".lower()
            if "tp-link" in mfg_str or "tapo" in mfg_str or port == 2020:
                self.vendor_hint = "tapo"

        # Query Media GetProfiles to obtain ProfileToken & PTZ spaces
        profiles_body = "<trt:GetProfiles/>"
        p_status, p_xml = send_onvif_soap(
            self.media_xaddr,
            profiles_body,
            username=username,
            password=password,
            timeout=2.5,
            time_offset_seconds=self.time_offset_seconds,
        )
        if p_status != 200 or "Fault" in p_xml:
            for alt_path in ("/onvif/media_service", "/onvif/device_service", "/onvif/service"):
                alt_url = f"http://{camera_ip}:{port}{alt_path}"
                p_status, p_xml = send_onvif_soap(
                    alt_url,
                    profiles_body,
                    username=username,
                    password=password,
                    timeout=2.5,
                    time_offset_seconds=self.time_offset_seconds,
                )
                if p_status == 200 and "Profiles" in p_xml and "Fault" not in p_xml:
                    self.media_xaddr = alt_url
                    break

        if p_status != 200 or "Fault" in p_xml:
            if "NotAuthorized" in p_xml or "Sender" in p_xml or p_status in (401, 403):
                self.last_error = f"ONVIF authentication rejected on {camera_ip}:{port} (check camera username/password)"
            return False

        found_profile = None
        has_zoom_space = False
        has_abs_space = False
        has_rel_space = False
        has_cont_space = False

        try:
            p_root = ET.fromstring(p_xml)
            for elem in p_root.iter():
                if _local_name(elem.tag) == "Profiles":
                    token = elem.attrib.get("token")
                    if token and not found_profile:
                        found_profile = token
                    for sub in elem.iter():
                        sname = _local_name(sub.tag)
                        if sname in (
                            "ZoomLimits",
                            "ContinuousZoomVelocitySpace",
                            "RelativeZoomTranslationSpace",
                            "AbsoluteZoomPositionSpace",
                        ):
                            has_zoom_space = True
                        elif sname == "DefaultAbsolutePantTiltPositionSpace":
                            has_abs_space = True
                        elif sname == "DefaultRelativePanTiltTranslationSpace":
                            has_rel_space = True
                        elif sname == "DefaultContinuousPanTiltVelocitySpace":
                            has_cont_space = True
                    if found_profile:
                        break
        except ET.ParseError:
            pass

        self.profile_token = found_profile or "profile_1"
        self.has_zoom = has_zoom_space
        if has_abs_space or has_rel_space or has_cont_space:
            self.supports_absolute_move = has_abs_space
            self.supports_relative_move = has_rel_space or True
            self.supports_continuous_move = has_cont_space or True

        if self.ptz_xaddr.endswith("/onvif/device_service"):
            self.ptz_xaddr = f"http://{camera_ip}:{port}/onvif/service"

        return True

    def _connect_onvif_zeep(
        self, camera_ip: str, port: int, username: str, password: str
    ) -> bool:
        """Fallback connection via python `onvif-zeep` library if installed."""
        try:
            from onvif import ONVIFCamera

            self.onvif_device = ONVIFCamera(camera_ip, port, username, password)
            self.ptz_service = self.onvif_device.create_ptz_service()
            media_service = self.onvif_device.create_media_service()
            profiles = media_service.GetProfiles()
            if profiles:
                self.media_profile = profiles[0]
                self.profile_token = getattr(self.media_profile, "token", "profile_1")
                return True
        except Exception as e:
            logger.debug("onvif-zeep connect failed on %s:%s: %s", camera_ip, port, e)
        return False

    def _connect_vendor_http_fallback(
        self, camera_ip: str, port: int, username: str, password: str
    ) -> bool:
        """Attempt direct vendor HTTP CGI PTZ discovery for non-ONVIF or hybrid cameras."""
        if self.ptz_type in ("auto", "hikvision_isapi"):
            url = f"http://{camera_ip}:{port}/ISAPI/System/deviceInfo"
            status, body = send_http_or_soap_request(
                url, method="GET", username=username, password=password, timeout=2.0
            )
            if status == 200 and ("DeviceInfo" in body or "Hikvision" in body):
                self.port = port
                self.active_protocol = "hikvision_isapi"
                self.has_zoom = True
                return True

        if self.ptz_type in ("auto", "dahua_cgi"):
            url = f"http://{camera_ip}:{port}/cgi-bin/magicBox.cgi?action=getSystemInfo"
            status, body = send_http_or_soap_request(
                url, method="GET", username=username, password=password, timeout=2.0
            )
            if status == 200 and ("serialNumber" in body or "deviceType" in body):
                self.port = port
                self.active_protocol = "dahua_cgi"
                self.has_zoom = True
                return True

        if self.ptz_type in ("auto", "reolink_api"):
            url = f"http://{camera_ip}:80/cgi-bin/api.cgi?cmd=GetDevInfo&user={urllib.parse.quote(username)}&password={urllib.parse.quote(password)}"
            status, body = send_http_or_soap_request(url, method="GET", timeout=2.0)
            if status == 200 and '"cmd"' in body and '"GetDevInfo"' in body:
                self.port = 80
                self.active_protocol = "reolink_api"
                self.has_zoom = True
                return True

        if self.ptz_type in ("auto", "axis_vapix"):
            url = f"http://{camera_ip}:{port}/axis-cgi/com/ptz.cgi?query=position"
            status, body = send_http_or_soap_request(
                url, method="GET", username=username, password=password, timeout=2.0
            )
            if status == 200 and ("pan=" in body or "tilt=" in body):
                self.port = port
                self.active_protocol = "axis_vapix"
                self.has_zoom = True
                return True

        return False

    def disconnect(self):
        """Disconnect from PTZ camera"""
        self._cancel_pending_auto_stop()
        self.onvif_device = None
        self.ptz_service = None
        self.media_profile = None
        self.is_connected = False
        self.active_protocol = None

    def _send_ptz_soap(self, body_xml: str, soap_action: Optional[str] = None) -> Tuple[bool, str]:
        """
        Send an ONVIF PTZ SOAP command to `self.ptz_xaddr`, falling back across
        `/onvif/service`, `/onvif/ptz_service`, and `/onvif/device_service` if
        the initial endpoint rejects or 404s.
        """
        candidates = [self.ptz_xaddr]
        for path in ("/onvif/service", "/onvif/ptz_service", "/onvif/device_service"):
            alt = f"http://{self.camera_ip}:{self.port}{path}"
            if alt not in candidates:
                candidates.append(alt)

        last_resp = ""
        for target_url in candidates:
            if not target_url:
                continue
            status, resp_xml = send_onvif_soap(
                target_url,
                body_xml,
                username=self.username,
                password=self.password,
                soap_action=soap_action,
                timeout=2.5,
                time_offset_seconds=self.time_offset_seconds,
            )
            last_resp = resp_xml
            if status == 200 and "Fault" not in resp_xml:
                self.ptz_xaddr = target_url
                return True, resp_xml
        return False, last_resp

    async def move_absolute(
        self, pan: float, tilt: float, zoom: float = 0.0, speed: float = 0.8
    ) -> bool:
        """
        Move camera to absolute position (-1.0..1.0 for pan/tilt, 0.0..1.0 for zoom).
        Automatically falls back to `RelativeMove` if the camera only implements
        relative/continuous spaces (such as TP-Link Tapo C200/C210/C220).
        """
        if not self.is_connected:
            return False

        self._cancel_pending_auto_stop()
        pan = max(self.pan_min, min(self.pan_max, float(pan)))
        tilt = max(self.tilt_min, min(self.tilt_max, float(tilt)))
        zoom = max(self.zoom_min, min(self.zoom_max, float(zoom)))
        speed = max(0.2, min(1.0, float(speed)))

        if self.active_protocol == "onvif_soap" and self.supports_absolute_move:
            zoom_pos_xml = (
                f'<tt:Zoom x="{zoom:.3f}" space="http://www.onvif.org/ver10/tptz/ZoomSpaces/PositionGenericSpace"/>'
                if self.has_zoom
                else ""
            )
            body = (
                '<tptz:AbsoluteMove>'
                f'<tptz:ProfileToken>{self.profile_token}</tptz:ProfileToken>'
                '<tptz:Position>'
                f'<tt:PanTilt x="{pan:.3f}" y="{tilt:.3f}"/>'
                f'{zoom_pos_xml}'
                '</tptz:Position>'
                '</tptz:AbsoluteMove>'
            )
            ok, _ = await asyncio.to_thread(
                self._send_ptz_soap,
                body,
                "http://www.onvif.org/ver20/ptz/wsdl/AbsoluteMove",
            )
            if ok:
                self.current_position = {"pan": pan, "tilt": tilt, "zoom": zoom}
                return True

        pan_delta = max(-1.0, min(1.0, pan - self.current_position.get("pan", 0.0)))
        tilt_delta = max(-1.0, min(1.0, tilt - self.current_position.get("tilt", 0.0)))
        zoom_delta = max(-1.0, min(1.0, zoom - self.current_position.get("zoom", 0.0)))
        if abs(pan_delta) < 0.05 and abs(tilt_delta) < 0.05:
            pan_delta, tilt_delta = pan, tilt
        rel_ok = await self.move_relative(pan_delta, tilt_delta, zoom_delta, speed)
        if rel_ok:
            self.current_position = {"pan": pan, "tilt": tilt, "zoom": zoom}
        return rel_ok

    async def move_relative(
        self,
        pan_delta: float,
        tilt_delta: float,
        zoom_delta: float = 0.0,
        speed: float = 0.8,
    ) -> bool:
        """
        Move camera by a clearly visible step in the requested direction.

        Why this uses a dual strategy:
        - Many cameras (especially TP-Link Tapo, Reolink, and Amcrest) either
          ignore `<tptz:Speed>` inside `RelativeMove`, or treat small `x`/`y`
          fractions (< 0.25) as a 1-degree micro-step, while responding briskly
          to `ContinuousMove` at full motor velocity (`±1.0`) for a timed burst
          (`0.55s`–`0.95s`) or `RelativeMove` without `<tptz:Speed>`.
        - For Tapo cameras (or whenever `ContinuousMove` is supported), we issue
          a full-velocity `ContinuousMove` burst and schedule a non-blocking
          auto-stop task (`_schedule_auto_stop`), falling back to `RelativeMove`
          (without `<tptz:Speed>`) if `ContinuousMove` is rejected.
        """
        if not self.is_connected:
            return False

        pan_d = max(-1.0, min(1.0, float(pan_delta)))
        tilt_d = max(-1.0, min(1.0, float(tilt_delta)))
        zoom_d = max(-1.0, min(1.0, float(zoom_delta)))
        spd = max(0.25, min(1.0, float(speed)))

        # Ensure step translation is large enough to produce a crisp, immediate ~12-20 degree step
        step_pan = _boost_motor_velocity(pan_d, min_active=max(0.35, spd * 0.65))
        step_tilt = _boost_motor_velocity(tilt_d, min_active=max(0.35, spd * 0.65))
        burst_duration = 0.26 + (spd * 0.38)  # 0.35s at 25% speed -> 0.64s at 100% speed

        if self.active_protocol == "onvif_soap":
            # Strategy A (Primary for Tapo & velocity-driven stepper cameras):
            # Start full-velocity ContinuousMove and schedule non-blocking Stop
            if self.vendor_hint in ("tapo", "reolink", "dahua") or not self.supports_relative_move:
                cont_ok = await self.move_continuous(
                    pan_velocity=_boost_motor_velocity(pan_d, min_active=0.9),
                    tilt_velocity=_boost_motor_velocity(tilt_d, min_active=0.9),
                    zoom_velocity=zoom_d,
                    cancel_timer=True,
                )
                if cont_ok:
                    self._schedule_auto_stop(burst_duration)
                    self._update_cached_position(step_pan * 0.25, step_tilt * 0.25, zoom_d * 0.2)
                    return True

            # Strategy B: ONVIF RelativeMove WITHOUT <tptz:Speed> (maximizes firmware compatibility)
            include_zoom = self.has_zoom and abs(zoom_d) > 1e-4
            zoom_trans_xml = f'<tt:Zoom x="{zoom_d:.3f}"/>' if include_zoom else ""
            body_simple = (
                '<tptz:RelativeMove>'
                f'<tptz:ProfileToken>{self.profile_token}</tptz:ProfileToken>'
                '<tptz:Translation>'
                f'<tt:PanTilt x="{step_pan:.3f}" y="{step_tilt:.3f}"/>'
                f'{zoom_trans_xml}'
                '</tptz:Translation>'
                '</tptz:RelativeMove>'
            )
            ok, _ = await asyncio.to_thread(
                self._send_ptz_soap,
                body_simple,
                "http://www.onvif.org/ver20/ptz/wsdl/RelativeMove",
            )
            if ok:
                self._update_cached_position(step_pan * 0.25, step_tilt * 0.25, zoom_d * 0.2)
                return True

            # Strategy C: Fallback to timed ContinuousMove burst for any camera that rejected RelativeMove
            cont_ok = await self.move_continuous(
                pan_velocity=_boost_motor_velocity(pan_d, min_active=0.9),
                tilt_velocity=_boost_motor_velocity(tilt_d, min_active=0.9),
                zoom_velocity=zoom_d,
                cancel_timer=True,
            )
            if cont_ok:
                self._schedule_auto_stop(burst_duration)
                self._update_cached_position(step_pan * 0.25, step_tilt * 0.25, zoom_d * 0.2)
                return True
            return False

        if self.active_protocol == "onvif_zeep" and self.ptz_service:
            cont_ok = await self.move_continuous(
                _boost_motor_velocity(pan_d, min_active=0.85),
                _boost_motor_velocity(tilt_d, min_active=0.85),
                zoom_d,
            )
            if cont_ok:
                self._schedule_auto_stop(burst_duration)
                self._update_cached_position(step_pan * 0.25, step_tilt * 0.25, zoom_d * 0.2)
                return True
            return False

        # Vendor HTTP CGI burst
        cont_ok = await self.move_continuous(
            _boost_motor_velocity(pan_d, min_active=0.85),
            _boost_motor_velocity(tilt_d, min_active=0.85),
            zoom_d,
        )
        if cont_ok:
            self._schedule_auto_stop(burst_duration)
            self._update_cached_position(step_pan * 0.25, step_tilt * 0.25, zoom_d * 0.2)
            return True
        return False

    def _update_cached_position(
        self, pan_delta: float, tilt_delta: float, zoom_delta: float
    ) -> None:
        self.current_position["pan"] = max(
            self.pan_min,
            min(self.pan_max, self.current_position.get("pan", 0.0) + pan_delta),
        )
        self.current_position["tilt"] = max(
            self.tilt_min,
            min(self.tilt_max, self.current_position.get("tilt", 0.0) + tilt_delta),
        )
        self.current_position["zoom"] = max(
            self.zoom_min,
            min(self.zoom_max, self.current_position.get("zoom", 0.0) + zoom_delta),
        )

    async def move_continuous(
        self,
        pan_velocity: float,
        tilt_velocity: float,
        zoom_velocity: float = 0.0,
        cancel_timer: bool = True,
    ) -> bool:
        """
        Start continuous camera movement (-1.0..1.0 velocity).
        Boosts non-zero Pan/Tilt velocities above stepper motor deadzones (`>= 0.75`)
        and omits `<tt:Zoom>` when `self.has_zoom` is False or `zoom_velocity == 0`
        so Pan/Tilt-only cameras (such as TP-Link Tapo) move smoothly at full speed.
        """
        if not self.is_connected:
            return False

        if cancel_timer:
            self._cancel_pending_auto_stop()

        pan_v = _boost_motor_velocity(
            max(-1.0, min(1.0, float(pan_velocity))),
            min_active=0.85 if self.vendor_hint == "tapo" else 0.65,
        )
        tilt_v = _boost_motor_velocity(
            max(-1.0, min(1.0, float(tilt_velocity))),
            min_active=0.85 if self.vendor_hint == "tapo" else 0.65,
        )
        zoom_v = max(-1.0, min(1.0, float(zoom_velocity)))

        if self.active_protocol == "onvif_soap":
            include_zoom = self.has_zoom and abs(zoom_v) > 1e-4
            zoom_xml = (
                f'<tt:Zoom x="{zoom_v:.2f}" '
                'space="http://www.onvif.org/ver10/tptz/ZoomSpaces/VelocityGenericSpace"/>'
                if include_zoom
                else ""
            )
            body_clean = (
                '<tptz:ContinuousMove>'
                f'<tptz:ProfileToken>{self.profile_token}</tptz:ProfileToken>'
                '<tptz:Velocity>'
                f'<tt:PanTilt x="{pan_v:.2f}" y="{tilt_v:.2f}"/>'
                f'{zoom_xml}'
                '</tptz:Velocity>'
                '</tptz:ContinuousMove>'
            )
            body_with_space = (
                '<tptz:ContinuousMove>'
                f'<tptz:ProfileToken>{self.profile_token}</tptz:ProfileToken>'
                '<tptz:Velocity>'
                f'<tt:PanTilt x="{pan_v:.2f}" y="{tilt_v:.2f}" '
                'space="http://www.onvif.org/ver10/tptz/PanTiltSpaces/VelocityGenericSpace"/>'
                f'{zoom_xml}'
                '</tptz:Velocity>'
                '</tptz:ContinuousMove>'
            )

            if self._continuous_use_space_attr is True:
                ok2, _ = await asyncio.to_thread(
                    self._send_ptz_soap,
                    body_with_space,
                    "http://www.onvif.org/ver20/ptz/wsdl/ContinuousMove",
                )
                if ok2:
                    return True

            ok, _ = await asyncio.to_thread(
                self._send_ptz_soap,
                body_clean,
                "http://www.onvif.org/ver20/ptz/wsdl/ContinuousMove",
            )
            if ok:
                self._continuous_use_space_attr = False
                return True

            ok2, _ = await asyncio.to_thread(
                self._send_ptz_soap,
                body_with_space,
                "http://www.onvif.org/ver20/ptz/wsdl/ContinuousMove",
            )
            if ok2:
                self._continuous_use_space_attr = True
            return ok2

        if self.active_protocol == "onvif_zeep" and self.ptz_service:
            try:
                request = self.ptz_service.create_type("ContinuousMove")
                request.ProfileToken = self.media_profile.token
                vel: Dict[str, Any] = {"PanTilt": {"x": pan_v, "y": tilt_v}}
                if self.has_zoom and abs(zoom_v) > 1e-4:
                    vel["Zoom"] = {"x": zoom_v}
                request.Velocity = vel
                await asyncio.to_thread(self.ptz_service.ContinuousMove, request)
                return True
            except Exception as e:
                logger.debug("onvif-zeep ContinuousMove failed: %s", e)
                return False

        return await asyncio.to_thread(
            self._vendor_continuous_move, pan_v, tilt_v, zoom_v
        )

    def _vendor_continuous_move(
        self, pan_v: float, tilt_v: float, zoom_v: float
    ) -> bool:
        """Execute continuous PTZ move on Hikvision ISAPI, Dahua CGI, Reolink, or Axis."""
        if self.active_protocol == "hikvision_isapi":
            xml_body = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<PTZData>'
                f'<pan>{int(round(pan_v * 60))}</pan>'
                f'<tilt>{int(round(tilt_v * 60))}</tilt>'
                f'<zoom>{int(round(zoom_v * 60))}</zoom>'
                '</PTZData>'
            )
            url = f"http://{self.camera_ip}:{self.port}/ISAPI/PTZCtrl/channels/1/continuous"
            status, _ = send_http_or_soap_request(
                url, method="PUT", body=xml_body, username=self.username, password=self.password
            )
            return status in (200, 204)

        if self.active_protocol == "dahua_cgi":
            code = "Up"
            if abs(pan_v) > abs(tilt_v):
                code = "Right" if pan_v > 0 else "Left"
            elif tilt_v != 0:
                code = "Up" if tilt_v > 0 else "Down"
            elif zoom_v != 0:
                code = "ZoomTele" if zoom_v > 0 else "ZoomWide"
            spd = max(1, min(8, int(round(max(abs(pan_v), abs(tilt_v), abs(zoom_v), 0.5) * 8))))
            url = (
                f"http://{self.camera_ip}:{self.port}/cgi-bin/ptz.cgi"
                f"?action=start&channel=1&code={code}&arg1=0&arg2={spd}&arg3=0"
            )
            status, _ = send_http_or_soap_request(
                url, method="GET", username=self.username, password=self.password
            )
            return status == 200

        if self.active_protocol == "reolink_api":
            op = "Up"
            if abs(pan_v) > abs(tilt_v):
                op = "Right" if pan_v > 0 else "Left"
            elif tilt_v != 0:
                op = "Up" if tilt_v > 0 else "Down"
            elif zoom_v != 0:
                op = "ZoomInc" if zoom_v > 0 else "ZoomDec"
            spd = max(1, min(64, int(round(max(abs(pan_v), abs(tilt_v), 0.5) * 32))))
            payload = json.dumps(
                [{"cmd": "PtzCtrl", "action": 0, "param": {"channel": 0, "op": op, "speed": spd}}]
            )
            url = (
                f"http://{self.camera_ip}:{self.port}/cgi-bin/api.cgi"
                f"?cmd=PtzCtrl&user={urllib.parse.quote(self.username)}&password={urllib.parse.quote(self.password)}"
            )
            status, _ = send_http_or_soap_request(url, method="POST", body=payload)
            return status == 200

        if self.active_protocol == "axis_vapix":
            url = (
                f"http://{self.camera_ip}:{self.port}/axis-cgi/com/ptz.cgi"
                f"?continuouspantiltmove={int(round(pan_v * 50))},{int(round(tilt_v * 50))}"
            )
            status, _ = send_http_or_soap_request(
                url, method="GET", username=self.username, password=self.password
            )
            return status in (200, 204)

        return False

    async def stop(self, cancel_timer: bool = True) -> bool:
        """Stop all camera movement safely across ONVIF and vendor protocols."""
        if cancel_timer:
            self._cancel_pending_auto_stop()

        if not self.is_connected:
            return False

        if self.active_protocol == "onvif_soap":
            zoom_stop = (
                "<tptz:Zoom>true</tptz:Zoom>"
                if self.has_zoom
                else "<tptz:Zoom>false</tptz:Zoom>"
            )
            body = (
                '<tptz:Stop>'
                f'<tptz:ProfileToken>{self.profile_token}</tptz:ProfileToken>'
                '<tptz:PanTilt>true</tptz:PanTilt>'
                f'{zoom_stop}'
                '</tptz:Stop>'
            )
            ok, _ = await asyncio.to_thread(
                self._send_ptz_soap,
                body,
                "http://www.onvif.org/ver20/ptz/wsdl/Stop",
            )
            return ok

        if self.active_protocol == "onvif_zeep" and self.ptz_service:
            try:
                request = self.ptz_service.create_type("Stop")
                request.ProfileToken = self.media_profile.token
                request.PanTilt = True
                request.Zoom = bool(self.has_zoom)
                await asyncio.to_thread(self.ptz_service.Stop, request)
                return True
            except Exception as e:
                logger.debug("onvif-zeep Stop failed: %s", e)
                return False

        return await asyncio.to_thread(self._vendor_stop)

    def _vendor_stop(self) -> bool:
        if self.active_protocol == "hikvision_isapi":
            xml_body = '<?xml version="1.0" encoding="UTF-8"?><PTZData><pan>0</pan><tilt>0</tilt><zoom>0</zoom></PTZData>'
            url = f"http://{self.camera_ip}:{self.port}/ISAPI/PTZCtrl/channels/1/continuous"
            status, _ = send_http_or_soap_request(
                url, method="PUT", body=xml_body, username=self.username, password=self.password
            )
            return status in (200, 204)

        if self.active_protocol == "dahua_cgi":
            url = f"http://{self.camera_ip}:{self.port}/cgi-bin/ptz.cgi?action=stop&channel=1&code=Up&arg1=0&arg2=0&arg3=0"
            status, _ = send_http_or_soap_request(
                url, method="GET", username=self.username, password=self.password
            )
            return status == 200

        if self.active_protocol == "reolink_api":
            payload = json.dumps([{"cmd": "PtzCtrl", "action": 0, "param": {"channel": 0, "op": "Stop"}}])
            url = (
                f"http://{self.camera_ip}:{self.port}/cgi-bin/api.cgi"
                f"?cmd=PtzCtrl&user={urllib.parse.quote(self.username)}&password={urllib.parse.quote(self.password)}"
            )
            status, _ = send_http_or_soap_request(url, method="POST", body=payload)
            return status == 200

        if self.active_protocol == "axis_vapix":
            url = f"http://{self.camera_ip}:{self.port}/axis-cgi/com/ptz.cgi?continuouspantiltmove=0,0"
            status, _ = send_http_or_soap_request(
                url, method="GET", username=self.username, password=self.password
            )
            return status in (200, 204)

        return False

    async def goto_home(self, speed: float = 0.8) -> bool:
        """Move camera to its Home position (with fallback to preset 1 or center (0,0))."""
        if not self.is_connected:
            return False

        self._cancel_pending_auto_stop()
        if self.active_protocol == "onvif_soap":
            body = (
                '<tptz:GotoHomePosition>'
                f'<tptz:ProfileToken>{self.profile_token}</tptz:ProfileToken>'
                '</tptz:GotoHomePosition>'
            )
            ok, _ = await asyncio.to_thread(
                self._send_ptz_soap,
                body,
                "http://www.onvif.org/ver20/ptz/wsdl/GotoHomePosition",
            )
            if ok:
                self.current_position = {"pan": 0.0, "tilt": 0.0, "zoom": 0.0}
                return True

        return await self.move_absolute(0.0, 0.0, 0.0, speed=speed)

    async def goto_preset(self, preset_number: int, speed: float = 0.8) -> bool:
        """Move camera to saved preset position (1-255)."""
        if not self.is_connected:
            return False

        self._cancel_pending_auto_stop()
        if self.active_protocol == "onvif_soap":
            body = (
                '<tptz:GotoPreset>'
                f'<tptz:ProfileToken>{self.profile_token}</tptz:ProfileToken>'
                f'<tptz:PresetToken>{preset_number}</tptz:PresetToken>'
                '</tptz:GotoPreset>'
            )
            ok, _ = await asyncio.to_thread(
                self._send_ptz_soap,
                body,
                "http://www.onvif.org/ver20/ptz/wsdl/GotoPreset",
            )
            return ok

        if self.active_protocol == "onvif_zeep" and self.ptz_service:
            try:
                request = self.ptz_service.create_type("GotoPreset")
                request.ProfileToken = self.media_profile.token
                request.PresetToken = str(preset_number)
                await asyncio.to_thread(self.ptz_service.GotoPreset, request)
                return True
            except Exception as e:
                logger.debug("onvif-zeep GotoPreset failed: %s", e)
                return False

        if self.active_protocol == "hikvision_isapi":
            url = f"http://{self.camera_ip}:{self.port}/ISAPI/PTZCtrl/channels/1/presets/{preset_number}/goto"
            status, _ = await asyncio.to_thread(
                send_http_or_soap_request,
                url,
                "PUT",
                None,
                None,
                self.username,
                self.password,
            )
            return status in (200, 204)

        if self.active_protocol == "dahua_cgi":
            url = f"http://{self.camera_ip}:{self.port}/cgi-bin/ptz.cgi?action=start&channel=1&code=GotoPreset&arg1=0&arg2={preset_number}&arg3=0"
            status, _ = await asyncio.to_thread(
                send_http_or_soap_request,
                url,
                "GET",
                None,
                None,
                self.username,
                self.password,
            )
            return status == 200

        return False

    async def set_preset(self, preset_number: int, preset_name: str = "") -> bool:
        """Save current position as preset on the camera hardware."""
        if not self.is_connected:
            return False

        safe_name = (
            (preset_name or f"Preset_{preset_number}")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        if self.active_protocol == "onvif_soap":
            body = (
                '<tptz:SetPreset>'
                f'<tptz:ProfileToken>{self.profile_token}</tptz:ProfileToken>'
                f'<tptz:PresetName>{safe_name}</tptz:PresetName>'
                f'<tptz:PresetToken>{preset_number}</tptz:PresetToken>'
                '</tptz:SetPreset>'
            )
            ok, _ = await asyncio.to_thread(
                self._send_ptz_soap,
                body,
                "http://www.onvif.org/ver20/ptz/wsdl/SetPreset",
            )
            return ok

        if self.active_protocol == "onvif_zeep" and self.ptz_service:
            try:
                request = self.ptz_service.create_type("SetPreset")
                request.ProfileToken = self.media_profile.token
                request.PresetToken = str(preset_number)
                if preset_name:
                    request.PresetName = preset_name
                await asyncio.to_thread(self.ptz_service.SetPreset, request)
                return True
            except Exception as e:
                logger.debug("onvif-zeep SetPreset failed: %s", e)
                return False

        return True

    async def get_hardware_presets(self) -> List[Dict[str, Any]]:
        """Query presets stored directly on the camera hardware via ONVIF GetPresets."""
        if not self.is_connected or self.active_protocol != "onvif_soap":
            return []

        body = (
            '<tptz:GetPresets>'
            f'<tptz:ProfileToken>{self.profile_token}</tptz:ProfileToken>'
            '</tptz:GetPresets>'
        )
        ok, xml_text = await asyncio.to_thread(
            self._send_ptz_soap,
            body,
            "http://www.onvif.org/ver20/ptz/wsdl/GetPresets",
        )
        if not ok or "<" not in xml_text:
            return []

        presets: List[Dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
            for idx, elem in enumerate(root.iter(), start=1):
                if _local_name(elem.tag) == "Preset":
                    token = elem.attrib.get("token", str(idx))
                    name = f"Preset {token}"
                    pan, tilt, zoom = 0.0, 0.0, 0.0
                    for child in elem.iter():
                        cname = _local_name(child.tag)
                        if cname == "Name" and child.text:
                            name = child.text.strip()
                        elif cname == "PanTilt":
                            try:
                                pan = float(child.attrib.get("x", 0.0))
                                tilt = float(child.attrib.get("y", 0.0))
                            except ValueError:
                                pass
                        elif cname == "Zoom":
                            try:
                                zoom = float(child.attrib.get("x", 0.0))
                            except ValueError:
                                pass
                    try:
                        num = int(re.sub(r"\D+", "", str(token)) or len(presets) + 1)
                    except ValueError:
                        num = len(presets) + 1
                    presets.append(
                        {
                            "preset_token": str(token),
                            "preset_number": max(1, min(255, num)),
                            "name": name,
                            "pan": pan,
                            "tilt": tilt,
                            "zoom": zoom,
                        }
                    )
        except ET.ParseError:
            pass
        return presets

    async def get_status(self) -> Optional[Dict[str, Any]]:
        """Get current PTZ status including position and discovered capabilities."""
        if not self.is_connected:
            return None

        if self.active_protocol == "onvif_soap":
            body = (
                '<tptz:GetStatus>'
                f'<tptz:ProfileToken>{self.profile_token}</tptz:ProfileToken>'
                '</tptz:GetStatus>'
            )
            ok, xml_text = await asyncio.to_thread(
                self._send_ptz_soap,
                body,
                "http://www.onvif.org/ver20/ptz/wsdl/GetStatus",
            )
            if ok and "<" in xml_text:
                try:
                    root = ET.fromstring(xml_text)
                    for elem in root.iter():
                        lname = _local_name(elem.tag)
                        if lname == "PanTilt":
                            self.current_position["pan"] = float(
                                elem.attrib.get("x", self.current_position["pan"])
                            )
                            self.current_position["tilt"] = float(
                                elem.attrib.get("y", self.current_position["tilt"])
                            )
                        elif lname == "Zoom":
                            self.current_position["zoom"] = float(
                                elem.attrib.get("x", self.current_position["zoom"])
                            )
                except Exception:
                    pass

        return {
            "pan": self.current_position.get("pan", 0.0),
            "tilt": self.current_position.get("tilt", 0.0),
            "zoom": self.current_position.get("zoom", 0.0),
            "moving": False,
            "protocol": self.active_protocol,
            "camera_ip": self.camera_ip,
            "port": self.port,
            "vendor_hint": self.vendor_hint,
            "device_info": self.device_info,
            "capabilities": {
                "pan_tilt": self.has_pan_tilt,
                "zoom": self.has_zoom,
                "continuous_move": self.supports_continuous_move,
                "relative_move": self.supports_relative_move,
                "absolute_move": self.supports_absolute_move,
                "home_position": self.supports_home_position,
                "presets": self.supports_presets,
            },
        }


# Global registry of PTZ controllers
_ptz_controllers: Dict[str, PTZController] = {}


def get_ptz_controller(camera_id: str, ptz_type: str = "auto") -> PTZController:
    """Get or create PTZ controller for a camera."""
    if camera_id not in _ptz_controllers:
        _ptz_controllers[camera_id] = PTZController(camera_id, ptz_type)
    elif ptz_type and ptz_type != "auto":
        _ptz_controllers[camera_id].ptz_type = ptz_type
    return _ptz_controllers[camera_id]


def remove_ptz_controller(camera_id: str):
    """Remove PTZ controller from registry."""
    if camera_id in _ptz_controllers:
        controller = _ptz_controllers[camera_id]
        controller.disconnect()
        del _ptz_controllers[camera_id]
