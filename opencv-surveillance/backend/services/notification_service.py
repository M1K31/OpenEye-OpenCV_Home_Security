# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Notification Service - Handles sending alerts via multiple channels
"""

import logging
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, Any
import os
from datetime import datetime
import aiohttp

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Central service for sending notifications via email, SMS, push, and webhooks
    """
    
    def __init__(self):
        # Email configuration (loaded from environment variables)
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.smtp_from_address = os.getenv("SMTP_FROM_ADDRESS", self.smtp_username)
        
        # Twilio configuration for SMS
        self.twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.twilio_from_number = os.getenv("TWILIO_FROM_NUMBER", "")
        
        # Firebase configuration for push notifications
        self.firebase_credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
        
        # Initialize Twilio client if credentials are provided
        self.twilio_client = None
        if self.twilio_account_sid and self.twilio_auth_token:
            try:
                from twilio.rest import Client
                self.twilio_client = Client(self.twilio_account_sid, self.twilio_auth_token)
                logger.info("Twilio SMS client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")
        
        logger.info("NotificationService initialized")
    
    async def send_email(
        self,
        to_address: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Send an email notification
        
        Args:
            to_address: Recipient email address
            subject: Email subject
            body: Plain text email body
            html_body: Optional HTML version of the email
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        if not self.smtp_username or not self.smtp_password:
            return False, "SMTP credentials not configured"
        
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["From"] = self.smtp_from_address
            message["To"] = to_address
            message["Subject"] = subject
            
            # Add plain text part
            message.attach(MIMEText(body, "plain"))
            
            # Add HTML part if provided
            if html_body:
                message.attach(MIMEText(html_body, "html"))
            
            # Send email
            async with aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
                use_tls=False
            ) as smtp:
                await smtp.connect()
                await smtp.starttls()
                await smtp.login(self.smtp_username, self.smtp_password)
                await smtp.send_message(message)
            
            logger.info(f"Email sent successfully to {to_address}")
            return True, None
            
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def send_sms(
        self,
        to_number: str,
        message: str
    ) -> tuple[bool, Optional[str]]:
        """
        Send an SMS notification via Twilio
        
        Args:
            to_number: Recipient phone number (E.164 format, e.g., +1234567890)
            message: SMS message content
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        if not self.twilio_client:
            return False, "Twilio not configured"
        
        try:
            message_obj = self.twilio_client.messages.create(
                body=message,
                from_=self.twilio_from_number,
                to=to_number
            )
            
            logger.info(f"SMS sent successfully to {to_number}, SID: {message_obj.sid}")
            return True, None
            
        except Exception as e:
            error_msg = f"Failed to send SMS: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def send_push_notification(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Send a push notification via Firebase Cloud Messaging
        
        Args:
            token: FCM device token
            title: Notification title
            body: Notification body
            data: Optional additional data
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging
            
            # Initialize Firebase if not already done
            if not firebase_admin._apps:
                if os.path.exists(self.firebase_credentials_path):
                    cred = credentials.Certificate(self.firebase_credentials_path)
                    firebase_admin.initialize_app(cred)
                else:
                    return False, "Firebase credentials not found"
            
            # Create message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                data=data or {},
                token=token
            )
            
            # Send message
            response = messaging.send(message)
            logger.info(f"Push notification sent successfully: {response}")
            return True, None
            
        except Exception as e:
            error_msg = f"Failed to send push notification: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    async def send_webhook(
        self,
        webhook_url: str,
        payload: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Send a webhook notification (HTTP POST)
        
        Args:
            webhook_url: Target webhook URL
            payload: JSON payload to send
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status in [200, 201, 202, 204]:
                        logger.info(f"Webhook sent successfully to {webhook_url}")
                        return True, None
                    else:
                        error_msg = f"Webhook returned status {response.status}"
                        logger.warning(error_msg)
                        return False, error_msg
                        
        except Exception as e:
            error_msg = f"Failed to send webhook: {str(e)}"
            logger.error(error_msg)
            return False, error_msg


# Global singleton instance
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get or create the global notification service instance"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service