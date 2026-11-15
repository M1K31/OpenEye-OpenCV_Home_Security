# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Camera Source At-Rest Encryption & Credential Utilities

Provides:
- Transparent Fernet symmetric encryption at rest for camera sources/URLs stored
  in the database (`EncryptedCameraSource` SQLAlchemy TypeDecorator).
- Deterministic key derivation from `CAMERA_ENCRYPTION_KEY`,
  `NOTIFICATION_ENCRYPTION_KEY`, or `SECRET_KEY` so encryption works out-of-the-box
  on every installation without manual key setup.
- Safe RFC 3986 percent-encoding when injecting RTSP/HTTP credentials into stream
  URLs (`inject_rtsp_credentials`).
- Credential redaction (`redact_url_credentials`) for logs and UI responses,
  credential stripping (`strip_url_credentials`) for duplicate-camera matching,
  and connection metadata extraction (`extract_camera_connection_info`) for
  automatic PTZ and Edge AI connection setup.
"""

import base64
import hashlib
import hmac
import logging
import os
import secrets
from typing import Any, Dict, Optional
from urllib.parse import quote, unquote, urlsplit, urlunsplit

try:
    from cryptography.fernet import Fernet, InvalidToken
    _HAS_FERNET = True
except ImportError:  # pragma: no cover - stdlib fallback when running outside venv
    Fernet = None  # type: ignore

    class InvalidToken(Exception):
        pass

    _HAS_FERNET = False

try:
    from sqlalchemy.types import String, TypeDecorator
except ImportError:  # pragma: no cover
    String = object  # type: ignore
    TypeDecorator = object  # type: ignore

logger = logging.getLogger(__name__)

ENCRYPTED_PREFIX = "enc:v1:"
_STDLIB_PREFIX = "enc:s1:"
_DOMAIN_SALT = b"openeye-camera-source-encryption-v1:"


class _StdlibAuthenticatedCipher:
    """
    Authenticated stream cipher (SHA-256 CTR + HMAC-SHA256 EtM) used only if the
    `cryptography` wheel is unavailable in a bare system Python interpreter.
    """

    def __init__(self, key_bytes: bytes):
        raw = base64.urlsafe_b64decode(key_bytes)
        self._enc_key = hashlib.sha256(b"enc:" + raw).digest()
        self._mac_key = hashlib.sha256(b"mac:" + raw).digest()

    def _keystream(self, nonce: bytes, length: int) -> bytes:
        out = bytearray()
        counter = 0
        while len(out) < length:
            block = hashlib.sha256(
                self._enc_key + nonce + counter.to_bytes(4, "big")
            ).digest()
            out.extend(block)
            counter += 1
        return bytes(out[:length])

    def encrypt(self, data: bytes) -> bytes:
        nonce = secrets.token_bytes(16)
        stream = self._keystream(nonce, len(data))
        ciphertext = bytes(a ^ b for a, b in zip(data, stream))
        tag = hmac.new(self._mac_key, nonce + ciphertext, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(nonce + tag + ciphertext)

    def decrypt(self, token: bytes) -> bytes:
        try:
            raw = base64.urlsafe_b64decode(token)
        except Exception as exc:
            raise InvalidToken("Invalid base64 token") from exc
        if len(raw) < 48:
            raise InvalidToken("Token too short")
        nonce, tag, ciphertext = raw[:16], raw[16:48], raw[48:]
        expected = hmac.new(
            self._mac_key, nonce + ciphertext, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(tag, expected):
            raise InvalidToken("HMAC verification failed")
        stream = self._keystream(nonce, len(ciphertext))
        return bytes(a ^ b for a, b in zip(ciphertext, stream))


def _derive_fernet_key(raw_secret: str) -> bytes:
    """
    Convert a configured key or secret into a valid 32-byte urlsafe-base64 Fernet key.

    If `raw_secret` is already a valid 44-character Fernet key, use it directly;
    otherwise derive a 32-byte key deterministically using SHA-256 with a domain
    separation prefix.
    """
    candidate = raw_secret.strip().encode("utf-8")
    if len(candidate) == 44:
        try:
            decoded = base64.urlsafe_b64decode(candidate)
            if len(decoded) == 32:
                return candidate
        except Exception:
            pass

    digest = hashlib.sha256(_DOMAIN_SALT + candidate).digest()
    return base64.urlsafe_b64encode(digest)


def get_camera_fernet():
    """
    Return a Fernet instance keyed from the installation's environment.

    Precedence:
      1. CAMERA_ENCRYPTION_KEY
      2. SECRET_KEY
      3. NOTIFICATION_ENCRYPTION_KEY
      4. Deterministic fallback for unit tests when no env file is loaded
    """
    secret = (
        os.getenv("CAMERA_ENCRYPTION_KEY")
        or os.getenv("SECRET_KEY")
        or os.getenv("NOTIFICATION_ENCRYPTION_KEY")
        or "openeye-default-dev-secret-key-do-not-use-in-prod"
    )
    key = _derive_fernet_key(secret)
    if _HAS_FERNET and Fernet is not None:
        return Fernet(key)
    return _StdlibAuthenticatedCipher(key)


def is_encrypted_source(value: Optional[str]) -> bool:
    """Return True if `value` carries the at-rest encryption prefix."""
    return isinstance(value, str) and (
        value.startswith(ENCRYPTED_PREFIX) or value.startswith(_STDLIB_PREFIX)
    )


def encrypt_camera_source(source: Optional[str]) -> Optional[str]:
    """
    Encrypt a camera source string for storage at rest.

    Idempotent: values already prefixed with `enc:v1:` are returned unchanged.
    """
    if not source or not isinstance(source, str):
        return source
    if is_encrypted_source(source):
        return source

    cipher = get_camera_fernet()
    token = cipher.encrypt(source.encode("utf-8")).decode("ascii")
    return f"{ENCRYPTED_PREFIX}{token}"


def _iter_fallback_ciphers():
    """
    Yield candidate ciphers derived from `.env` and `config.env` files across
    both the repo checkout and `~/.local/share/openeye` so camera sources
    encrypted before a sync/migration still decrypt seamlessly.
    """
    from pathlib import Path

    seen_secrets = set()
    candidate_paths = [
        Path.home() / ".local" / "share" / "openeye" / "config.env",
        Path.home() / ".local" / "share" / "openeye" / "app" / ".env",
        Path.home() / "Library" / "Application Support" / "OpenEye" / "config.env",
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / "config.env",
        Path("/Users/mikelsmart/GitHub/OpenEye-OpenCV_Home_Security/opencv_surveillance/.env"),
    ]
    for env_path in candidate_paths:
        try:
            if not env_path.is_file():
                continue
            for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.startswith("export "):
                    line = line[len("export "):].strip()
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                if k in ("CAMERA_ENCRYPTION_KEY", "SECRET_KEY", "NOTIFICATION_ENCRYPTION_KEY") and v and v not in seen_secrets:
                    seen_secrets.add(v)
                    key = _derive_fernet_key(v)
                    if _HAS_FERNET and Fernet is not None:
                        yield Fernet(key)
                    yield _StdlibAuthenticatedCipher(key)
        except Exception:
            continue

    # Also include the default dev fallback key
    dev_key = _derive_fernet_key("openeye-default-dev-secret-key-do-not-use-in-prod")
    if _HAS_FERNET and Fernet is not None:
        yield Fernet(dev_key)
    yield _StdlibAuthenticatedCipher(dev_key)


def decrypt_camera_source(value: Optional[str]) -> Optional[str]:
    """
    Decrypt a stored camera source string.

    Backwards-compatible: legacy plaintext values (without `enc:v1:`) are
    returned unchanged, and if the active process `SECRET_KEY` differs from the
    key used when the camera was added (e.g. after syncing between the repo and
    `~/.local/share/openeye`), fallback keys from `.env`/`config.env` are tried
    automatically.
    """
    if not value or not isinstance(value, str):
        return value
    if not is_encrypted_source(value):
        return value

    prefix = ENCRYPTED_PREFIX if value.startswith(ENCRYPTED_PREFIX) else _STDLIB_PREFIX
    token_bytes = value[len(prefix):].encode("ascii")
    try:
        return get_camera_fernet().decrypt(token_bytes).decode("utf-8")
    except Exception:
        for fallback_cipher in _iter_fallback_ciphers():
            try:
                return fallback_cipher.decrypt(token_bytes).decode("utf-8")
            except Exception:
                continue
        logger.warning(
            "Could not decrypt camera source with current or fallback keys; "
            "returning stored value without raising."
        )
        return value


def inject_rtsp_credentials(
    url: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    Safely inject percent-encoded credentials into an RTSP/RTMP/HTTP stream URL.

    Percent-encodes special characters (such as `@`, `:`, `/`, `$`, `&`) in both
    username and password so they neither break URL parsing nor trigger command-
    injection character filters.
    """
    if not url or not isinstance(url, str):
        return url

    user = (username or "").strip()
    pwd = password if password is not None else ""
    if not user and not pwd:
        return url

    try:
        parts = urlsplit(url)
        if not parts.scheme or not parts.hostname:
            return url

        # Reconstruct host[:port] without any existing userinfo
        host = parts.hostname
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        host_port = f"{host}:{parts.port}" if parts.port else host

        enc_user = quote(user, safe="")
        if pwd:
            enc_pwd = quote(pwd, safe="")
            netloc = f"{enc_user}:{enc_pwd}@{host_port}"
        else:
            netloc = f"{enc_user}@{host_port}"

        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception as e:
        logger.debug("Failed to inject credentials into URL: %s", e)
        return url


