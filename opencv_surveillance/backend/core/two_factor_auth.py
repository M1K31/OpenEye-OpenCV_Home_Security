# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Two-Factor Authentication (2FA) System
TOTP-based 2FA using free and open source libraries
"""

import pyotp
import qrcode
import io
import base64
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TwoFactorAuth:
    """
    TOTP-based Two-Factor Authentication
    Uses pyotp (free and open source) for TOTP generation
    """

    def __init__(self, issuer_name: str = "OpenEye Surveillance"):
        """
        Initialize 2FA system

        Args:
            issuer_name: Name shown in authenticator apps
        """
        self.issuer_name = issuer_name

    def generate_secret(self) -> str:
        """
        Generate a new TOTP secret for a user

        Returns:
            Base32-encoded secret key
        """
        return pyotp.random_base32()

    def get_provisioning_uri(self, username: str, secret: str) -> str:
        """
        Generate provisioning URI for QR code

        Args:
            username: User's username
            secret: User's TOTP secret

        Returns:
            Provisioning URI for authenticator apps
        """
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(
            name=username,
            issuer_name=self.issuer_name
        )

    def generate_qr_code(self, username: str, secret: str) -> str:
        """
        Generate QR code for 2FA setup

        Args:
            username: User's username
            secret: User's TOTP secret

        Returns:
            Base64-encoded PNG image of QR code
        """
        uri = self.get_provisioning_uri(username, secret)

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)

        # Create image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        img_str = base64.b64encode(buffer.read()).decode()

        return f"data:image/png;base64,{img_str}"

    def verify_token(self, secret: str, token: str, valid_window: int = 1) -> bool:
        """
        Verify a TOTP token

        Args:
            secret: User's TOTP secret
            token: 6-digit token from authenticator app
            valid_window: Number of time windows to check (default: 1)
                         1 = 30 seconds before/after current time

        Returns:
            True if token is valid, False otherwise
        """
        try:
            totp = pyotp.TOTP(secret)
            return totp.verify(token, valid_window=valid_window)
        except Exception as e:
            logger.error(f"2FA verification error: {e}")
            return False

    def get_backup_codes(self, count: int = 10) -> list:
        """
        Generate backup codes for 2FA recovery

        Args:
            count: Number of backup codes to generate

        Returns:
            List of backup codes (format: XXXX-XXXX-XXXX)
        """
        import secrets
        import string

        codes = []
        for _ in range(count):
            # Generate 12-character code (3 groups of 4)
            code_parts = []
            for _ in range(3):
                part = ''.join(secrets.choice(string.ascii_uppercase + string.digits)
                             for _ in range(4))
                code_parts.append(part)
            codes.append('-'.join(code_parts))

        return codes


# Global 2FA instance
_twofa: Optional[TwoFactorAuth] = None


def get_2fa_system() -> TwoFactorAuth:
    """Get or create global 2FA system instance"""
    global _twofa
    if _twofa is None:
        _twofa = TwoFactorAuth()
    return _twofa
