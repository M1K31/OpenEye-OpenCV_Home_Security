#!/usr/bin/env python3
# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Automation Rule Execution Engine

Evaluates automation rules when face detection events occur and executes
configured actions (notifications, recordings, webhooks, alerts).

This module integrates with the face detection system to automatically
trigger actions based on person-specific rules and conditions.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from backend.database.session import SessionLocal
from backend.database import models

logger = logging.getLogger(__name__)


# ============================================================
# Condition Evaluation
# ============================================================

def evaluate_rule_conditions(
    conditions: Optional[Dict[str, Any]],
    camera_id: Optional[str] = None,
    confidence: float = 0.0,
    detected_at: Optional[datetime] = None
) -> bool:
    """
    Evaluate if all rule conditions are met.
    
    Args:
        conditions: Dictionary of conditions to check
        camera_id: Camera that detected the person
        confidence: Face detection confidence (0.0-1.0)
        detected_at: Timestamp of detection
    
    Returns:
        True if all conditions are met (or no conditions defined)
    """
    if not conditions:
        # No conditions means always trigger
        return True
    
    detected_at = detected_at or datetime.utcnow()
    
    # Check camera filter
    if 'cameras' in conditions and conditions['cameras']:
        if camera_id not in conditions['cameras']:
            logger.debug(f"Camera {camera_id} not in allowed cameras: {conditions['cameras']}")
            return False
    
    # Check confidence threshold
    if 'confidence_threshold' in conditions:
        threshold = conditions['confidence_threshold']
        if confidence < threshold:
            logger.debug(f"Confidence {confidence} below threshold {threshold}")
            return False
    
    # Check time range
    if 'time_range' in conditions and conditions['time_range']:
        time_range = conditions['time_range']
        current_time = detected_at.time()
        
        # Parse start and end times
        start_time = datetime.strptime(time_range['start'], '%H:%M').time()
        end_time = datetime.strptime(time_range['end'], '%H:%M').time()
        
        # Check if current time is within range
        if start_time <= end_time:
            # Normal range (e.g., 08:00 - 18:00)
            if not (start_time <= current_time <= end_time):
                logger.debug(f"Time {current_time} outside range {start_time}-{end_time}")
                return False
        else:
            # Overnight range (e.g., 22:00 - 06:00)
            if not (current_time >= start_time or current_time <= end_time):
                logger.debug(f"Time {current_time} outside overnight range {start_time}-{end_time}")
                return False
    
    # Check days of week
    if 'days_of_week' in conditions and conditions['days_of_week']:
        current_day = detected_at.weekday()  # 0=Monday, 6=Sunday
        if current_day not in conditions['days_of_week']:
            logger.debug(f"Day {current_day} not in allowed days: {conditions['days_of_week']}")
            return False
    
    # All conditions met
    return True


# ============================================================
# Action Execution
# ============================================================

def execute_notification_action(
    action_config: Dict[str, Any],
    person_name: str,
    camera_id: str,
    rule_id: Optional[int] = None
) -> Dict[str, Any]:
    """Send a real notification through the user's configured providers.

    Optional action_config keys:
      providers: list of provider type/name/id strings (None = all enabled)
      cooldown_seconds: throttle repeats of THIS notification (0 = off).
        Distinct from the whole-rule cooldown — recordings/alerts still run.
    """
    message = action_config.get('message', f'{person_name} detected')
    priority = action_config.get('priority', 'normal')
    providers = action_config.get('providers')
    cooldown = int(action_config.get('cooldown_seconds', 0) or 0)

    from backend.core import notification_dispatch
    queued = notification_dispatch.dispatch_from_thread(
        message=message,
        title=f"OpenEye: {person_name} detected",
        priority=priority,
        event_type="automation",
        camera_id=camera_id,
        person_name=person_name,
        target_providers=providers,
        cooldown_key=("rule", rule_id, camera_id, person_name),
        cooldown_seconds=cooldown,
    )
    logger.info(f"NOTIFICATION [{priority}] {message} (queued={queued})")
    return {
        "type": "notification",
        "success": bool(queued),
        "queued": bool(queued),
        "message": message,
        "priority": priority,
    }


