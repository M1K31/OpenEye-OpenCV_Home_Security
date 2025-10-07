# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Alert & Notification System
Multi-channel notification delivery with templates and scheduling

This module provides email, SMS, push notifications, and custom alerts
with template support, scheduling, rate limiting, and delivery tracking.
"""

import logging
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import json
from enum import Enum
from jinja2 import Template
import requests

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    """Notification delivery channels"""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    TELEGRAM = "telegram"
    DISCORD = "discord"


class AlertPriority(Enum):
    """Alert priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AlertRule:
    """Alert rule configuration"""
    id: str
    name: str
    enabled: bool = True
    
    # Trigger conditions
    event_types: List[str] = field(default_factory=list)
    camera_ids: Optional[List[str]] = None  # None = all cameras
    time_range: Optional[Dict[str, str]] = None  # {"start": "22:00", "end": "06:00"}
    days_of_week: Optional[List[int]] = None  # 0-6 (Monday-Sunday)
    
    # Notification settings
    channels: List[NotificationChannel] = field(default_factory=list)
    priority: AlertPriority = AlertPriority.MEDIUM
    recipients: List[str] = field(default_factory=list)
    
    # Rate limiting
    cooldown_seconds: int = 300  # Don't repeat same alert within this time
    max_per_hour: int = 10
    
    # Template
    subject_template: str = "Alert: {event_type} on {camera_id}"
    body_template: str = "Event detected at {timestamp}"
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_triggered: Optional[datetime] = None


@dataclass
class Notification:
    """Notification to be delivered"""
    id: str
    alert_rule_id: str
    channel: NotificationChannel
    recipient: str
    subject: str
    body: str
    priority: AlertPriority
    timestamp: datetime
    data: Dict = field(default_factory=dict)
    attachments: List[str] = field(default_factory=list)
    
    # Delivery status
    delivered: bool = False
    delivery_time: Optional[datetime] = None
    error: Optional[str] = None


