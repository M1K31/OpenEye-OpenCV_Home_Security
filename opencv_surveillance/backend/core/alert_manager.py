# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Alert Manager - Coordinates alert triggering and notification sending
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from backend.services.notification_service import get_notification_service
from backend.database import alert_models
from backend.database.session import SessionLocal
from backend.database.utils import get_db_context

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Manages alert triggering, throttling, and notification sending
    """

    def __init__(self):
        self.notification_service = get_notification_service()
        logger.info("AlertManager initialized")

    def _should_send_alert(
        self, db: Session, throttle_key: str, min_seconds: int = 300
    ) -> bool:
        """
        Check if enough time has passed since last alert

        Args:
            db: Database session
            throttle_key: Unique key for this alert type
            min_seconds: Minimum seconds between alerts

        Returns:
            True if alert should be sent, False if throttled
        """
        throttle = (
            db.query(alert_models.AlertThrottle)
            .filter(alert_models.AlertThrottle.throttle_key == throttle_key)
            .first()
        )

        now = datetime.utcnow()

        if not throttle:
            # First time seeing this alert - create throttle entry
            throttle = alert_models.AlertThrottle(
                throttle_key=throttle_key, last_alert_time=now, alert_count=1
            )
            db.add(throttle)
            db.commit()
            return True

        # Check if enough time has passed
        time_since_last = (now - throttle.last_alert_time).total_seconds()

        if time_since_last >= min_seconds:
            # Enough time has passed - update and allow
            throttle.last_alert_time = now
            throttle.alert_count += 1
            db.commit()
            return True

        # Too soon - throttle
        logger.info(f"Alert throttled: {throttle_key} (last sent {time_since_last:.0f}s ago)")
        return False

    def _is_quiet_hours(self, config: alert_models.AlertConfiguration) -> bool:
        """
        Check if current time is within quiet hours

        Args:
            config: Alert configuration with quiet hours settings

        Returns:
            True if in quiet hours, False otherwise
        """
        if not config.quiet_hours_enabled:
            return False

        now = datetime.now().time()

        try:
            start_time = datetime.strptime(
                config.quiet_hours_start, "%H:%M").time()
            end_time = datetime.strptime(
                config.quiet_hours_end, "%H:%M").time()

            # Handle overnight quiet hours (e.g., 22:00 to 07:00)
            if start_time > end_time:
                return now >= start_time or now <= end_time
            else:
                return start_time <= now <= end_time

        except Exception as e:
            logger.error(f"Error parsing quiet hours: {e}")
            return False

    async def trigger_motion_alert(
        self, camera_id: str, event_data: Optional[Dict[str, Any]] = None
    ):
        """
        Trigger a motion detection alert

        Args:
            camera_id: ID of the camera that detected motion
            event_data: Additional event data
        """
        # FIXED: Use context manager to prevent session leak (v3.6.0.1)
        with get_db_context() as db:
            # Get all alert configurations
            configs = (
                db.query(alert_models.AlertConfiguration)
                .filter(alert_models.AlertConfiguration.motion_alerts_enabled)
                .all()
            )

            for config in configs:
                # Check throttling
                throttle_key = f"motion_{camera_id}"
                if not self._should_send_alert(
                    db, throttle_key, config.min_seconds_between_alerts
                ):
                    continue

                # Check quiet hours
                if self._is_quiet_hours(config):
                    logger.info(f"Motion alert skipped due to quiet hours")
                    continue

                # Send notifications via enabled channels
                await self._send_notifications(
                    db=db,
                    config=config,
                    event_type="motion",
                    camera_id=camera_id,
                    subject="Motion Detected",
                    message=f"Motion detected on camera {camera_id}",
                    event_data=event_data,
                )

    async def trigger_face_recognition_alert(
        self,
        camera_id: str,
        person_name: str,
        confidence: float,
        is_known: bool,
        event_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Trigger a face recognition alert

        Args:
            camera_id: ID of the camera
            person_name: Name of recognized person (or "Unknown")
            confidence: Recognition confidence (0.0 - 1.0)
            is_known: True if person is in database
            event_data: Additional event data
        """
        db = self._get_db()
        try:
            # Determine which alert type to trigger
            if is_known:
                event_type = "face_known"
                configs = (
                    db.query(alert_models.AlertConfiguration)
                    .filter(
                        alert_models.AlertConfiguration.face_recognition_alerts_enabled

                    )
                    .all()
                )
                subject = f"Known Person Detected: {person_name}"
                message = f"{person_name} detected on camera {camera_id} (confidence: {confidence:.1%})"
            else:
                event_type = "face_unknown"
                configs = (
                    db.query(alert_models.AlertConfiguration)
                    .filter(
                        alert_models.AlertConfiguration.unknown_face_alerts_enabled

                    )
                    .all()
                )
                subject = "Unknown Person Detected"
                message = f"Unknown person detected on camera {camera_id}"

            for config in configs:
                # Check throttling
                throttle_key = f"{event_type}_{person_name}_{camera_id}"
                if not self._should_send_alert(
                    db, throttle_key, config.min_seconds_between_alerts
                ):
                    continue

                # Check quiet hours
                if self._is_quiet_hours(config):
                    continue

                # Send notifications
                await self._send_notifications(
                    db=db,
                    config=config,
                    event_type=event_type,
                    camera_id=camera_id,
                    subject=subject,
                    message=message,
                    event_data=event_data or {},
                )

        finally:
            db.close()

    async def trigger_recording_alert(
        self,
        camera_id: str,
        recording_started: bool,
        event_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Trigger a recording event alert

        Args:
            camera_id: ID of the camera
            recording_started: True if recording started, False if stopped
            event_data: Additional event data
        """
        db = self._get_db()
        try:
            configs = (
                db.query(alert_models.AlertConfiguration)
                .filter(
                    alert_models.AlertConfiguration.recording_alerts_enabled
                )
                .all()
            )

            event_type = "recording_started" if recording_started else "recording_stopped"
            status_text = 'Started' if recording_started else 'Stopped'
            action_text = 'started' if recording_started else 'stopped'
            subject = f"Recording {status_text}"
            message = f"Camera {camera_id} {action_text} recording"

            for config in configs:
                throttle_key = f"{event_type}_{camera_id}"
                if not self._should_send_alert(
                    db, throttle_key, 60
                ):  # 1 minute throttle
                    continue

                if self._is_quiet_hours(config):
                    continue

                await self._send_notifications(
                    db=db,
                    config=config,
                    event_type=event_type,
                    camera_id=camera_id,
                    subject=subject,
                    message=message,
                    event_data=event_data,
                )

        finally:
            db.close()

    async def trigger_object_detection_alert(
        self,
        camera_id: str,
        object_class: str,
        object_subclass: Optional[str] = None,
        identified_object_name: Optional[str] = None,
        confidence: float = 0.0,
        event_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Trigger an object detection alert

        Args:
            camera_id: ID of the camera
            object_class: Object class (vehicle, animal, package, person)
            object_subclass: Specific object type (car, dog, backpack, etc.)
            identified_object_name: Name of identified object (e.g., "John's Tesla", "My Dog Rex")
            confidence: Detection confidence (0.0 - 1.0)
            event_data: Additional event data
        """
        # Use context manager to prevent session leak
        with get_db_context() as db:
            # Start with master toggle check
            configs = (
                db.query(alert_models.AlertConfiguration)
                .filter(alert_models.AlertConfiguration.object_detection_alerts_enabled)
                .all()
            )

            if not configs:
                return

            # Build subject and message based on detection type
            if identified_object_name:
                # Identified object alert
                event_type = f"object_identified_{object_class}"
                subject = f"Identified Object Detected: {identified_object_name}"
                message = f"{identified_object_name} ({object_class}) detected on camera {camera_id}"
                if confidence > 0:
                    message += f" (confidence: {confidence:.1%})"
            else:
                # Generic class-based alert
                event_type = f"object_{object_class}"
                object_label = object_subclass or object_class
                subject = f"{object_label.title()} Detected"
                message = f"{object_label.title()} detected on camera {camera_id}"
                if confidence > 0:
                    message += f" (confidence: {confidence:.1%})"

            for config in configs:
                # Check class-specific toggles
                should_alert = False

                if identified_object_name and config.identified_object_alerts_enabled:
                    # Identified object takes precedence
                    should_alert = True
                elif object_class == 'vehicle' and config.vehicle_alerts_enabled:
                    should_alert = True
                elif object_class == 'animal' and config.animal_alerts_enabled:
                    should_alert = True
                elif object_class == 'package' and config.package_alerts_enabled:
                    should_alert = True

                if not should_alert:
                    continue

                # Build throttle key
                if identified_object_name:
                    # Throttle per identified object
                    throttle_key = f"object_identified_{identified_object_name}_{camera_id}"
                else:
                    # Throttle per class
                    throttle_key = f"object_{object_class}_{camera_id}"

                # Check throttling
                if not self._should_send_alert(
                    db, throttle_key, config.min_seconds_between_alerts
                ):
                    continue

                # Check quiet hours
                if self._is_quiet_hours(config):
                    logger.info(f"Object detection alert skipped due to quiet hours")
                    continue

                # Send notifications via enabled channels
                await self._send_notifications(
                    db=db,
                    config=config,
                    event_type=event_type,
                    camera_id=camera_id,
                    subject=subject,
                    message=message,
                    event_data=event_data or {},
                )

    async def _send_notifications(
        self,
        db: Session,
        config: alert_models.AlertConfiguration,
        event_type: str,
        camera_id: str,
        subject: str,
        message: str,
        event_data: Dict[str, Any],
    ):
        """
        Send notifications via all enabled channels

        Args:
            db: Database session
            config: Alert configuration
            event_type: Type of event
            camera_id: Camera ID
            subject: Notification subject
            message: Notification message
            event_data: Additional event data
        """
        timestamp = datetime.utcnow()

        # Email
        if config.email_enabled and config.email_address:
            success, error = await self.notification_service.send_email(
                to_address=config.email_address,
                subject=f"[OpenEye] {subject}",
                body=f"{message}\n\nTime: {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}\nCamera: {camera_id}",
            )

            # Log notification
            log = alert_models.NotificationLog(
                event_type=event_type,
                camera_id=camera_id,
                channel="email",
                recipient=config.email_address,
                subject=subject,
                message=message,
                event_data=event_data,
                sent_successfully=success,
                error_message=error,
                sent_at=timestamp if success else None,
            )
            db.add(log)

        # SMS
        if config.sms_enabled and config.phone_number:
            sms_message = f"[OpenEye] {subject}: {message}"
            success, error = self.notification_service.send_sms(
                to_number=config.phone_number, message=sms_message
            )

            log = alert_models.NotificationLog(
                event_type=event_type,
                camera_id=camera_id,
                channel="sms",
                recipient=config.phone_number,
                subject=subject,
                message=sms_message,
                event_data=event_data,
                sent_successfully=success,
                error_message=error,
                sent_at=timestamp if success else None,
            )
            db.add(log)

        # Push notification
        if config.push_enabled and config.push_token:
            success, error = await self.notification_service.send_push_notification(
                token=config.push_token,
                title=subject,
                body=message,
                data={"camera_id": camera_id, "event_type": event_type},
            )

            log = alert_models.NotificationLog(
                event_type=event_type,
                camera_id=camera_id,
                channel="push",
                recipient=config.push_token[:20] + "...",  # Truncate token
                subject=subject,
                message=message,
                event_data=event_data,
                sent_successfully=success,
                error_message=error,
                sent_at=timestamp if success else None,
            )
            db.add(log)

        # Webhook
        if config.webhook_enabled and config.webhook_url:
            payload = {
                "event_type": event_type,
                "camera_id": camera_id,
                "subject": subject,
                "message": message,
                "timestamp": timestamp.isoformat(),
                "data": event_data,
            }

            success, error = await self.notification_service.send_webhook(
                webhook_url=config.webhook_url, payload=payload
            )

            log = alert_models.NotificationLog(
                event_type=event_type,
                camera_id=camera_id,
                channel="webhook",
                recipient=config.webhook_url,
                subject=subject,
                message=message,
                event_data=event_data,
                sent_successfully=success,
                error_message=error,
                sent_at=timestamp if success else None,
            )
            db.add(log)

        db.commit()


# Global singleton instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get or create the global alert manager instance"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