def execute_record_action(
    action_config: Dict[str, Any],
    person_name: str,
    camera_id: str
) -> Dict[str, Any]:
    """Request a recording on the detecting camera.

    Opens a manual-record window on the running camera; the existing recorder
    pipeline produces the file + DB metadata when the window closes. Not
    subject to notification cooldown — footage is never dropped.
    """
    duration = int(action_config.get('duration', 30) or 30)

    from backend.core.camera_manager import CameraManager
    camera = CameraManager().get_camera(camera_id)
    if camera is None:
        logger.warning(f"Record action: camera '{camera_id}' is not running")
        return {"type": "record", "success": False,
                "error": f"camera '{camera_id}' not running"}

    camera.request_recording(duration)
    logger.info(f"RECORD {duration}s on {camera_id} (person: {person_name})")
    return {"type": "record", "success": True, "camera_id": camera_id,
            "duration": duration, "recording_requested": True}


def execute_webhook_action(
    action_config: Dict[str, Any],
    person_name: str,
    camera_id: str
) -> Dict[str, Any]:
    """Execute a webhook action"""
    import requests
    
    url = action_config.get('url')
    method = action_config.get('method', 'POST').upper()
    headers = action_config.get('headers', {})
    
    if not url:
        logger.error("Webhook action missing URL")
        return {
            "type": "webhook",
            "success": False,
            "error": "Missing URL"
        }
    
    # Prepare payload
    payload = {
        "person_name": person_name,
        "camera_id": camera_id,
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": "person_detected"
    }
    
    try:
        logger.info(f"🌐 WEBHOOK: {method} {url}")
        
        if method == 'GET':
            response = requests.get(url, headers=headers, params=payload, timeout=10)
        else:
            response = requests.request(
                method,
                url,
                json=payload,
                headers=headers,
                timeout=10
            )
        
        response.raise_for_status()
        
        return {
            "type": "webhook",
            "success": True,
            "url": url,
            "status_code": response.status_code
        }
    
    except Exception as e:
        logger.error(f"Webhook failed: {e}")
        return {
            "type": "webhook",
            "success": False,
            "error": str(e)
        }


def execute_alert_action(
    action_config: Dict[str, Any],
    person_name: str,
    camera_id: str,
    db: Any
) -> Dict[str, Any]:
    """Execute an alert action (creates an alert in the database)"""
    message = action_config.get('message', f'{person_name} detected at {camera_id}')
    alert_type = action_config.get('alert_type', 'person_detection')
    
    try:
        # Create alert in database
        alert = models.Alert(
            message=message,
            alert_type=alert_type,
            camera_id=camera_id,
            metadata=json.dumps({
                "person_name": person_name,
                "source": "automation_rule"
            })
        )
        
        db.add(alert)
        db.commit()
        
        logger.info(f"🚨 ALERT: Created alert for {person_name} on {camera_id}")
        
        return {
            "type": "alert",
            "success": True,
            "alert_id": alert.id,
            "message": message
        }
    
    except Exception as e:
        logger.error(f"Alert creation failed: {e}")
        db.rollback()
        return {
            "type": "alert",
            "success": False,
            "error": str(e)
        }