class EmailNotifier:
    """
    Email notification delivery
    
    Sends emails via SMTP with HTML templates and attachments
    """
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        username: str = "",
        password: str = "",
        from_email: str = "",
        use_tls: bool = True
    ):
        """Initialize email notifier"""
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email or username
        self.use_tls = use_tls
        
        logger.info(f"Email notifier initialized for {smtp_host}")
    
    async def send(self, notification: Notification) -> bool:
        """
        Send email notification
        
        Args:
            notification: Notification to send
            
        Returns:
            True if successful
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = notification.subject
            msg['From'] = self.from_email
            msg['To'] = notification.recipient
            msg['Date'] = notification.timestamp.strftime("%a, %d %b %Y %H:%M:%S %z")
            
            # Priority header
            if notification.priority == AlertPriority.CRITICAL:
                msg['X-Priority'] = '1'
            elif notification.priority == AlertPriority.HIGH:
                msg['X-Priority'] = '2'
            
            # HTML body
            html_body = self._create_html_body(notification)
            msg.attach(MIMEText(html_body, 'html'))
            
            # Attachments (images)
            for attachment_path in notification.attachments:
                try:
                    with open(attachment_path, 'rb') as f:
                        img = MIMEImage(f.read())
                        img.add_header('Content-ID', f'<{Path(attachment_path).name}>')
                        msg.attach(img)
                except Exception as e:
                    logger.error(f"Error attaching {attachment_path}: {e}")
            
            # Send via SMTP
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_smtp, msg, notification.recipient)
            
            logger.info(f"Email sent to {notification.recipient}")
            return True
        
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            notification.error = str(e)
            return False
    
    def _send_smtp(self, msg: MIMEMultipart, recipient: str):
        """Send email via SMTP (blocking)"""
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            if self.use_tls:
                server.starttls()
            
            if self.username and self.password:
                server.login(self.username, self.password)
            
            server.send_message(msg, self.from_email, [recipient])
    
    def _create_html_body(self, notification: Notification) -> str:
        """Create HTML email body"""
        template = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: #007bff; color: white; padding: 20px; text-align: center; }
                .content { background: #f8f9fa; padding: 20px; margin: 20px 0; }
                .footer { text-align: center; color: #666; font-size: 12px; padding: 20px; }
                .priority-critical { border-left: 5px solid #dc3545; }
                .priority-high { border-left: 5px solid #fd7e14; }
                .priority-medium { border-left: 5px solid #ffc107; }
                .priority-low { border-left: 5px solid #28a745; }
                .button { 
                    display: inline-block; 
                    padding: 10px 20px; 
                    background: #007bff; 
                    color: white; 
                    text-decoration: none; 
                    border-radius: 5px; 
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🔔 Surveillance Alert</h2>
                </div>
                <div class="content priority-{{ priority }}">
                    <h3>{{ subject }}</h3>
                    <p>{{ body }}</p>
                    
                    {% if data %}
                    <table style="width:100%; border-collapse: collapse;">
                        {% for key, value in data.items() %}
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>{{ key }}</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{{ value }}</td>
                        </tr>
                        {% endfor %}
                    </table>
                    {% endif %}
                    
                    <p style="margin-top: 20px;">
                        <a href="{{ dashboard_url }}" class="button">View Dashboard</a>
                    </p>
                </div>
                <div class="footer">
                    <p>OpenCV Surveillance System</p>
                    <p>{{ timestamp }}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        jinja_template = Template(template)
        
        return jinja_template.render(
            subject=notification.subject,
            body=notification.body,
            priority=notification.priority.value,
            data=notification.data,
            timestamp=notification.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            dashboard_url="http://localhost:8080/dashboard"
        )


class SMSNotifier:
    """
    SMS notification delivery
    
    Sends SMS via Twilio API
    """
    
    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str
    ):
        """Initialize SMS notifier"""
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.from_number = from_number
        
        logger.info("SMS notifier initialized")
    
    async def send(self, notification: Notification) -> bool:
        """Send SMS notification"""
        try:
            # Twilio API endpoint
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
            
            # Prepare SMS body (limited to 160 characters)
            sms_body = f"{notification.subject}\n{notification.body[:100]}"
            
            # Send request
            response = requests.post(
                url,
                auth=(self.account_sid, self.auth_token),
                data={
                    'From': self.from_number,
                    'To': notification.recipient,
                    'Body': sms_body
                }
            )
            
            response.raise_for_status()
            
            logger.info(f"SMS sent to {notification.recipient}")
            return True
        
        except Exception as e:
            logger.error(f"Error sending SMS: {e}")
            notification.error = str(e)
            return False


class PushNotifier:
    """
    Push notification delivery
    
    Sends push notifications via Firebase Cloud Messaging (FCM)
    """
    
    def __init__(self, fcm_server_key: str):
        """Initialize push notifier"""
        self.fcm_server_key = fcm_server_key
        self.fcm_url = "https://fcm.googleapis.com/fcm/send"
        
        logger.info("Push notifier initialized")
    
    async def send(self, notification: Notification) -> bool:
        """Send push notification"""
        try:
            headers = {
                'Authorization': f'key={self.fcm_server_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'to': notification.recipient,  # FCM device token
                'notification': {
                    'title': notification.subject,
                    'body': notification.body,
                    'sound': 'default',
                    'priority': 'high' if notification.priority in [AlertPriority.HIGH, AlertPriority.CRITICAL] else 'normal'
                },
                'data': notification.data
            }
            
            response = requests.post(
                self.fcm_url,
                headers=headers,
                json=payload
            )
            
            response.raise_for_status()
            
            logger.info(f"Push notification sent to {notification.recipient}")
            return True
        
        except Exception as e:
            logger.error(f"Error sending push notification: {e}")
            notification.error = str(e)
            return False


class TelegramNotifier:
    """
    Telegram notification delivery
    
    Sends messages via Telegram Bot API
    """
    
    def __init__(self, bot_token: str):
        """Initialize Telegram notifier"""
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
        logger.info("Telegram notifier initialized")
    
    async def send(self, notification: Notification) -> bool:
        """Send Telegram message"""
        try:
            # notification.recipient should be chat_id
            message_text = f"*{notification.subject}*\n\n{notification.body}"
            
            url = f"{self.base_url}/sendMessage"
            
            response = requests.post(url, data={
                'chat_id': notification.recipient,
                'text': message_text,
                'parse_mode': 'Markdown'
            })
            
            response.raise_for_status()
            
            # Send images if attachments
            for image_path in notification.attachments:
                try:
                    with open(image_path, 'rb') as photo:
                        requests.post(
                            f"{self.base_url}/sendPhoto",
                            data={'chat_id': notification.recipient},
                            files={'photo': photo}
                        )
                except Exception as e:
                    logger.error(f"Error sending Telegram photo: {e}")
            
            logger.info(f"Telegram message sent to {notification.recipient}")
            return True
        
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            notification.error = str(e)
            return False


class AlertManager:
    """
    Main alert management system
    
    Coordinates alert rules, notification delivery, and tracking
    """
    
    def __init__(self, config_path: str = "config/alerts.json"):
        """Initialize alert manager"""
        self.config_path = Path(config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Alert rules
        self.rules: Dict[str, AlertRule] = {}
        self._load_rules()
        
        # Notifiers
        self.notifiers: Dict[NotificationChannel, object] = {}
        
        # Delivery queue
        self.notification_queue: asyncio.Queue = asyncio.Queue()
        
        # Rate limiting
        self._trigger_history: Dict[str, List[datetime]] = {}
        
        # Delivery history
        self.delivery_history: List[Notification] = []
        
        logger.info(f"Alert manager initialized with {len(self.rules)} rules")
    
    def _load_rules(self):
        """Load alert rules from disk"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    
                    for rule_data in data.get('rules', []):
                        rule = AlertRule(
                            id=rule_data['id'],
                            name=rule_data['name'],
                            enabled=rule_data.get('enabled', True),
                            event_types=rule_data.get('event_types', []),
                            camera_ids=rule_data.get('camera_ids'),
                            channels=[NotificationChannel(c) for c in rule_data.get('channels', [])],
                            priority=AlertPriority(rule_data.get('priority', 'medium')),
                            recipients=rule_data.get('recipients', []),
                            cooldown_seconds=rule_data.get('cooldown_seconds', 300),
                            subject_template=rule_data.get('subject_template', ''),
                            body_template=rule_data.get('body_template', '')
                        )
                        
                        self.rules[rule.id] = rule
        
        except Exception as e:
            logger.error(f"Error loading alert rules: {e}")
    
    def _save_rules(self):
        """Save alert rules to disk"""
        try:
            data = {
                'rules': [
                    {
                        'id': rule.id,
                        'name': rule.name,
                        'enabled': rule.enabled,
                        'event_types': rule.event_types,
                        'camera_ids': rule.camera_ids,
                        'channels': [c.value for c in rule.channels],
                        'priority': rule.priority.value,
                        'recipients': rule.recipients,
                        'cooldown_seconds': rule.cooldown_seconds,
                        'subject_template': rule.subject_template,
                        'body_template': rule.body_template
                    }
                    for rule in self.rules.values()
                ]
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
        
        except Exception as e:
            logger.error(f"Error saving alert rules: {e}")
    
    def register_notifier(self, channel: NotificationChannel, notifier: object):
        """Register notification provider"""
        self.notifiers[channel] = notifier
        logger.info(f"Registered notifier for {channel.value}")
    
    def add_rule(self, rule: AlertRule):
        """Add alert rule"""
        self.rules[rule.id] = rule
        self._save_rules()
        logger.info(f"Added alert rule: {rule.name}")
    
    def remove_rule(self, rule_id: str):
        """Remove alert rule"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            self._save_rules()
            logger.info(f"Removed alert rule: {rule_id}")
    
    def _should_trigger(self, rule: AlertRule, event_data: Dict) -> bool:
        """Check if rule should trigger for event"""
        if not rule.enabled:
            return False
        
        # Check event type
        if rule.event_types and event_data.get('event_type') not in rule.event_types:
            return False
        
        # Check camera
        if rule.camera_ids and event_data.get('camera_id') not in rule.camera_ids:
            return False
        
        # Check time range
        if rule.time_range:
            now = datetime.now().time()
            start = datetime.strptime(rule.time_range['start'], '%H:%M').time()
            end = datetime.strptime(rule.time_range['end'], '%H:%M').time()
            
            if start <= end:
                if not (start <= now <= end):
                    return False
            else:  # Crosses midnight
                if not (now >= start or now <= end):
                    return False
        
        # Check day of week
        if rule.days_of_week:
            today = datetime.now().weekday()
            if today not in rule.days_of_week:
                return False
        
        # Check rate limiting
        if not self._check_rate_limit(rule):
            return False
        
        return True
    
    def _check_rate_limit(self, rule: AlertRule) -> bool:
        """Check if rule is within rate limits"""
        now = datetime.now()
        rule_id = rule.id
        
        if rule_id not in self._trigger_history:
            self._trigger_history[rule_id] = []
        
        # Remove old entries
        cutoff_time = now - timedelta(seconds=rule.cooldown_seconds)
        self._trigger_history[rule_id] = [
            t for t in self._trigger_history[rule_id]
            if t > cutoff_time
        ]
        
        # Check cooldown
        if rule.last_triggered:
            if (now - rule.last_triggered).total_seconds() < rule.cooldown_seconds:
                return False
        
        # Check max per hour
        hour_ago = now - timedelta(hours=1)
        recent_triggers = [t for t in self._trigger_history[rule_id] if t > hour_ago]
        
        if len(recent_triggers) >= rule.max_per_hour:
            return False
        
        return True
    
    async def process_event(self, event_data: Dict):
        """
        Process event and trigger matching alerts
        
        Args:
            event_data: Event data dictionary
        """
        for rule in self.rules.values():
            if self._should_trigger(rule, event_data):
                await self._trigger_alert(rule, event_data)
    
    async def _trigger_alert(self, rule: AlertRule, event_data: Dict):
        """Trigger alert for rule"""
        # Update trigger history
        now = datetime.now()
        rule.last_triggered = now
        
        if rule.id not in self._trigger_history:
            self._trigger_history[rule.id] = []
        self._trigger_history[rule.id].append(now)
        
        # Render templates
        subject = Template(rule.subject_template).render(**event_data)
        body = Template(rule.body_template).render(**event_data)
        
        # Create notifications for each channel and recipient
        for channel in rule.channels:
            for recipient in rule.recipients:
                notification = Notification(
                    id=f"{rule.id}_{now.timestamp()}",
                    alert_rule_id=rule.id,
                    channel=channel,
                    recipient=recipient,
                    subject=subject,
                    body=body,
                    priority=rule.priority,
                    timestamp=now,
                    data=event_data
                )
                
                # Queue for delivery
                await self.notification_queue.put(notification)
        
        logger.info(f"Alert triggered: {rule.name}")
    
    async def start_delivery_worker(self):
        """Start background worker for notification delivery"""
        while True:
            try:
                notification = await self.notification_queue.get()
                
                # Get notifier for channel
                notifier = self.notifiers.get(notification.channel)
                
                if notifier:
                    success = await notifier.send(notification)
                    
                    notification.delivered = success
                    notification.delivery_time = datetime.now()
                else:
                    logger.error(f"No notifier registered for {notification.channel}")
                    notification.error = "No notifier registered"
                
                # Store delivery history
                self.delivery_history.append(notification)
                
                # Limit history size
                if len(self.delivery_history) > 1000:
                    self.delivery_history = self.delivery_history[-1000:]
            
            except Exception as e:
                logger.error(f"Error in delivery worker: {e}")
    
    def get_statistics(self) -> Dict:
        """Get alert statistics"""
        total_delivered = sum(1 for n in self.delivery_history if n.delivered)
        total_failed = len(self.delivery_history) - total_delivered
        
        by_channel = {}
        for notification in self.delivery_history:
            channel = notification.channel.value
            if channel not in by_channel:
                by_channel[channel] = {'delivered': 0, 'failed': 0}
            
            if notification.delivered:
                by_channel[channel]['delivered'] += 1
            else:
                by_channel[channel]['failed'] += 1
        
        return {
            'total_rules': len(self.rules),
            'active_rules': sum(1 for r in self.rules.values() if r.enabled),
            'total_delivered': total_delivered,
            'total_failed': total_failed,
            'by_channel': by_channel,
            'recent_alerts': [
                {
                    'rule_name': self.rules[n.alert_rule_id].name,
                    'channel': n.channel.value,
                    'delivered': n.delivered,
                    'timestamp': n.timestamp.isoformat()
                }
                for n in self.delivery_history[-10:]
            ]
        }


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def main():
        logging.basicConfig(level=logging.INFO)
        
        # Initialize alert manager
        manager = AlertManager()
        
        # Register notifiers
        email_notifier = EmailNotifier(
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            username="your_email@gmail.com",
            password="your_password",
            from_email="surveillance@example.com"
        )
        
        manager.register_notifier(NotificationChannel.EMAIL, email_notifier)
        
        # Add alert rule
        rule = AlertRule(
            id="motion_alert_night",
            name="Motion Detection at Night",
            event_types=["motion_detected"],
            time_range={"start": "22:00", "end": "06:00"},
            channels=[NotificationChannel.EMAIL],
            recipients=["admin@example.com"],
            subject_template="Motion Detected: {camera_id}",
            body_template="Motion was detected on camera {camera_id} at {timestamp}"
        )
        
        manager.add_rule(rule)
        
        # Start delivery worker
        asyncio.create_task(manager.start_delivery_worker())
        
        # Simulate event
        await manager.process_event({
            'event_type': 'motion_detected',
            'camera_id': 'camera_1',
            'timestamp': datetime.now().isoformat(),
            'confidence': 0.95
        })
        
        # Wait for delivery
        await asyncio.sleep(5)
        
        # Get statistics
        stats = manager.get_statistics()
        print(json.dumps(stats, indent=2))
    
    asyncio.run(main())