def redact_url_credentials(url: Optional[str]) -> Optional[str]:
    """
    Mask embedded password in a stream URL (`rtsp://user:***@host:554/stream1`).

    Safe for log output and UI display. Non-URL sources (e.g. `"0"`, `"mock"`)
    and URLs without passwords are returned unchanged.
    """
    if not url or not isinstance(url, str):
        return url
    decoded = decrypt_camera_source(url)
    if "@" not in decoded or "://" not in decoded:
        return decoded

    try:
        parts = urlsplit(decoded)
        if not parts.hostname:
            return decoded
        if parts.username is None:
            return decoded

        host = parts.hostname
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        host_port = f"{host}:{parts.port}" if parts.port else host

        if parts.password is not None:
            netloc = f"{parts.username}:***@{host_port}"
        else:
            netloc = f"{parts.username}@{host_port}"

        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return decoded


def strip_url_credentials(url: Optional[str]) -> Optional[str]:
    """
    Remove `username:password@` from a stream URL for canonical comparison.

    Allows discovery to recognize that `rtsp://admin:secret@192.168.50.135:554/stream1`
    in the database corresponds to `rtsp://192.168.50.135:554/stream1` on the network.
    """
    if not url or not isinstance(url, str):
        return url
    decoded = decrypt_camera_source(url)
    if "@" not in decoded or "://" not in decoded:
        return decoded

    try:
        parts = urlsplit(decoded)
        if not parts.hostname:
            return decoded

        host = parts.hostname
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        host_port = f"{host}:{parts.port}" if parts.port else host

        return urlunsplit((parts.scheme, host_port, parts.path, parts.query, parts.fragment))
    except Exception:
        return decoded


