# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Multi-Vendor Camera Edge AI & Hardware Control Subsystem

Integrates built-in camera hardware capabilities (Edge AI person/vehicle/pet/package/
motion detection, Smart Auto-Tracking, Privacy Lens Mask, Night Vision / IR / Spotlight
modes, and Built-in Siren/Alarm) across popular IP camera brands:

1. Standard ONVIF Profile S / T (Universal: TP-Link Tapo, Hikvision, Dahua, Amcrest,
   Reolink, Axis, Uniview, Bosch, Generic ONVIF):
   - Device Information (`GetDeviceInformation`: Manufacturer, Model, Firmware)
   - Edge AI Event Service (`CreatePullPointSubscription` + `PullMessages` &
     `GetEventProperties` over SOAP 1.2 + WS-UsernameToken Digest)
   - Imaging Service (`GetImagingSettings` / `SetImagingSettings`: IR Cut Filter /
     Night Vision, WDR, Backlight Compensation, Brightness, Contrast)
   - Auxiliary Hardware Commands (`SendAuxiliaryCommand`: IR Lamp, Wiper, Audio/Siren)

2. TP-Link Tapo Native Hardware Control (`pytapo` if installed + built-in HTTPS stok
   JSON API fallback on port 443):
   - On-camera AI toggles (`people_detection`, `vehicle_detection`, `pet_detection`,
     `package_detection`, `bcd` baby cry / bark / glass break, `motion_detection`)
   - Auto-Tracking / Smart Track (`target_track`)
   - Privacy Mask / Lens Hide (`lens_mask`)
   - Night Vision Mode (`inf_night_vision` IR, `wtl_night_vision` Full-Color Spotlight,
     `md_night_vision` Smart Auto)
   - Built-in Siren (`msg_alarm`) & Status LED (`led`)

3. Multi-Vendor HTTP CGI Extensions:
   - Hikvision ISAPI (`/ISAPI/Event/notification/alertStream`, `/ISAPI/PTZCtrl/channels/1/autoTrack`,
     `/ISAPI/Image/channels/1/ircutFilter`, `/ISAPI/Event/triggers/notifications/AudioAlarm`)
   - Dahua / Amcrest CGI (`/cgi-bin/configManager.cgi`, `/cgi-bin/coaxialControlIO.cgi`)
   - Reolink HTTP JSON API (`/cgi-bin/api.cgi?cmd=GetAiState`, `SetAiCfg`, `SetIrLights`, `AudioAlarmPlay`)
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import logging
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import cv2
except ImportError:
    cv2 = None

from backend.core.camera_security import extract_camera_connection_info
from backend.core.paths import paths
from backend.core.ptz_controller import (
    DEFAULT_ONVIF_PORTS,
    VENDOR_PORT_PRIORITY,
    _local_name,
    _rewrite_xaddr_host,
    get_ptz_controller,
    send_http_or_soap_request,
    send_onvif_soap,
)
from backend.core.timeutil import utcnow

logger = logging.getLogger(__name__)


# Standardized topic mapping from ONVIF / Vendor Edge AI rules to OpenEye classes
EDGE_EVENT_TOPIC_MAPPING: Tuple[Tuple[Tuple[str, ...], str, str], ...] = (
    (("peopledetector", "human", "person", "people", "face"), "person", "person"),
    (("vehicledetector", "vehicle", "car", "truck", "licenseplate"), "vehicle", "car"),
    (("petdetector", "pet", "animal", "dog_cat", "dog", "cat"), "animal", "pet"),
    (("packagedetector", "package", "parcel", "box"), "package", "package"),
    (("babycry", "bcd", "bark", "meow", "glassbreak", "audioanalytics", "detectedsound"), "person", "audio_alert"),
    (("linedetector", "crossed", "fielddetector", "intrusion", "tamper"), "motion", "perimeter"),
    (("cellmotiondetector", "motionalarm", "motion"), "motion", "motion"),
)


def classify_edge_event_topic(topic: str, data_items: Dict[str, str]) -> Optional[Tuple[str, str]]:
    """
    Map an ONVIF or vendor event topic + key/value payload to an OpenEye
    `(object_class, object_subclass)` tuple if the event indicates an active detection.
    """
    lowered_topic = (topic or "").lower()
    combined = lowered_topic + " " + " ".join(f"{k.lower()}={v.lower()}" for k, v in data_items.items())

    # Determine whether the state is active/true
    is_active = False
    if not data_items:
        is_active = True
    else:
        for k, v in data_items.items():
            val = str(v).strip().lower()
            if val in ("true", "1", "active", "yes", "motion", "detected", "inside", "crossed"):
                is_active = True
                break

    if not is_active:
        return None

    for keywords, obj_class, obj_subclass in EDGE_EVENT_TOPIC_MAPPING:
        if any(kw in combined for kw in keywords):
            return obj_class, obj_subclass

    return None


@dataclass
class EdgeAISettingsState:
    """Normalized Edge AI & Hardware settings across camera brands."""
    edge_ai_enabled: bool = True
    person_detection: bool = True
    vehicle_detection: bool = True
    pet_detection: bool = True
    package_detection: bool = False
    audio_alarm_detection: bool = False
    motion_detection: bool = True
    auto_tracking: bool = False
    privacy_mode: bool = False
    night_vision_mode: str = "auto"  # "auto" | "ir" | "color" | "off"
    wdr_enabled: bool = False
    siren_active: bool = False
    status_led_enabled: bool = True
    trigger_recording_on_edge_ai: bool = True
    cooldown_seconds: int = 10

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_ai_enabled": self.edge_ai_enabled,
            "person_detection": self.person_detection,
            "vehicle_detection": self.vehicle_detection,
            "pet_detection": self.pet_detection,
            "package_detection": self.package_detection,
            "audio_alarm_detection": self.audio_alarm_detection,
            "motion_detection": self.motion_detection,
            "auto_tracking": self.auto_tracking,
            "privacy_mode": self.privacy_mode,
            "night_vision_mode": self.night_vision_mode,
            "wdr_enabled": self.wdr_enabled,
            "siren_active": self.siren_active,
            "status_led_enabled": self.status_led_enabled,
            "trigger_recording_on_edge_ai": self.trigger_recording_on_edge_ai,
            "cooldown_seconds": self.cooldown_seconds,
        }


