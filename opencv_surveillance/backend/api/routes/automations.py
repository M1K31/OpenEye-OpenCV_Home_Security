#!/usr/bin/env python3
# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
API routes for automation rules management

Provides CRUD operations and statistics for person-based automation rules.
Rules trigger actions (notifications, recordings, webhooks) when specific
people are detected by the face recognition system.
"""

import json
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.session import get_db
from backend.database import models
from backend.api.schemas.automation import (
    AutomationRuleCreate,
    AutomationRuleUpdate,
    AutomationRuleResponse,
    AutomationRuleList,
    AutomationRuleStats,
    AutomationTestRequest,
    AutomationTestResponse,
)
from backend.core.auth import get_current_active_user
from backend.api.schemas import user as user_schema

router = APIRouter(prefix="/automations", tags=["Automations"])


# ============================================================
# Helper Functions
# ============================================================

def serialize_conditions(conditions):
    """Convert ConditionSchema to JSON string"""
    if conditions is None:
        return None
    return json.dumps(conditions.dict(exclude_none=True))


def serialize_actions(actions):
    """Convert list of ActionSchema to JSON string"""
    return json.dumps([action.dict() for action in actions])


def deserialize_conditions(conditions_str):
    """Convert JSON string to dict"""
    if not conditions_str:
        return None
    return json.loads(conditions_str)


def deserialize_actions(actions_str):
    """Convert JSON string to list"""
    return json.loads(actions_str)


# ============================================================
# CRUD Endpoints
# ============================================================

@router.get("/", response_model=AutomationRuleList)
def list_automation_rules(
    person_name: Optional[str] = Query(None, description="Filter by person name"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(get_current_active_user),
):
    """
    List automation rules with optional filtering.
    
    - **person_name**: Filter rules for specific person
    - **enabled**: Filter by enabled/disabled status
    - **skip**: Pagination offset
    - **limit**: Maximum results to return
    """
    # Build query
    query = db.query(models.AutomationRule)
    
    # Apply filters
    if person_name:
        query = query.filter(models.AutomationRule.person_name == person_name)
    if enabled is not None:
        query = query.filter(models.AutomationRule.enabled == enabled)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    rules = query.offset(skip).limit(limit).all()
    
    return AutomationRuleList(rules=rules, total=total)


@router.post("/", response_model=AutomationRuleResponse, status_code=201)
def create_automation_rule(
    rule: AutomationRuleCreate,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(get_current_active_user),
):
    """
    Create a new automation rule.
    
    The rule will trigger the specified actions when the person is detected
    and all conditions are met. A cooldown period prevents spam.
    """
    # Create new rule
    db_rule = models.AutomationRule(
        name=rule.name,
        person_name=rule.person_name,
        enabled=rule.enabled,
        conditions=serialize_conditions(rule.conditions),
        actions=serialize_actions(rule.actions),
        cooldown_seconds=rule.cooldown_seconds,
    )
    
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    
    return db_rule


@router.get("/{rule_id}", response_model=AutomationRuleResponse)
def get_automation_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(get_current_active_user),
):
    """Get a specific automation rule by ID"""
    rule = db.query(models.AutomationRule).filter(
        models.AutomationRule.id == rule_id
    ).first()
    
    if not rule:
        raise HTTPException(status_code=404, detail=f"Automation rule {rule_id} not found")
    
    return rule


@router.put("/{rule_id}", response_model=AutomationRuleResponse)
def update_automation_rule(
    rule_id: int,
    rule_update: AutomationRuleUpdate,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(get_current_active_user),
):
    """
    Update an automation rule.
    
    Only provided fields will be updated. Omitted fields remain unchanged.
    """
    # Get existing rule
    db_rule = db.query(models.AutomationRule).filter(
        models.AutomationRule.id == rule_id
    ).first()
    
    if not db_rule:
        raise HTTPException(status_code=404, detail=f"Automation rule {rule_id} not found")
    
    # Update fields
    update_data = rule_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if field == "conditions" and value is not None:
            setattr(db_rule, field, serialize_conditions(value))
        elif field == "actions" and value is not None:
            setattr(db_rule, field, serialize_actions(value))
        else:
            setattr(db_rule, field, value)
    
    # Update timestamp
    db_rule.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_rule)
    
    return db_rule


@router.delete("/{rule_id}", status_code=204)
def delete_automation_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(get_current_active_user),
):
    """Delete an automation rule"""
    rule = db.query(models.AutomationRule).filter(
        models.AutomationRule.id == rule_id
    ).first()
    
    if not rule:
        raise HTTPException(status_code=404, detail=f"Automation rule {rule_id} not found")
    
    db.delete(rule)
    db.commit()
    
    return None


@router.patch("/{rule_id}/toggle", response_model=AutomationRuleResponse)
def toggle_automation_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(get_current_active_user),
):
    """Toggle an automation rule enabled/disabled state"""
    rule = db.query(models.AutomationRule).filter(
        models.AutomationRule.id == rule_id
    ).first()
    
    if not rule:
        raise HTTPException(status_code=404, detail=f"Automation rule {rule_id} not found")
    
    # Toggle enabled state
    rule.enabled = not rule.enabled
    rule.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(rule)
    
    return rule


# ============================================================
# Statistics Endpoints
# ============================================================

@router.get("/stats/summary", response_model=AutomationRuleStats)
def get_automation_stats(
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(get_current_active_user),
):
    """
    Get automation rule statistics.
    
    Returns counts of total rules, enabled/disabled rules, total triggers,
    and breakdown by person.
    """
    # Total rules
    total_rules = db.query(models.AutomationRule).count()
    
    # Enabled/disabled counts
    enabled_rules = db.query(models.AutomationRule).filter(
        models.AutomationRule.enabled == True
    ).count()
    disabled_rules = total_rules - enabled_rules
    
    # Total triggers across all rules
    total_triggers = db.query(
        func.sum(models.AutomationRule.trigger_count)
    ).scalar() or 0
    
    # Rules by person
    person_counts = db.query(
        models.AutomationRule.person_name,
        func.count(models.AutomationRule.id)
    ).group_by(models.AutomationRule.person_name).all()
    
    rules_by_person = {person: count for person, count in person_counts}
    
    return AutomationRuleStats(
        total_rules=total_rules,
        enabled_rules=enabled_rules,
        disabled_rules=disabled_rules,
        total_triggers=total_triggers,
        rules_by_person=rules_by_person
    )


@router.post("/{rule_id}/reset-cooldown", response_model=AutomationRuleResponse)
def reset_rule_cooldown(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(get_current_active_user),
):
    """
    Reset the cooldown period for a rule.
    
    This clears the last_triggered_at timestamp, allowing the rule to
    trigger immediately on the next matching detection.
    """
    rule = db.query(models.AutomationRule).filter(
        models.AutomationRule.id == rule_id
    ).first()
    
    if not rule:
        raise HTTPException(status_code=404, detail=f"Automation rule {rule_id} not found")
    
    rule.last_triggered_at = None
    rule.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(rule)
    
    return rule


# ============================================================
# Testing Endpoint
# ============================================================

@router.post("/{rule_id}/test", response_model=AutomationTestResponse)
def test_automation_rule(
    rule_id: int,
    test_request: AutomationTestRequest,
    db: Session = Depends(get_db),
    current_user: user_schema.User = Depends(get_current_active_user),
):
    """
    Test an automation rule without executing actions.
    
    This endpoint simulates a face detection event and checks if the rule
    would trigger. Useful for debugging rule conditions.
    
    Note: This endpoint does NOT actually execute actions. It only validates
    that conditions are met and returns what actions would be executed.
    """
    from backend.core.automation_engine import evaluate_rule_conditions
    
    rule = db.query(models.AutomationRule).filter(
        models.AutomationRule.id == rule_id
    ).first()
    
    if not rule:
        raise HTTPException(status_code=404, detail=f"Automation rule {rule_id} not found")
    
    # Check if rule is enabled
    if not rule.enabled:
        return AutomationTestResponse(
            success=False,
            message="Rule is disabled",
            conditions_met=False,
            cooldown_active=False,
            actions_executed=[]
        )
    
    # Check cooldown (unless skip_cooldown is True)
    cooldown_active = False
    if not test_request.skip_cooldown and rule.last_triggered_at:
        from datetime import timedelta
        cooldown_until = rule.last_triggered_at + timedelta(seconds=rule.cooldown_seconds)
        if datetime.utcnow() < cooldown_until:
            cooldown_active = True
            remaining = (cooldown_until - datetime.utcnow()).total_seconds()
            return AutomationTestResponse(
                success=False,
                message=f"Cooldown active ({remaining:.0f}s remaining)",
                conditions_met=True,
                cooldown_active=True,
                actions_executed=[]
            )
    
    # Evaluate conditions
    conditions = deserialize_conditions(rule.conditions)
    conditions_met = evaluate_rule_conditions(
        conditions,
        camera_id=test_request.camera_id,
        confidence=test_request.confidence
    )
    
    if not conditions_met:
        return AutomationTestResponse(
            success=False,
            message="Conditions not met",
            conditions_met=False,
            cooldown_active=False,
            actions_executed=[]
        )
    
    # Get actions that would be executed
    actions = deserialize_actions(rule.actions)
    
    return AutomationTestResponse(
        success=True,
        message="Rule would trigger",
        conditions_met=True,
        cooldown_active=False,
        actions_executed=actions
    )
