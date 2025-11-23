# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Camera Source Validation
Prevents SSRF attacks and command injection via camera source URLs
"""

import re
import os
from urllib.parse import urlparse
from typing import Tuple
from fastapi import HTTPException, status


# Configuration
ALLOW_LOCALHOST = os.getenv("ALLOW_LOCALHOST_CAMERAS", "true").lower() == "true"
ALLOW_PRIVATE_NETWORKS = os.getenv("ALLOW_PRIVATE_NETWORKS", "true").lower() == "true"

# Private IP ranges (RFC 1918)
PRIVATE_IP_RANGES = [
    r'^10\.',                    # 10.0.0.0/8
    r'^172\.(1[6-9]|2[0-9]|3[01])\.', # 172.16.0.0/12
    r'^192\.168\.',              # 192.168.0.0/16
    r'^127\.',                   # Loopback
    r'^169\.254\.',              # Link-local
]


def is_private_ip(hostname: str) -> bool:
    """
    Check if hostname is a private/internal IP address

    Args:
        hostname: IP address or hostname to check

    Returns:
        True if hostname is in private IP range
    """
    if not hostname:
        return False

    # Check for localhost
    if hostname in ['localhost', '127.0.0.1', '::1']:
        return True

    # Check private IP ranges
    for pattern in PRIVATE_IP_RANGES:
        if re.match(pattern, hostname):
            return True

    return False


def validate_rtsp_url(source: str) -> Tuple[bool, str]:
    """
    Validate RTSP/RTMP camera source URL

    Args:
        source: Camera source URL

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check protocol
    if not source.startswith(('rtsp://', 'rtmp://', 'rtsps://')):
        return False, "Invalid protocol. Must be rtsp://, rtmp://, or rtsps://"

    # Parse URL
    try:
        parsed = urlparse(source)
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"

    # Validate hostname exists
    if not parsed.hostname:
        return False, "URL must include a hostname"

    # Check for SSRF to internal networks
    if is_private_ip(parsed.hostname):
        if not ALLOW_LOCALHOST and parsed.hostname in ['localhost', '127.0.0.1', '::1']:
            return False, "Localhost camera sources are not allowed (set ALLOW_LOCALHOST_CAMERAS=true to enable)"

        if not ALLOW_PRIVATE_NETWORKS:
            return False, "Private network camera sources are not allowed (set ALLOW_PRIVATE_NETWORKS=true to enable)"

    # Check for suspicious characters that could lead to command injection
    suspicious_chars = [';', '|', '&', '`', '$', '(', ')', '<', '>']
    for char in suspicious_chars:
        if char in source:
            return False, f"URL contains suspicious character: {char}"

    # Validate port (if specified)
    if parsed.port:
        if not (1 <= parsed.port <= 65535):
            return False, f"Invalid port number: {parsed.port}"

    return True, ""


def validate_usb_source(source: str) -> Tuple[bool, str]:
    """
    Validate USB camera device path

    Args:
        source: Camera source (device path or index)

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Allow integer indices (0, 1, 2, etc.)
    if source.isdigit():
        index = int(source)
        if 0 <= index <= 10:  # Reasonable upper limit
            return True, ""
        else:
            return False, f"USB camera index must be between 0 and 10, got {index}"

    # Allow /dev/video* paths (Linux)
    if re.match(r'^/dev/video\d+$', source):
        return True, ""

    # Allow COM* paths (Windows - though unlikely for this project)
    if re.match(r'^COM\d+$', source, re.IGNORECASE):
        return True, ""

    return False, "USB source must be a device index (0-10) or device path (/dev/videoN)"


def validate_mock_source(source: str) -> Tuple[bool, str]:
    """
    Validate mock camera source

    Args:
        source: Camera source

    Returns:
        Tuple of (is_valid, error_message)
    """
    if source.lower() != "mock":
        return False, "Mock camera source must be exactly 'mock'"

    return True, ""


def validate_onvif_source(source: str) -> Tuple[bool, str]:
    """
    Validate ONVIF camera source URL

    Args:
        source: Camera source URL

    Returns:
        Tuple of (is_valid, error_message)
    """
    # ONVIF cameras typically use HTTP/HTTPS
    if not source.startswith(('http://', 'https://')):
        return False, "ONVIF source must use http:// or https://"

    # Parse URL
    try:
        parsed = urlparse(source)
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"

    # Validate hostname
    if not parsed.hostname:
        return False, "URL must include a hostname"

    # Check for SSRF to internal networks (same rules as RTSP)
    if is_private_ip(parsed.hostname):
        if not ALLOW_LOCALHOST and parsed.hostname in ['localhost', '127.0.0.1', '::1']:
            return False, "Localhost camera sources are not allowed"

        if not ALLOW_PRIVATE_NETWORKS:
            return False, "Private network camera sources are not allowed"

    # Check for suspicious characters
    suspicious_chars = [';', '|', '&', '`', '$', '(', ')', '<', '>']
    for char in suspicious_chars:
        if char in source:
            return False, f"URL contains suspicious character: {char}"

    return True, ""


def validate_camera_source(source: str, camera_type: str) -> None:
    """
    Validate camera source URL based on camera type

    Args:
        source: Camera source URL or device path
        camera_type: Type of camera (rtsp, usb, mock, onvif)

    Raises:
        HTTPException: If validation fails
    """
    if not source:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera source cannot be empty"
        )

    if not camera_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera type must be specified"
        )

    camera_type = camera_type.lower()

    # Validate based on camera type
    validators = {
        'rtsp': validate_rtsp_url,
        'rtmp': validate_rtsp_url,  # Same validation as RTSP
        'usb': validate_usb_source,
        'mock': validate_mock_source,
        'onvif': validate_onvif_source,
    }

    validator = validators.get(camera_type)
    if not validator:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported camera type: {camera_type}. Supported: rtsp, usb, mock, onvif"
        )

    is_valid, error_message = validator(source)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid camera source: {error_message}"
        )
