# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Ecosystem Security Module

Provides enhanced security features for ecosystem integration:
- Token rotation and refresh
- IP-based validation
- Rate limiting for authentication attempts
- Device fingerprinting
- Secure token storage recommendations
"""

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, Optional, Tuple

# Single source of truth for crypto helpers (C-4 fix: consolidated)
from ecosystem_auth.tokens import (
    generate_secure_token,
    hash_token,
    sign_payload,
    verify_signature,
    verify_token_hash,
)

logger = logging.getLogger(__name__)

# Rate limiting storage (in production, use Redis)
_auth_attempts: Dict[str, list] = {}  # IP -> list of timestamps
_blocked_ips: Dict[str, datetime] = {}  # IP -> blocked until

# Token rotation tracking
_token_rotation_log: Dict[str, datetime] = {}  # old_token_hash -> rotated_at

# Configuration
MAX_AUTH_ATTEMPTS = 5  # Max attempts before blocking
AUTH_WINDOW_SECONDS = 300  # 5 minute window for rate limiting
BLOCK_DURATION_SECONDS = 900  # 15 minute block duration
TOKEN_ROTATION_INTERVAL_HOURS = 12  # Rotate tokens every 12 hours
TOKEN_VALIDITY_HOURS = 24  # Tokens valid for 24 hours


def generate_device_fingerprint(
    ip_address: str,
    user_agent: str = "",
    app_name: str = "",
    device_id: str = ""
) -> str:
    """
    Generate a device fingerprint from available attributes.
    
    This helps identify devices even if they reconnect with new tokens.
    """
    components = [
        ip_address or "",
        user_agent or "",
        app_name or "",
        device_id or ""
    ]
    fingerprint_data = "|".join(components)
    return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]


def check_rate_limit(ip_address: str) -> Tuple[bool, Optional[int]]:
    """
    Check if an IP address is rate limited.
    
    Returns:
        Tuple of (is_allowed, seconds_until_unblocked)
    """
    now = datetime.utcnow()
    
    # Check if IP is blocked
    if ip_address in _blocked_ips:
        blocked_until = _blocked_ips[ip_address]
        if now < blocked_until:
            remaining = int((blocked_until - now).total_seconds())
            return False, remaining
        else:
            # Block expired, remove it
            del _blocked_ips[ip_address]
    
    # Clean up old attempts
    if ip_address in _auth_attempts:
        cutoff = now - timedelta(seconds=AUTH_WINDOW_SECONDS)
        _auth_attempts[ip_address] = [
            ts for ts in _auth_attempts[ip_address]
            if ts > cutoff
        ]
    
    # Check attempt count
    attempts = len(_auth_attempts.get(ip_address, []))
    if attempts >= MAX_AUTH_ATTEMPTS:
        # Block the IP
        _blocked_ips[ip_address] = now + timedelta(seconds=BLOCK_DURATION_SECONDS)
        logger.warning(f"IP {ip_address} blocked for {BLOCK_DURATION_SECONDS}s due to too many auth attempts")
        return False, BLOCK_DURATION_SECONDS
    
    return True, None


def record_auth_attempt(ip_address: str, success: bool):
    """
    Record an authentication attempt for rate limiting.
    
    Successful attempts clear the failure count.
    """
    now = datetime.utcnow()
    
    if success:
        # Clear attempts on successful auth
        if ip_address in _auth_attempts:
            del _auth_attempts[ip_address]
        if ip_address in _blocked_ips:
            del _blocked_ips[ip_address]
    else:
        # Record failed attempt
        if ip_address not in _auth_attempts:
            _auth_attempts[ip_address] = []
        _auth_attempts[ip_address].append(now)


def should_rotate_token(token_created_at: datetime) -> bool:
    """
    Check if a token should be rotated based on age.
    
    Tokens should be rotated periodically for security.
    """
    age = datetime.utcnow() - token_created_at
    return age > timedelta(hours=TOKEN_ROTATION_INTERVAL_HOURS)


def is_token_expired(token_created_at: datetime) -> bool:
    """Check if a token has expired."""
    age = datetime.utcnow() - token_created_at
    return age > timedelta(hours=TOKEN_VALIDITY_HOURS)


def validate_ip_for_device(
    current_ip: str,
    registered_ip: str,
    allow_ip_change: bool = True
) -> Tuple[bool, str]:
    """
    Validate that a device's IP is acceptable.
    
    Args:
        current_ip: Current request IP
        registered_ip: IP registered with the device
        allow_ip_change: Whether to allow devices to change IPs
        
    Returns:
        Tuple of (is_valid, message)
    """
    if not registered_ip:
        # New registration
        return True, "New device registration"
    
    if current_ip == registered_ip:
        return True, "IP matches registration"
    
    if allow_ip_change:
        logger.info(f"Device IP changed from {registered_ip} to {current_ip}")
        return True, "IP change allowed"
    
    logger.warning(f"Device IP mismatch: expected {registered_ip}, got {current_ip}")
    return False, "IP address does not match registered device"


def generate_challenge(device_token: str) -> Tuple[str, str]:
    """
    Generate a challenge-response pair for device verification.

    The device must HMAC-sign the challenge with its token.  The
    expected_response is pre-computed here so the caller can compare
    without needing the token again.

    Args:
        device_token: The device's shared secret / token.

    Returns:
        Tuple of (challenge, expected_response)
    """
    challenge = secrets.token_hex(16)
    expected = hmac.new(
        device_token.encode(), challenge.encode(), hashlib.sha256
    ).hexdigest()
    return challenge, expected


def verify_challenge_response(
    challenge: str,
    response: str,
    device_token: str
) -> bool:
    """
    Verify a challenge response from a device.
    
    The device should sign the challenge with its token.
    """
    expected = hmac.new(
        device_token.encode(),
        challenge.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, response)


class SecureTokenManager:
    """
    Manages secure token operations with rotation.
    
    Usage:
        manager = SecureTokenManager()
        token, token_id = manager.create_token()
        
        # Later, verify and optionally rotate
        is_valid, new_token = manager.verify_and_rotate(token, token_id)
    """
    
    def __init__(self):
        self._tokens: Dict[str, dict] = {}  # token_id -> {hash, created_at, rotated_from}
    
    def create_token(self) -> Tuple[str, str]:
        """
        Create a new secure token.
        
        Returns:
            Tuple of (token, token_id)
        """
        token = generate_secure_token()
        token_id = secrets.token_hex(8)
        
        self._tokens[token_id] = {
            "hash": hash_token(token),
            "created_at": datetime.utcnow(),
            "rotated_from": None
        }
        
        return token, token_id
    
    def verify_token(self, token: str, token_id: str) -> bool:
        """Verify a token is valid."""
        if token_id not in self._tokens:
            return False
        
        token_data = self._tokens[token_id]
        
        # Check expiration
        if is_token_expired(token_data["created_at"]):
            logger.info(f"Token {token_id} has expired")
            del self._tokens[token_id]
            return False
        
        # Verify hash
        return verify_token_hash(token, token_data["hash"])
    
    def rotate_token(self, token_id: str) -> Optional[str]:
        """
        Rotate a token, returning the new token.
        
        The old token remains valid for a grace period.
        """
        if token_id not in self._tokens:
            return None
        
        old_data = self._tokens[token_id]
        new_token = generate_secure_token()
        
        # Update with new token
        self._tokens[token_id] = {
            "hash": hash_token(new_token),
            "created_at": datetime.utcnow(),
            "rotated_from": old_data["hash"]
        }
        
        logger.info(f"Rotated token {token_id}")
        return new_token
    
    def verify_and_rotate(
        self,
        token: str,
        token_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify a token and rotate if needed.
        
        Returns:
            Tuple of (is_valid, new_token_if_rotated)
        """
        if not self.verify_token(token, token_id):
            return False, None
        
        token_data = self._tokens[token_id]
        
        # Check if rotation is needed
        if should_rotate_token(token_data["created_at"]):
            new_token = self.rotate_token(token_id)
            return True, new_token
        
        return True, None
    
    def revoke_token(self, token_id: str):
        """Revoke a token immediately."""
        if token_id in self._tokens:
            del self._tokens[token_id]
            logger.info(f"Revoked token {token_id}")