def infer_vendor_from_url(url: Optional[str]) -> str:
    """
    Infer camera manufacturer family from RTSP/HTTP stream path conventions.

    Returns one of: 'tapo', 'hikvision', 'dahua', 'reolink', 'axis', 'foscam',
    'unifi', or 'generic'.
    """
    if not url or not isinstance(url, str):
        return "generic"
    lowered = url.lower()
    if "/stream1" in lowered or "/stream2" in lowered or "tapo" in lowered:
        return "tapo"
    if "/streaming/channels/" in lowered or "/isapi/" in lowered or "hikvision" in lowered:
        return "hikvision"
    if "/cam/realmonitor" in lowered or "amcrest" in lowered or "dahua" in lowered:
        return "dahua"
    if "h264preview_" in lowered or "h265preview_" in lowered or "reolink" in lowered:
        return "reolink"
    if "/axis-media/" in lowered or "/axis-cgi/" in lowered:
        return "axis"
    if "videomain" in lowered or "videosub" in lowered or "foscam" in lowered:
        return "foscam"
    if "unifi" in lowered or "ubnt" in lowered:
        return "unifi"
    return "generic"


def extract_camera_connection_info(source: Optional[str]) -> Dict[str, Any]:
    """
    Extract decrypted host, port, username, password, path, and vendor hint
    from a stored camera `source`.

    Used by PTZ auto-connect and Camera Edge AI / Hardware controllers so users
    do not have to re-type credentials that are already encrypted in SQLite.
    """
    info: Dict[str, Any] = {
        "camera_ip": "",
        "rtsp_port": 554,
        "username": "",
        "password": "",
        "path": "",
        "scheme": "",
        "vendor_hint": "generic",
        "is_network_camera": False,
    }
    if not source or not isinstance(source, str):
        return info

    decoded = decrypt_camera_source(source).strip()
    if "://" not in decoded:
        return info

    try:
        parts = urlsplit(decoded)
        host = parts.hostname or ""
        if not host:
            return info

        info["camera_ip"] = host
        info["rtsp_port"] = parts.port or (554 if parts.scheme.startswith("rtsp") else 80)
        info["username"] = unquote(parts.username) if parts.username else ""
        info["password"] = unquote(parts.password) if parts.password else ""
        info["path"] = parts.path or "/"
        info["scheme"] = parts.scheme.lower()
        info["vendor_hint"] = infer_vendor_from_url(decoded)
        info["is_network_camera"] = True
        return info
    except Exception as e:
        logger.debug("Could not parse camera source connection info: %s", e)
        return info


class EncryptedCameraSource(TypeDecorator):
    """
    SQLAlchemy column type that transparently encrypts `Camera.source` at rest
    using Fernet (`enc:v1:<ciphertext>`) and decrypts on ORM load.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        if value is None:
            return None
        return encrypt_camera_source(str(value))

    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        if value is None:
            return None
        return decrypt_camera_source(value)