def execute_action(
    action: Dict[str, Any],
    person_name: str,
    camera_id: str,
    db: Any,
    rule_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Execute a single action.

    Args:
        action: Action configuration dict with 'type' and 'config'
        person_name: Name of detected person
        camera_id: Camera that detected the person
        db: Database session
        rule_id: ID of the automation rule (optional)

    Returns:
        Dictionary with execution results
    """
    action_type = action.get('type')
    action_config = action.get('config', {})

    try:
        if action_type == 'notification':
            return execute_notification_action(action_config, person_name, camera_id, rule_id)
        
        elif action_type == 'record':
            return execute_record_action(action_config, person_name, camera_id)
        
        elif action_type == 'webhook':
            return execute_webhook_action(action_config, person_name, camera_id)
        
        elif action_type == 'alert':
            return execute_alert_action(action_config, person_name, camera_id, db)
        
        else:
            logger.warning(f"Unknown action type: {action_type}")
            return {
                "type": action_type,
                "success": False,
                "error": f"Unknown action type: {action_type}"
            }
    
    except Exception as e:
        logger.error(f"Action execution failed: {e}", exc_info=True)
        return {
            "type": action_type,
            "success": False,
            "error": str(e)
        }


# ============================================================
# Main Rule Processing
# ============================================================

def process_face_detection(
    person_name: str,
    camera_id: str,
    confidence: float,
    detected_at: Optional[datetime] = None
):
    """
    Process a face detection event and execute matching automation rules.
    
    This function is called by the face detection system when a person is
    identified. It finds all enabled rules for that person, checks conditions,
    manages cooldowns, and executes actions.
    
    Args:
        person_name: Name of detected person
        camera_id: Camera that detected the person
        confidence: Face detection confidence (0.0-1.0)
        detected_at: Timestamp of detection (defaults to now)
    """
    detected_at = detected_at or datetime.utcnow()
    
    logger.debug(f"Processing automation rules for {person_name} on {camera_id}")

    # FIXED: Use context manager to prevent session leak (v3.6.0.1)
    from backend.database.utils import get_db_context
    with get_db_context() as db:
        # Find all enabled rules for this person
        rules = db.query(models.AutomationRule).filter(
            models.AutomationRule.person_name == person_name,
            models.AutomationRule.enabled == True
        ).all()

        if not rules:
            logger.debug(f"No automation rules found for {person_name}")
            return

        logger.info(f"Found {len(rules)} automation rule(s) for {person_name}")

        for rule in rules:
            try:
                # Check cooldown
                if rule.last_triggered_at:
                    cooldown_until = rule.last_triggered_at + timedelta(seconds=rule.cooldown_seconds)
                    if datetime.utcnow() < cooldown_until:
                        remaining = (cooldown_until - datetime.utcnow()).total_seconds()
                        logger.debug(
                            f"Rule '{rule.name}' in cooldown ({remaining:.0f}s remaining)"
                        )
                        continue

                # Parse conditions
                conditions = None
                if rule.conditions:
                    conditions = json.loads(rule.conditions)

                # Evaluate conditions
                if not evaluate_rule_conditions(
                    conditions,
                    camera_id=camera_id,
                    confidence=confidence,
                    detected_at=detected_at
                ):
                    logger.debug(f"Rule '{rule.name}' conditions not met")
                    continue

                logger.info(f"✓ Rule '{rule.name}' triggered for {person_name}")

                # Parse and execute actions
                actions = json.loads(rule.actions)
                results = []

                for action in actions:
                    result = execute_action(action, person_name, camera_id, db, rule_id=rule.id)
                    results.append(result)

                # Update rule statistics
                rule.last_triggered_at = datetime.utcnow()
                rule.trigger_count += 1
                rule.updated_at = datetime.utcnow()
                db.commit()

                # Log results
                success_count = sum(1 for r in results if r.get('success'))
                logger.info(
                    f"Rule '{rule.name}' executed {success_count}/{len(results)} actions successfully"
                )

            except Exception as e:
                logger.error(f"Error processing rule '{rule.name}': {e}", exc_info=True)
                db.rollback()
                continue


# ============================================================
# Integration Hook
# ============================================================

def hook_into_face_detection():
    """
    Hook the automation engine into the face detection system.
    
    This function should be called during application startup to register
    the automation processor with face detection events.
    """
    # TODO: Register with face detection event system
    # This would typically involve adding process_face_detection as a callback
    # to be called whenever a face is detected
    
    logger.info("Automation engine initialized")
