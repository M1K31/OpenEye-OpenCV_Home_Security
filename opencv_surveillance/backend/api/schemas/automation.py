#!/usr/bin/env python3
# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security
"""
Pydantic schemas for automation rules API

Defines request/response schemas for person-based automation rules.
Supports flexible conditions (cameras, time ranges, confidence thresholds)
and multiple action types (notifications, recordings, webhooks, alerts).
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


# ============================================================
# Action Schemas
# ============================================================

class ActionSchema(BaseModel):
    """Schema for an automation action"""
    type: str = Field(..., description="Action type: notification, record, webhook, alert")
    config: Dict[str, Any] = Field(default_factory=dict, description="Action-specific configuration")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "type": "notification",
                    "config": {
                        "message": "John detected at front door",
                        "priority": "high"
                    }
                },
                {
                    "type": "record",
                    "config": {
                        "duration": 30,
                        "pre_buffer": 5
                    }
                },
                {
                    "type": "webhook",
                    "config": {
                        "url": "https://example.com/webhook",
                        "method": "POST",
                        "headers": {"Authorization": "Bearer token"}
                    }
                }
            ]
        }


# ============================================================
# Condition Schemas
# ============================================================

class ConditionSchema(BaseModel):
    """Schema for automation rule conditions"""
    cameras: Optional[List[str]] = Field(None, description="Camera IDs to filter on")
    time_range: Optional[Dict[str, str]] = Field(None, description="Time range (start/end HH:MM)")
    confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum face confidence")
    days_of_week: Optional[List[int]] = Field(None, description="Days to activate (0=Monday, 6=Sunday)")
    
    @validator('time_range')
    def validate_time_range(cls, v):
        """Validate time range format"""
        if v is not None:
            if 'start' not in v or 'end' not in v:
                raise ValueError("time_range must have 'start' and 'end' keys")
            # Basic HH:MM validation
            for key in ['start', 'end']:
                time_str = v[key]
                try:
                    hours, minutes = time_str.split(':')
                    h, m = int(hours), int(minutes)
                    if not (0 <= h < 24 and 0 <= m < 60):
                        raise ValueError
                except (ValueError, AttributeError):
                    raise ValueError(f"Invalid time format for {key}: {time_str}. Use HH:MM")
        return v
    
    @validator('days_of_week')
    def validate_days_of_week(cls, v):
        """Validate days of week are 0-6"""
        if v is not None:
            for day in v:
                if not 0 <= day <= 6:
                    raise ValueError("days_of_week must be integers 0-6 (0=Monday)")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "cameras": ["front_door", "driveway"],
                "time_range": {"start": "08:00", "end": "18:00"},
                "confidence_threshold": 0.85,
                "days_of_week": [0, 1, 2, 3, 4]  # Monday-Friday
            }
        }


# ============================================================
# Base Automation Rule Schemas
# ============================================================

class AutomationRuleBase(BaseModel):
    """Base schema for automation rules"""
    name: str = Field(..., min_length=1, max_length=255, description="Rule name")
    person_name: str = Field(..., min_length=1, description="Person to trigger on")
    enabled: bool = Field(True, description="Whether rule is active")
    conditions: Optional[ConditionSchema] = Field(None, description="Trigger conditions")
    actions: List[ActionSchema] = Field(..., min_items=1, description="Actions to execute")
    cooldown_seconds: int = Field(300, ge=0, description="Cooldown period (default 5 minutes)")


class AutomationRuleCreate(AutomationRuleBase):
    """Schema for creating a new automation rule"""
    pass


class AutomationRuleUpdate(BaseModel):
    """Schema for updating an automation rule"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    person_name: Optional[str] = Field(None, min_length=1)
    enabled: Optional[bool] = None
    conditions: Optional[ConditionSchema] = None
    actions: Optional[List[ActionSchema]] = Field(None, min_items=1)
    cooldown_seconds: Optional[int] = Field(None, ge=0)


class AutomationRuleResponse(AutomationRuleBase):
    """Schema for automation rule responses"""
    id: int
    last_triggered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    trigger_count: int = 0
    
    class Config:
        from_attributes = True  # Enable ORM mode for SQLAlchemy models


# ============================================================
# List and Statistics Schemas
# ============================================================

class AutomationRuleList(BaseModel):
    """Schema for list of automation rules"""
    rules: List[AutomationRuleResponse]
    total: int


class AutomationRuleStats(BaseModel):
    """Schema for automation rule statistics"""
    total_rules: int
    enabled_rules: int
    disabled_rules: int
    total_triggers: int
    rules_by_person: Dict[str, int]


# ============================================================
# Test Execution Schemas
# ============================================================

class AutomationTestRequest(BaseModel):
    """Schema for testing an automation rule manually"""
    camera_id: Optional[str] = Field(None, description="Camera ID to simulate detection from")
    confidence: float = Field(0.95, ge=0.0, le=1.0, description="Simulated confidence score")
    skip_cooldown: bool = Field(False, description="Skip cooldown check for testing")


class AutomationTestResponse(BaseModel):
    """Schema for automation test execution response"""
    success: bool
    message: str
    conditions_met: bool
    cooldown_active: bool
    actions_executed: List[Dict[str, Any]]
    errors: Optional[List[str]] = None