# Decorator for rate-limited endpoints
def rate_limit(func):
    """
    Decorator to apply rate limiting to an endpoint.
    
    Usage:
        @rate_limit
        async def connect_device(request: Request, ...):
            ...
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract request from args or kwargs
        request = kwargs.get('request') or kwargs.get('http_request')
        if not request:
            for arg in args:
                if hasattr(arg, 'client'):
                    request = arg
                    break
        
        if request and hasattr(request, 'client') and request.client:
            ip = request.client.host
            is_allowed, wait_time = check_rate_limit(ip)
            
            if not is_allowed:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many requests. Please wait {wait_time} seconds.",
                    headers={"Retry-After": str(wait_time)}
                )
        
        return await func(*args, **kwargs)
    
    return wrapper


# Security recommendations as constants
SECURITY_RECOMMENDATIONS = {
    "use_https": {
        "title": "Use HTTPS",
        "description": "Always use HTTPS in production to encrypt token transmission",
        "severity": "high",
        "implementation": "Configure SSL/TLS certificates with Let's Encrypt or similar"
    },
    "token_storage": {
        "title": "Secure Token Storage",
        "description": "Store tokens securely - never in plain text logs or databases",
        "severity": "high",
        "implementation": "Use environment variables or secure vault services"
    },
    "ip_allowlist": {
        "title": "IP Allowlisting",
        "description": "Restrict ecosystem connections to known IP ranges",
        "severity": "medium",
        "implementation": "Configure ALLOWED_ECOSYSTEM_IPS environment variable"
    },
    "regular_rotation": {
        "title": "Token Rotation",
        "description": "Rotate ecosystem tokens regularly",
        "severity": "medium",
        "implementation": "Tokens auto-rotate every 12 hours when rotation is enabled"
    },
    "audit_logging": {
        "title": "Audit Logging",
        "description": "Log all ecosystem authentication attempts",
        "severity": "medium",
        "implementation": "Enable audit logging in system settings"
    },
    "firewall": {
        "title": "Firewall Rules",
        "description": "Use firewall rules to restrict access to ecosystem ports",
        "severity": "high",
        "implementation": "Configure iptables or cloud firewall rules"
    }
}


def get_security_status() -> dict:
    """
    Get current security status for admin dashboard.
    
    Returns information about rate limiting, blocked IPs, etc.
    """
    now = datetime.utcnow()
    
    # Count active blocks
    active_blocks = sum(
        1 for blocked_until in _blocked_ips.values()
        if blocked_until > now
    )
    
    # Count recent auth attempts
    recent_attempts = sum(len(attempts) for attempts in _auth_attempts.values())
    
    return {
        "active_blocks": active_blocks,
        "blocked_ips": [
            {"ip": ip, "until": until.isoformat()}
            for ip, until in _blocked_ips.items()
            if until > now
        ],
        "recent_auth_attempts": recent_attempts,
        "rate_limit_config": {
            "max_attempts": MAX_AUTH_ATTEMPTS,
            "window_seconds": AUTH_WINDOW_SECONDS,
            "block_duration_seconds": BLOCK_DURATION_SECONDS
        },
        "token_config": {
            "rotation_interval_hours": TOKEN_ROTATION_INTERVAL_HOURS,
            "validity_hours": TOKEN_VALIDITY_HOURS
        },
        "recommendations": list(SECURITY_RECOMMENDATIONS.values())
    }