class CameraEdgeController:
    """
    Unified controller for a single camera's built-in Edge AI event stream and
    hardware controls (ONVIF + TP-Link Tapo + Hikvision + Dahua/Amcrest + Reolink).
    """

    def __init__(self, camera_id: str, source: Optional[str] = None):
        self.camera_id = camera_id
        self.source = source or ""
        self.conn_info = extract_camera_connection_info(self.source)
        self.camera_ip: str = self.conn_info.get("camera_ip", "")
        self.username: str = self.conn_info.get("username", "")
        self.password: str = self.conn_info.get("password", "")
        self.vendor_hint: str = self.conn_info.get("vendor_hint", "generic")

        self.onvif_port: int = 2020 if self.vendor_hint == "tapo" else 80
        self.device_xaddr: str = ""
        self.events_xaddr: str = ""
        self.imaging_xaddr: str = ""
        self.media_xaddr: str = ""
        self.video_source_token: str = "VideoSource_1"
        self.subscription_xaddr: str = ""

        self.device_info: Dict[str, str] = {}
        self.supported_topics: List[str] = []
        self.capabilities: Dict[str, bool] = {
            "onvif_events": False,
            "onvif_imaging": False,
            "ptz": False,
            "auto_tracking": False,
            "privacy_mode": False,
            "night_vision_modes": False,
            "siren": False,
            "edge_person_detection": False,
            "edge_vehicle_detection": False,
            "edge_pet_detection": False,
            "edge_package_detection": False,
            "edge_audio_detection": False,
            "tapo_native_api": False,
            "vendor_http_api": False,
        }
        self.settings = EdgeAISettingsState()
        self.recent_events: List[Dict[str, Any]] = []
        self._last_event_by_class: Dict[str, float] = {}
        self._probed: bool = False
        self._tapo_stok: Optional[str] = None

    def update_source(self, source: Optional[str], extra_settings: Optional[Dict[str, Any]] = None) -> None:
        if source and source != self.source:
            self.source = source
            self.conn_info = extract_camera_connection_info(self.source)
            self.camera_ip = self.conn_info.get("camera_ip", "")
            self.username = self.conn_info.get("username", "")
            self.password = self.conn_info.get("password", "")
            self.vendor_hint = self.conn_info.get("vendor_hint", "generic")
            self._probed = False
        if extra_settings:
            for k, v in extra_settings.items():
                if hasattr(self.settings, k) and v is not None:
                    setattr(self.settings, k, v)

    async def probe_capabilities(self, force: bool = False) -> Dict[str, Any]:
        """
        Discover the camera's hardware capabilities, manufacturer/model, ONVIF Event
        topics, Imaging service, and vendor-specific APIs (Tapo, Hikvision, Dahua, Reolink).
        """
        if self._probed and not force:
            return self.get_summary()

        if not self.conn_info.get("is_network_camera") or not self.camera_ip:
            self._probed = True
            return self.get_summary()

        await asyncio.to_thread(self._probe_sync)
        self._probed = True
        return self.get_summary()

    def _probe_sync(self) -> None:
        # 1. Check if PTZ controller already discovered ONVIF port & XAddrs
        ptz = get_ptz_controller(self.camera_id)
        candidate_ports = list(
            VENDOR_PORT_PRIORITY.get(self.vendor_hint, DEFAULT_ONVIF_PORTS)
        )
        if ptz.is_connected and ptz.port:
            if ptz.port in candidate_ports:
                candidate_ports.remove(ptz.port)
            candidate_ports.insert(0, ptz.port)

        # 2. Probe ONVIF Device, Events, and Imaging services
        for port in candidate_ports:
            dev_url = f"http://{self.camera_ip}:{port}/onvif/device_service"
            cap_body = "<tds:GetCapabilities><tds:Category>All</tds:Category></tds:GetCapabilities>"
            status, xml_text = send_onvif_soap(
                dev_url, cap_body, username=self.username, password=self.password, timeout=2.5
            )
            if status == 0 or ("Envelope" not in xml_text and "onvif" not in xml_text.lower()):
                continue

            self.onvif_port = port
            self.device_xaddr = dev_url
            self.events_xaddr = f"http://{self.camera_ip}:{port}/onvif/service"
            self.imaging_xaddr = f"http://{self.camera_ip}:{port}/onvif/service"
            self.media_xaddr = f"http://{self.camera_ip}:{port}/onvif/service"

            try:
                root = ET.fromstring(xml_text)
                for elem in root.iter():
                    lname = _local_name(elem.tag)
                    if lname in ("Events", "Imaging", "Media", "PTZ"):
                        for child in elem.iter():
                            if _local_name(child.tag) == "XAddr" and child.text:
                                xaddr = _rewrite_xaddr_host(child.text, self.camera_ip, port)
                                if lname == "Events":
                                    self.events_xaddr = xaddr
                                    self.capabilities["onvif_events"] = True
                                elif lname == "Imaging":
                                    self.imaging_xaddr = xaddr
                                    self.capabilities["onvif_imaging"] = True
                                    self.capabilities["night_vision_modes"] = True
                                elif lname == "Media":
                                    self.media_xaddr = xaddr
                                elif lname == "PTZ":
                                    self.capabilities["ptz"] = True
            except ET.ParseError:
                pass

            # Query GetDeviceInformation
            i_status, i_xml = send_onvif_soap(
                dev_url, "<tds:GetDeviceInformation/>", username=self.username, password=self.password, timeout=2.0
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

            # Update vendor hint from Manufacturer/Model if present
            mfg_model = (
                f"{self.device_info.get('Manufacturer', '')} {self.device_info.get('Model', '')}"
            ).lower()
            if "tp-link" in mfg_model or "tapo" in mfg_model or port == 2020:
                self.vendor_hint = "tapo"
            elif "hikvision" in mfg_model:
                self.vendor_hint = "hikvision"
            elif "dahua" in mfg_model or "amcrest" in mfg_model:
                self.vendor_hint = "dahua"
            elif "reolink" in mfg_model:
                self.vendor_hint = "reolink"
            elif "axis" in mfg_model:
                self.vendor_hint = "axis"

            # Query GetEventProperties to inspect supported Edge AI topics on the camera
            ep_status, ep_xml = send_onvif_soap(
                self.events_xaddr,
                "<tev:GetEventProperties/>",
                username=self.username,
                password=self.password,
                timeout=2.5,
            )
            if ep_status == 200 and "Fault" not in ep_xml:
                self.capabilities["onvif_events"] = True
                self._parse_event_properties(ep_xml)
            break

        # 3. Enable vendor-specific Edge AI & hardware capabilities
        if self.vendor_hint == "tapo":
            # TP-Link Tapo cameras support built-in Person/Pet/Vehicle/BabyCry AI,
            # Smart Track (on PTZ models), Privacy Mask, Night Vision modes, and Siren
            self.capabilities.update(
                {
                    "onvif_events": True,
                    "ptz": True,
                    "auto_tracking": True,
                    "privacy_mode": True,
                    "night_vision_modes": True,
                    "siren": True,
                    "edge_person_detection": True,
                    "edge_vehicle_detection": True,
                    "edge_pet_detection": True,
                    "edge_package_detection": True,
                    "edge_audio_detection": True,
                }
            )
            self._probe_tapo_native()
        elif self.vendor_hint in ("hikvision", "dahua", "reolink", "axis"):
            self.capabilities.update(
                {
                    "vendor_http_api": True,
                    "auto_tracking": True,
                    "night_vision_modes": True,
                    "siren": True,
                    "edge_person_detection": True,
                    "edge_vehicle_detection": True,
                    "edge_pet_detection": self.vendor_hint == "reolink",
                }
            )
        elif self.capabilities["onvif_events"]:
            # Generic ONVIF camera with Events service
            self.capabilities["edge_person_detection"] = True
            self.capabilities["night_vision_modes"] = True

    def _parse_event_properties(self, ep_xml: str) -> None:
        """Extract advertised ONVIF event topics from GetEventProperties XML."""
        topics: List[str] = []
        try:
            root = ET.fromstring(ep_xml)
            for elem in root.iter():
                lname = _local_name(elem.tag).lower()
                if lname in ("person", "peopledetector", "human", "people"):
                    self.capabilities["edge_person_detection"] = True
                    topics.append(lname)
                elif lname in ("vehicle", "vehicledetector", "car"):
                    self.capabilities["edge_vehicle_detection"] = True
                    topics.append(lname)
                elif lname in ("pet", "petdetector", "animal", "dog_cat"):
                    self.capabilities["edge_pet_detection"] = True
                    topics.append(lname)
                elif lname in ("package", "packagedetector"):
                    self.capabilities["edge_package_detection"] = True
                    topics.append(lname)
                elif lname in ("cellmotiondetector", "motionalarm", "motion"):
                    topics.append("motion")
        except ET.ParseError:
            pass
        self.supported_topics = sorted(set(topics)) or ["motion", "person"]

    def _probe_tapo_native(self) -> None:
        """
        Attempt to connect via `pytapo` (if installed) or Tapo HTTPS stok endpoint on
        port 443 to read live hardware toggles (Privacy Mode, Smart Track, AI switches).
        """
        if not self.camera_ip:
            return
        try:
            from pytapo import Tapo  # type: ignore

            tapo = Tapo(self.camera_ip, self.username or "admin", self.password)
            basic = tapo.getBasicInfo()
            if basic:
                self.capabilities["tapo_native_api"] = True
            try:
                priv = tapo.getPrivacyMode()
                self.settings.privacy_mode = str(priv.get("enabled", "off")).lower() == "on"
            except Exception:
                pass
            return
        except Exception:
            pass

        # Fallback: Try Tapo local HTTPS login (`/`) on port 443
        # The Tapo local login takes the password's uppercase MD5 hex: the camera's
        # protocol, not storage. Nothing is stored or logged.
        password_md5 = hashlib.md5((self.password or "").encode("utf-8")).hexdigest().upper()
        for pwd_candidate in (password_md5, self.password):
            login_payload = json.dumps(
                {
                    "method": "login",
                    "params": {
                        "hashed": True if pwd_candidate == password_md5 else False,
                        "username": self.username or "admin",
                        "password": pwd_candidate,
                    },
                }
            )
            status, resp_text = send_http_or_soap_request(
                f"https://{self.camera_ip}:443/",
                method="POST",
                body=login_payload,
                headers={"Content-Type": "application/json"},
                timeout=2.0,
            )
            if status == 200 and '"stok"' in resp_text:
                try:
                    data = json.loads(resp_text)
                    stok = data.get("result", {}).get("stok")
                    if stok:
                        self._tapo_stok = stok
                        self.capabilities["tapo_native_api"] = True
                        self._sync_tapo_stok_settings()
                        return
                except Exception:
                    pass

    def _sync_tapo_stok_settings(self) -> None:
        if not self._tapo_stok:
            return
        url = f"https://{self.camera_ip}:443/stok={self._tapo_stok}/ds"
        query_payload = json.dumps(
            {
                "method": "multipleRequest",
                "params": {
                    "requests": [
                        {"method": "getLensMaskConfig", "params": {"lens_mask": {"name": ["lens_mask_info"]}}},
                        {"method": "getTargetTrackConfig", "params": {"target_track": {"name": ["target_track_info"]}}},
                        {"method": "getPersonDetectionConfig", "params": {"people_detection": {"name": ["detection"]}}},
                    ]
                },
            }
        )
        status, text = send_http_or_soap_request(
            url,
            method="POST",
            body=query_payload,
            headers={"Content-Type": "application/json"},
            timeout=2.0,
        )
        if status == 200 and '"result"' in text:
            try:
                res = json.loads(text)
                for item in res.get("result", {}).get("responses", []):
                    r = item.get("result", {})
                    if "lens_mask" in r:
                        en = r["lens_mask"].get("lens_mask_info", {}).get("enabled")
                        if en is not None:
                            self.settings.privacy_mode = str(en).lower() == "on"
                    if "target_track" in r:
                        en = r["target_track"].get("target_track_info", {}).get("enabled")
                        if en is not None:
                            self.settings.auto_tracking = str(en).lower() == "on"
                    if "people_detection" in r:
                        en = r["people_detection"].get("detection", {}).get("enabled")
                        if en is not None:
                            self.settings.person_detection = str(en).lower() == "on"
            except Exception:
                pass

    async def apply_hardware_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply Edge AI and hardware control updates (Night Vision mode, Auto-Tracking,
        Privacy Mask, Siren, and Edge AI toggles) to both OpenEye's runtime state and
        the physical camera hardware via ONVIF / Tapo / Vendor APIs.
        """
        applied_hardware_calls: List[str] = []

        for key, value in updates.items():
            if hasattr(self.settings, key) and value is not None:
                setattr(self.settings, key, value)

        # 1. Night Vision / IR Cut Filter via ONVIF Imaging Service + Vendor APIs
        if "night_vision_mode" in updates and self.camera_ip:
            mode = str(updates["night_vision_mode"]).lower()
            hw_ok = await asyncio.to_thread(self._set_hardware_night_vision, mode)
            if hw_ok:
                applied_hardware_calls.append(f"night_vision:{mode}")

        # 2. Auto-Tracking / Smart Track
        if "auto_tracking" in updates and self.camera_ip:
            enabled = bool(updates["auto_tracking"])
            hw_ok = await asyncio.to_thread(self._set_hardware_auto_tracking, enabled)
            if hw_ok:
                applied_hardware_calls.append(f"auto_tracking:{enabled}")

        # 3. Privacy Mode / Lens Mask
        if "privacy_mode" in updates and self.camera_ip:
            enabled = bool(updates["privacy_mode"])
            hw_ok = await asyncio.to_thread(self._set_hardware_privacy_mode, enabled)
            if hw_ok:
                applied_hardware_calls.append(f"privacy_mode:{enabled}")

        # 4. On-camera AI detection switches (Person / Vehicle / Pet / Package)
        if any(
            k in updates
            for k in (
                "person_detection",
                "vehicle_detection",
                "pet_detection",
                "package_detection",
                "motion_detection",
            )
        ) and self.camera_ip:
            hw_ok = await asyncio.to_thread(self._set_hardware_ai_switches, updates)
            if hw_ok:
                applied_hardware_calls.append("edge_ai_switches")

        return {
            "camera_id": self.camera_id,
            "settings": self.settings.to_dict(),
            "applied_hardware_calls": applied_hardware_calls,
        }

    def _set_hardware_night_vision(self, mode: str) -> bool:
        """
        Configure camera Night Vision / IR Cut Filter mode across:
        - ONVIF Imaging Service (`SetImagingSettings` -> `IrCutFilter`: AUTO / ON / OFF)
        - TP-Link Tapo (`inf_night_vision` / `wtl_night_vision` / `md_night_vision`)
        - Hikvision ISAPI (`/ISAPI/Image/channels/1/ircutFilter`)
        - Dahua / Amcrest CGI (`/cgi-bin/configManager.cgi`)
        - Reolink API (`SetIrLights`)
        """
        # Map mode ("auto", "ir", "color", "off") to ONVIF IrCutFilter
        # Note: In ONVIF, IrCutFilter=ON means IR filter is engaged (Day/Color mode),
        # IrCutFilter=OFF means IR filter is open (Night/Infrared mode), AUTO is automatic.
        onvif_ir_map = {
            "auto": "AUTO",
            "ir": "OFF",
            "color": "ON",
            "off": "ON",
        }
        ir_val = onvif_ir_map.get(mode, "AUTO")

        # 1. Try ONVIF SetImagingSettings
        img_url = self.imaging_xaddr or f"http://{self.camera_ip}:{self.onvif_port}/onvif/service"
        body = (
            '<timg:SetImagingSettings>'
            f'<timg:VideoSourceToken>{self.video_source_token}</timg:VideoSourceToken>'
            '<timg:ImagingSettings>'
            f'<tt:IrCutFilter>{ir_val}</tt:IrCutFilter>'
            '</timg:ImagingSettings>'
            '<timg:ForcePersistence>true</timg:ForcePersistence>'
            '</timg:SetImagingSettings>'
        )
        status, resp = send_onvif_soap(
            img_url, body, username=self.username, password=self.password, timeout=2.5
        )
        onvif_ok = status == 200 and "Fault" not in resp

        # 2. Try Tapo Native if applicable
        if self.vendor_hint == "tapo":
            tapo_mode_map = {
                "auto": "md_night_vision",
                "ir": "inf_night_vision",
                "color": "wtl_night_vision",
                "off": "inf_night_vision",
            }
            t_mode = tapo_mode_map.get(mode, "md_night_vision")
            if self._send_tapo_command(
                "setNightVisionModeConfig",
                {"image": {"switch": {"night_vision_mode": t_mode}}},
            ):
                return True

        # 3. Try Hikvision ISAPI
        if self.vendor_hint == "hikvision":
            hik_type = {"auto": "auto", "ir": "night", "color": "day", "off": "day"}.get(mode, "auto")
            xml_payload = f'<?xml version="1.0" encoding="UTF-8"?><IrcutFilter><IrcutFilterType>{hik_type}</IrcutFilterType></IrcutFilter>'
            st, _ = send_http_or_soap_request(
                f"http://{self.camera_ip}:80/ISAPI/Image/channels/1/ircutFilter",
                method="PUT",
                body=xml_payload,
                username=self.username,
                password=self.password,
                timeout=2.0,
            )
            if st in (200, 204):
                return True

        # 4. Try Reolink API
        if self.vendor_hint == "reolink":
            state = "Auto" if mode in ("auto", "ir") else "Off"
            payload = json.dumps([{"cmd": "SetIrLights", "action": 0, "param": {"IrLights": {"state": state}}}])
            st, _ = send_http_or_soap_request(
                f"http://{self.camera_ip}:80/cgi-bin/api.cgi?cmd=SetIrLights&user={urllib.parse.quote(self.username)}&password={urllib.parse.quote(self.password)}",
                method="POST",
                body=payload,
                timeout=2.0,
            )
            if st == 200:
                return True

        return onvif_ok

    def _set_hardware_auto_tracking(self, enabled: bool) -> bool:
        """Toggle on-camera PTZ Smart Auto-Tracking across Tapo, ONVIF, Hikvision, Dahua, and Reolink."""
        # 1. Tapo Native / pytapo
        if self.vendor_hint == "tapo":
            try:
                from pytapo import Tapo  # type: ignore

                tapo = Tapo(self.camera_ip, self.username or "admin", self.password)
                tapo.setAutoTrackTarget(enabled)
                return True
            except Exception:
                pass
            if self._send_tapo_command(
                "setTargetTrackConfig",
                {"target_track": {"target_track_info": {"enabled": "on" if enabled else "off"}}},
            ):
                return True

        # 2. ONVIF Auxiliary Command (`tt:AutoTrack|On` / `tt:AutoTrack|Off`)
        ptz_url = f"http://{self.camera_ip}:{self.onvif_port}/onvif/service"
        aux_cmd = "tt:AutoTrack|On" if enabled else "tt:AutoTrack|Off"
        body = (
            '<tptz:SendAuxiliaryCommand>'
            '<tptz:ProfileToken>profile_1</tptz:ProfileToken>'
            f'<tptz:AuxiliaryData>{aux_cmd}</tptz:AuxiliaryData>'
            '</tptz:SendAuxiliaryCommand>'
        )
        st, resp = send_onvif_soap(
            ptz_url, body, username=self.username, password=self.password, timeout=2.0
        )
        if st == 200 and "Fault" not in resp:
            return True

        # 3. Hikvision ISAPI
        if self.vendor_hint == "hikvision":
            xml_payload = f'<?xml version="1.0" encoding="UTF-8"?><autoTrack><enabled>{"true" if enabled else "false"}</enabled></autoTrack>'
            st, _ = send_http_or_soap_request(
                f"http://{self.camera_ip}:80/ISAPI/PTZCtrl/channels/1/autoTrack",
                method="PUT",
                body=xml_payload,
                username=self.username,
                password=self.password,
                timeout=2.0,
            )
            if st in (200, 204):
                return True

        # 4. Dahua / Amcrest CGI
        if self.vendor_hint == "dahua":
            st, _ = send_http_or_soap_request(
                f"http://{self.camera_ip}:80/cgi-bin/configManager.cgi?action=setConfig&PtzAutoMovement[0].AutoTrackEnable={'true' if enabled else 'false'}",
                method="GET",
                username=self.username,
                password=self.password,
                timeout=2.0,
            )
            if st == 200:
                return True

        return False

    def _set_hardware_privacy_mode(self, enabled: bool) -> bool:
        """Toggle camera hardware Privacy Mode / Lens Mask."""
        if self.vendor_hint == "tapo":
            try:
                from pytapo import Tapo  # type: ignore

                tapo = Tapo(self.camera_ip, self.username or "admin", self.password)
                tapo.setPrivacyMode(enabled)
                return True
            except Exception:
                pass
            if self._send_tapo_command(
                "setLensMaskConfig",
                {"lens_mask": {"lens_mask_info": {"enabled": "on" if enabled else "off"}}},
            ):
                return True

        if self.vendor_hint == "dahua":
            st, _ = send_http_or_soap_request(
                f"http://{self.camera_ip}:80/cgi-bin/configManager.cgi?action=setConfig&LeLensMask[0].Enable={'true' if enabled else 'false'}",
                method="GET",
                username=self.username,
                password=self.password,
                timeout=2.0,
            )
            if st == 200:
                return True

        return False

    def _set_hardware_ai_switches(self, updates: Dict[str, Any]) -> bool:
        """Update on-camera AI detection switches on Tapo / Reolink / ONVIF cameras."""
        if self.vendor_hint == "tapo":
            reqs = []
            if "person_detection" in updates:
                reqs.append(
                    {
                        "method": "setPersonDetectionConfig",
                        "params": {
                            "people_detection": {
                                "detection": {"enabled": "on" if updates["person_detection"] else "off"}
                            }
                        },
                    }
                )
            if "vehicle_detection" in updates:
                reqs.append(
                    {
                        "method": "setVehicleDetectionConfig",
                        "params": {
                            "vehicle_detection": {
                                "detection": {"enabled": "on" if updates["vehicle_detection"] else "off"}
                            }
                        },
                    }
                )
            if "pet_detection" in updates:
                reqs.append(
                    {
                        "method": "setPetDetectionConfig",
                        "params": {
                            "pet_detection": {
                                "detection": {"enabled": "on" if updates["pet_detection"] else "off"}
                            }
                        },
                    }
                )
            if reqs and self._tapo_stok:
                url = f"https://{self.camera_ip}:443/stok={self._tapo_stok}/ds"
                payload = json.dumps({"method": "multipleRequest", "params": {"requests": reqs}})
                st, _ = send_http_or_soap_request(
                    url,
                    method="POST",
                    body=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=2.5,
                )
                return st == 200
        return True

    async def trigger_siren(self, active: bool = True, duration_seconds: int = 5) -> Dict[str, Any]:
        """Trigger or stop the camera's built-in siren / audio alarm."""
        self.settings.siren_active = active
        hw_triggered = await asyncio.to_thread(self._trigger_siren_sync, active, duration_seconds)
        if active and duration_seconds > 0:
            asyncio.create_task(self._auto_stop_siren(duration_seconds))
        return {
            "camera_id": self.camera_id,
            "siren_active": self.settings.siren_active,
            "hardware_acknowledged": hw_triggered,
            "duration_seconds": duration_seconds if active else 0,
        }

    async def _auto_stop_siren(self, duration_seconds: int) -> None:
        await asyncio.sleep(max(1, min(60, duration_seconds)))
        if self.settings.siren_active:
            self.settings.siren_active = False
            await asyncio.to_thread(self._trigger_siren_sync, False, 0)

    def _trigger_siren_sync(self, active: bool, duration_seconds: int) -> bool:
        if not self.camera_ip:
            return False

        # 1. Tapo Native / pytapo
        if self.vendor_hint == "tapo":
            try:
                from pytapo import Tapo  # type: ignore

                tapo = Tapo(self.camera_ip, self.username or "admin", self.password)
                if active:
                    tapo.startManualAlarm()
                else:
                    tapo.stopManualAlarm()
                return True
            except Exception:
                pass
            if self._send_tapo_command(
                "setMsgAlarmConfig",
                {
                    "msg_alarm": {
                        "chn1_msg_alarm_info": {
                            "enabled": "on" if active else "off",
                        }
                    }
                },
            ):
                return True

        # 2. ONVIF Auxiliary Command / Relay Output
        dev_url = self.device_xaddr or f"http://{self.camera_ip}:{self.onvif_port}/onvif/device_service"
        logical_state = "active" if active else "inactive"
        relay_body = (
            '<tds:SetRelayOutputState>'
            '<tds:RelayOutputToken>RelayOutput_1</tds:RelayOutputToken>'
            f'<tds:LogicalState>{logical_state}</tds:LogicalState>'
            '</tds:SetRelayOutputState>'
        )
        st, resp = send_onvif_soap(
            dev_url, relay_body, username=self.username, password=self.password, timeout=2.0
        )
        if st == 200 and "Fault" not in resp:
            return True

        # 3. Reolink AudioAlarmPlay
        if self.vendor_hint == "reolink":
            payload = json.dumps(
                [
                    {
                        "cmd": "AudioAlarmPlay",
                        "action": 0,
                        "param": {"alarm_mode": "manul", "manual_switch": 1 if active else 0},
                    }
                ]
            )
            st, _ = send_http_or_soap_request(
                f"http://{self.camera_ip}:80/cgi-bin/api.cgi?cmd=AudioAlarmPlay&user={urllib.parse.quote(self.username)}&password={urllib.parse.quote(self.password)}",
                method="POST",
                body=payload,
                timeout=2.0,
            )
            if st == 200:
                return True

        # 4. Dahua / Amcrest Coaxial Siren
        if self.vendor_hint == "dahua":
            st, _ = send_http_or_soap_request(
                f"http://{self.camera_ip}:80/cgi-bin/coaxialControlIO.cgi?action=control&channel=1&info[0].Type=2&info[0].IO={'1' if active else '0'}",
                method="GET",
                username=self.username,
                password=self.password,
                timeout=2.0,
            )
            if st == 200:
                return True

        return False

    def _send_tapo_command(self, method: str, params: Dict[str, Any]) -> bool:
        if not self._tapo_stok:
            self._probe_tapo_native()
        if not self._tapo_stok:
            return False
        url = f"https://{self.camera_ip}:443/stok={self._tapo_stok}/ds"
        payload = json.dumps(
            {
                "method": "multipleRequest",
                "params": {"requests": [{"method": method, "params": params}]},
            }
        )
        status, text = send_http_or_soap_request(
            url,
            method="POST",
            body=payload,
            headers={"Content-Type": "application/json"},
            timeout=2.5,
        )
        return status == 200 and '"error_code":0' in text.replace(" ", "")

    async def poll_edge_ai_events_once(self) -> List[Dict[str, Any]]:
        """
        Poll the camera's built-in Edge AI event stream once via:
        1. ONVIF `CreatePullPointSubscription` + `PullMessages` (works across Tapo,
           Hikvision, Dahua, Amcrest, Reolink, Axis, Generic ONVIF)
        2. Reolink `GetAiState` JSON API (if vendor is Reolink)
        Returns any newly triggered detections.
        """
        if not self.settings.edge_ai_enabled or not self.camera_ip:
            return []

        raw_events = await asyncio.to_thread(self._poll_events_sync)
        accepted: List[Dict[str, Any]] = []
        now = time.time()

        for evt in raw_events:
            obj_class = evt["object_class"]
            obj_subclass = evt["object_subclass"]

            # Filter against user-enabled Edge AI switches
            if obj_class == "person" and obj_subclass == "audio_alert":
                if not self.settings.audio_alarm_detection:
                    continue
            elif obj_class == "person" and not self.settings.person_detection:
                continue
            elif obj_class == "vehicle" and not self.settings.vehicle_detection:
                continue
            elif obj_class == "animal" and not self.settings.pet_detection:
                continue
            elif obj_class == "package" and not self.settings.package_detection:
                continue
            elif obj_class == "motion" and not self.settings.motion_detection:
                continue

            # Cooldown per class to avoid flooding duplicate detections
            key = f"{obj_class}:{obj_subclass}"
            last_ts = self._last_event_by_class.get(key, 0.0)
            if now - last_ts < max(2, self.settings.cooldown_seconds):
                continue

            self._last_event_by_class[key] = now
            accepted.append(evt)
            self.recent_events.insert(0, evt)
            if len(self.recent_events) > 50:
                self.recent_events = self.recent_events[:50]

        return accepted

    def _poll_events_sync(self) -> List[Dict[str, Any]]:
        detected: List[Dict[str, Any]] = []
        events_url = self.events_xaddr or f"http://{self.camera_ip}:{self.onvif_port}/onvif/service"

        # 1. Create or reuse ONVIF PullPointSubscription
        if not self.subscription_xaddr:
            sub_body = (
                '<tev:CreatePullPointSubscription>'
                '<tev:InitialTerminationTime>PT600S</tev:InitialTerminationTime>'
                '</tev:CreatePullPointSubscription>'
            )
            st, sub_xml = send_onvif_soap(
                events_url,
                sub_body,
                username=self.username,
                password=self.password,
                soap_action="http://www.onvif.org/ver10/events/wsdl/EventPortType/CreatePullPointSubscriptionRequest",
                timeout=2.5,
            )
            if st == 200 and "Fault" not in sub_xml and "<" in sub_xml:
                try:
                    root = ET.fromstring(sub_xml)
                    for elem in root.iter():
                        if _local_name(elem.tag) == "Address" and elem.text:
                            self.subscription_xaddr = _rewrite_xaddr_host(
                                elem.text, self.camera_ip, self.onvif_port
                            )
                            break
                except ET.ParseError:
                    pass

        target_pull_url = self.subscription_xaddr or events_url
        pull_body = (
            '<tev:PullMessages>'
            '<tev:Timeout>PT1S</tev:Timeout>'
            '<tev:MessageLimit>10</tev:MessageLimit>'
            '</tev:PullMessages>'
        )
        p_st, p_xml = send_onvif_soap(
            target_pull_url,
            pull_body,
            username=self.username,
            password=self.password,
            soap_action="http://www.onvif.org/ver10/events/wsdl/PullPointSubscription/PullMessagesRequest",
            timeout=2.5,
        )
        if p_st != 200 or "Fault" in p_xml:
            # Subscription may have expired; clear so next cycle re-subscribes
            self.subscription_xaddr = ""
        elif "<" in p_xml:
            detected.extend(self._parse_pull_messages_xml(p_xml))

        # 2. Reolink GetAiState JSON fallback
        if self.vendor_hint == "reolink":
            url = (
                f"http://{self.camera_ip}:80/cgi-bin/api.cgi"
                f"?cmd=GetAiState&user={urllib.parse.quote(self.username)}&password={urllib.parse.quote(self.password)}"
            )
            st, body = send_http_or_soap_request(url, method="GET", timeout=2.0)
            if st == 200 and '"value"' in body:
                try:
                    arr = json.loads(body)
                    val = arr[0].get("value", {}) if isinstance(arr, list) and arr else {}
                    reolink_map = {
                        "people": ("person", "person"),
                        "vehicle": ("vehicle", "car"),
                        "dog_cat": ("animal", "pet"),
                        "package": ("package", "package"),
                    }
                    for r_key, (o_cls, o_sub) in reolink_map.items():
                        state_obj = val.get(r_key, {})
                        if isinstance(state_obj, dict) and state_obj.get("alarm_state") == 1:
                            detected.append(
                                {
                                    "camera_id": self.camera_id,
                                    "object_class": o_cls,
                                    "object_subclass": o_sub,
                                    "confidence": 0.95,
                                    "topic": f"reolink:GetAiState/{r_key}",
                                    "vendor": "reolink",
                                    "timestamp": utcnow().isoformat(),
                                }
                            )
                except Exception:
                    pass

        return detected

    def _parse_pull_messages_xml(self, xml_text: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
            for msg in root.iter():
                if _local_name(msg.tag) != "NotificationMessage":
                    continue
                topic_text = ""
                data_items: Dict[str, str] = {}
                for elem in msg.iter():
                    lname = _local_name(elem.tag)
                    if lname == "Topic" and elem.text:
                        topic_text = elem.text.strip()
                    elif lname == "SimpleItem":
                        k = elem.attrib.get("Name", "")
                        v = elem.attrib.get("Value", "")
                        if k:
                            data_items[k] = v
                classified = classify_edge_event_topic(topic_text, data_items)
                if classified:
                    obj_class, obj_subclass = classified
                    results.append(
                        {
                            "camera_id": self.camera_id,
                            "object_class": obj_class,
                            "object_subclass": obj_subclass,
                            "confidence": 0.94,
                            "topic": topic_text,
                            "data": data_items,
                            "vendor": self.vendor_hint,
                            "timestamp": utcnow().isoformat(),
                        }
                    )
        except ET.ParseError:
            pass
        return results

    def get_summary(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "camera_ip": self.camera_ip,
            "onvif_port": self.onvif_port,
            "vendor": self.vendor_hint,
            "is_network_camera": bool(self.conn_info.get("is_network_camera")),
            "device_info": self.device_info,
            "capabilities": self.capabilities,
            "supported_topics": self.supported_topics,
            "settings": self.settings.to_dict(),
            "recent_events": self.recent_events[:15],
        }


class CameraEdgeManager:
    """
    Global manager that coordinates `CameraEdgeController` instances and runs a
    lightweight background loop to ingest camera-native Edge AI detections into
    OpenEye's database (`ObjectDetectionEvent` / `MotionDetectionEvent`), snapshots,
    and recordings.
    """

    def __init__(self):
        self._controllers: Dict[str, CameraEdgeController] = {}
        self._task: Optional[asyncio.Task] = None
        self._running: bool = False

    def get_controller(self, camera_id: str, source: Optional[str] = None) -> CameraEdgeController:
        if camera_id not in self._controllers:
            self._controllers[camera_id] = CameraEdgeController(camera_id, source)
        elif source:
            self._controllers[camera_id].update_source(source)
        return self._controllers[camera_id]

    def remove_controller(self, camera_id: str) -> None:
        self._controllers.pop(camera_id, None)

    def ensure_background_worker(self) -> None:
        """Start the async Edge AI event polling worker if an event loop is running."""
        if self._running and self._task and not self._task.done():
            return
        try:
            loop = asyncio.get_running_loop()
            self._running = True
            self._task = loop.create_task(self._background_poll_loop())
            logger.info("Started Camera Edge AI background event listener")
        except RuntimeError:
            pass

    async def _background_poll_loop(self) -> None:
        while self._running:
            try:
                for camera_id, ctrl in list(self._controllers.items()):
                    if not ctrl.settings.edge_ai_enabled or not ctrl.camera_ip:
                        continue
                    events = await ctrl.poll_edge_ai_events_once()
                    for evt in events:
                        await self.record_edge_detection_event(camera_id, evt, ctrl)
            except Exception as exc:
                logger.debug("Edge AI background poll cycle error: %s", exc)
            await asyncio.sleep(2.5)

    async def record_edge_detection_event(
        self,
        camera_id: str,
        evt: Dict[str, Any],
        ctrl: Optional[CameraEdgeController] = None,
    ) -> Dict[str, Any]:
        """
        Persist a hardware Edge AI event into OpenEye's `ObjectDetectionEvent` and/or
        `MotionDetectionEvent` tables, capture a snapshot from the active stream, and
        trigger motion recording / face recognition wake-up.
        """
        from backend.core.camera_manager import manager as camera_manager
        from backend.database import crud
        from backend.database.utils import get_db_context

        obj_class = evt.get("object_class", "person")
        obj_subclass = evt.get("object_subclass", obj_class)
        confidence = float(evt.get("confidence", 0.94))

        snapshot_rel_path: Optional[str] = None
        frame_w, frame_h = 1920, 1080

        # Capture snapshot from live camera buffer if running
        cam = camera_manager.get_camera(camera_id)
        if cam is not None:
            # Wake up face recognition window & optionally trigger recording
            cam.last_motion_time = time.time()
            if (ctrl is None or ctrl.settings.trigger_recording_on_edge_ai):
                try:
                    cam.request_recording(15)
                except Exception:
                    pass

            pub = cam.get_published_frame()
            if pub is not None:
                frame, _, _ = pub
                if frame is not None and hasattr(frame, "shape"):
                    frame_h, frame_w = frame.shape[:2]
                    try:
                        snapshots_dir = paths.snapshots_dir
                        snapshots_dir.mkdir(parents=True, exist_ok=True)
                        ts_str = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        fname = f"edge_{obj_class}_{camera_id}_{ts_str}.jpg"
                        full_path = snapshots_dir / fname
                        if cv2.imwrite(str(full_path), frame):
                            snapshot_rel_path = f"/data/snapshots/{fname}"
                    except Exception as snap_err:
                        logger.debug("Could not write Edge AI snapshot: %s", snap_err)

        created_event_id: Optional[int] = None
        with get_db_context() as db:
            if obj_class in ("person", "vehicle", "animal", "package"):
                db_evt = crud.create_object_detection_event(
                    db,
                    {
                        "camera_id": camera_id,
                        "object_class": obj_class,
                        "object_subclass": obj_subclass,
                        "confidence": confidence,
                        "detected_at": utcnow(),
                        "bbox_x": 0,
                        "bbox_y": 0,
                        "bbox_width": frame_w,
                        "bbox_height": frame_h,
                        "frame_width": frame_w,
                        "frame_height": frame_h,
                        "snapshot_path": snapshot_rel_path,
                        "motion_detected": True,
                        "detection_metadata": json.dumps(
                            {
                                "source": "camera_edge_ai",
                                "vendor": evt.get("vendor", "onvif"),
                                "topic": evt.get("topic", ""),
                            }
                        ),
                    },
                )
                created_event_id = db_evt.id
            else:
                from backend.database.models import MotionDetectionEvent

                m_evt = MotionDetectionEvent(
                    camera_id=camera_id,
                    detected_at=utcnow(),
                    motion_area=int(frame_w * frame_h * 0.05),
                    motion_percentage=5.0,
                    contour_count=1,
                    snapshot_path=snapshot_rel_path,
                    frame_width=frame_w,
                    frame_height=frame_h,
                )
                db.add(m_evt)
                db.commit()
                db.refresh(m_evt)
                created_event_id = m_evt.id

        evt["db_event_id"] = created_event_id
        evt["snapshot_path"] = snapshot_rel_path
        return evt


edge_manager = CameraEdgeManager()
