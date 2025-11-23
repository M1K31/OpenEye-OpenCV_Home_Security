# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for automation API schemas
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from backend.api.schemas.automation import (
    ActionSchema,
    ConditionSchema,
    AutomationRuleBase,
    AutomationRuleCreate,
    AutomationRuleUpdate,
    AutomationRuleResponse,
    AutomationRuleList,
    AutomationRuleStats,
    AutomationTestRequest,
    AutomationTestResponse,
)


class TestActionSchema:
    """Test ActionSchema"""

    def test_valid_action_schema(self):
        """Test valid action schema"""
        action = ActionSchema(
            type="notification",
            config={"message": "Person detected", "priority": "high"},
        )

        assert action.type == "notification"
        assert action.config["message"] == "Person detected"
        assert action.config["priority"] == "high"

    def test_action_schema_default_config(self):
        """Test action schema with default empty config"""
        action = ActionSchema(type="record")

        assert action.type == "record"
        assert action.config == {}

    def test_action_schema_complex_config(self):
        """Test action schema with complex nested config"""
        action = ActionSchema(
            type="webhook",
            config={
                "url": "https://example.com/webhook",
                "method": "POST",
                "headers": {"Authorization": "Bearer token"},
                "body": {"event": "person_detected"},
            },
        )

        assert action.type == "webhook"
        assert action.config["url"] == "https://example.com/webhook"
        assert action.config["headers"]["Authorization"] == "Bearer token"


class TestConditionSchema:
    """Test ConditionSchema"""

    def test_valid_condition_schema(self):
        """Test valid condition schema"""
        condition = ConditionSchema(
            cameras=["front_door", "driveway"],
            time_range={"start": "08:00", "end": "18:00"},
            confidence_threshold=0.85,
            days_of_week=[0, 1, 2, 3, 4],
        )

        assert condition.cameras == ["front_door", "driveway"]
        assert condition.time_range == {"start": "08:00", "end": "18:00"}
        assert condition.confidence_threshold == 0.85
        assert condition.days_of_week == [0, 1, 2, 3, 4]

    def test_condition_schema_all_optional(self):
        """Test condition schema with all fields None"""
        condition = ConditionSchema()

        assert condition.cameras is None
        assert condition.time_range is None
        assert condition.confidence_threshold is None
        assert condition.days_of_week is None

    def test_time_range_valid_formats(self):
        """Test time_range validator with valid formats"""
        # Valid 24-hour times
        for time_range in [
            {"start": "00:00", "end": "23:59"},
            {"start": "09:30", "end": "17:45"},
            {"start": "12:00", "end": "13:00"},
        ]:
            condition = ConditionSchema(time_range=time_range)
            assert condition.time_range == time_range

    def test_time_range_missing_start_key(self):
        """Test time_range validator rejects missing 'start' key"""
        with pytest.raises(ValidationError) as exc_info:
            ConditionSchema(time_range={"end": "18:00"})

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("time_range",) for error in errors)
        assert any("start" in error["msg"] for error in errors)

    def test_time_range_missing_end_key(self):
        """Test time_range validator rejects missing 'end' key"""
        with pytest.raises(ValidationError) as exc_info:
            ConditionSchema(time_range={"start": "08:00"})

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("time_range",) for error in errors)
        assert any("end" in error["msg"] for error in errors)

    def test_time_range_invalid_hour_format(self):
        """Test time_range validator rejects invalid hour"""
        with pytest.raises(ValidationError) as exc_info:
            ConditionSchema(time_range={"start": "25:00", "end": "18:00"})

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("time_range",) for error in errors)
        assert any("Invalid time format" in error["msg"] for error in errors)

    def test_time_range_invalid_minute_format(self):
        """Test time_range validator rejects invalid minute"""
        with pytest.raises(ValidationError) as exc_info:
            ConditionSchema(time_range={"start": "08:00", "end": "18:60"})

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("time_range",) for error in errors)
        assert any("Invalid time format" in error["msg"] for error in errors)

    def test_time_range_malformed_string(self):
        """Test time_range validator rejects malformed time string"""
        with pytest.raises(ValidationError) as exc_info:
            ConditionSchema(time_range={"start": "8:00am", "end": "6:00pm"})

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("time_range",) for error in errors)

    def test_time_range_missing_colon(self):
        """Test time_range validator rejects time without colon"""
        with pytest.raises(ValidationError) as exc_info:
            ConditionSchema(time_range={"start": "0800", "end": "1800"})

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("time_range",) for error in errors)

    def test_days_of_week_valid_range(self):
        """Test days_of_week validator with valid values"""
        # Valid day ranges
        for days in [[0], [6], [0, 1, 2, 3, 4, 5, 6], [3, 4]]:
            condition = ConditionSchema(days_of_week=days)
            assert condition.days_of_week == days

    def test_days_of_week_invalid_negative(self):
        """Test days_of_week validator rejects negative values"""
        with pytest.raises(ValidationError) as exc_info:
            ConditionSchema(days_of_week=[-1, 0, 1])

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("days_of_week",) for error in errors)
        assert any("0-6" in error["msg"] for error in errors)

    def test_days_of_week_invalid_too_large(self):
        """Test days_of_week validator rejects values > 6"""
        with pytest.raises(ValidationError) as exc_info:
            ConditionSchema(days_of_week=[0, 1, 7])

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("days_of_week",) for error in errors)
        assert any("0-6" in error["msg"] for error in errors)

    def test_confidence_threshold_range(self):
        """Test confidence_threshold must be between 0.0 and 1.0"""
        # Valid values
        for value in [0.0, 0.5, 0.85, 1.0]:
            condition = ConditionSchema(confidence_threshold=value)
            assert condition.confidence_threshold == value

        # Invalid values
        for invalid_value in [-0.1, 1.1]:
            with pytest.raises(ValidationError) as exc_info:
                ConditionSchema(confidence_threshold=invalid_value)

            errors = exc_info.value.errors()
            assert any(error["loc"] == ("confidence_threshold",) for error in errors)


class TestAutomationRuleBase:
    """Test AutomationRuleBase schema"""

    def test_valid_automation_rule_base(self):
        """Test valid automation rule base"""
        rule = AutomationRuleBase(
            name="Alert on John",
            person_name="John",
            enabled=True,
            actions=[
                ActionSchema(type="notification", config={"message": "John detected"})
            ],
            cooldown_seconds=300,
        )

        assert rule.name == "Alert on John"
        assert rule.person_name == "John"
        assert rule.enabled is True
        assert len(rule.actions) == 1
        assert rule.cooldown_seconds == 300

    def test_automation_rule_with_conditions(self):
        """Test automation rule with conditions"""
        rule = AutomationRuleBase(
            name="Weekday alerts",
            person_name="Alice",
            conditions=ConditionSchema(
                cameras=["front_door"],
                time_range={"start": "09:00", "end": "17:00"},
                days_of_week=[0, 1, 2, 3, 4],
            ),
            actions=[ActionSchema(type="record")],
        )

        assert rule.conditions is not None
        assert rule.conditions.cameras == ["front_door"]
        assert rule.conditions.days_of_week == [0, 1, 2, 3, 4]

    def test_name_min_length(self):
        """Test name must have minimum length of 1"""
        with pytest.raises(ValidationError) as exc_info:
            AutomationRuleBase(
                name="",
                person_name="John",
                actions=[ActionSchema(type="notification")],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    def test_name_max_length(self):
        """Test name maximum length of 255"""
        long_name = "a" * 256
        with pytest.raises(ValidationError) as exc_info:
            AutomationRuleBase(
                name=long_name,
                person_name="John",
                actions=[ActionSchema(type="notification")],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    def test_person_name_min_length(self):
        """Test person_name must have minimum length of 1"""
        with pytest.raises(ValidationError) as exc_info:
            AutomationRuleBase(
                name="Test Rule",
                person_name="",
                actions=[ActionSchema(type="notification")],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("person_name",) for error in errors)

    def test_actions_min_items(self):
        """Test actions must have at least one item"""
        with pytest.raises(ValidationError) as exc_info:
            AutomationRuleBase(
                name="Test Rule",
                person_name="John",
                actions=[],
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("actions",) for error in errors)

    def test_cooldown_seconds_non_negative(self):
        """Test cooldown_seconds must be non-negative"""
        # Valid values
        for value in [0, 60, 300, 3600]:
            rule = AutomationRuleBase(
                name="Test",
                person_name="John",
                actions=[ActionSchema(type="notification")],
                cooldown_seconds=value,
            )
            assert rule.cooldown_seconds == value

        # Invalid negative value
        with pytest.raises(ValidationError) as exc_info:
            AutomationRuleBase(
                name="Test",
                person_name="John",
                actions=[ActionSchema(type="notification")],
                cooldown_seconds=-1,
            )

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("cooldown_seconds",) for error in errors)

    def test_default_enabled_true(self):
        """Test enabled defaults to True"""
        rule = AutomationRuleBase(
            name="Test",
            person_name="John",
            actions=[ActionSchema(type="notification")],
        )

        assert rule.enabled is True

    def test_default_cooldown_300(self):
        """Test cooldown_seconds defaults to 300"""
        rule = AutomationRuleBase(
            name="Test",
            person_name="John",
            actions=[ActionSchema(type="notification")],
        )

        assert rule.cooldown_seconds == 300


class TestAutomationRuleCreate:
    """Test AutomationRuleCreate schema"""

    def test_valid_automation_rule_create(self):
        """Test valid automation rule creation"""
        rule = AutomationRuleCreate(
            name="New Rule",
            person_name="Bob",
            actions=[ActionSchema(type="webhook", config={"url": "https://test.com"})],
        )

        assert rule.name == "New Rule"
        assert rule.person_name == "Bob"
        assert len(rule.actions) == 1


class TestAutomationRuleUpdate:
    """Test AutomationRuleUpdate schema"""

    def test_valid_automation_rule_update(self):
        """Test valid automation rule update"""
        update = AutomationRuleUpdate(
            name="Updated Name",
            enabled=False,
            cooldown_seconds=600,
        )

        assert update.name == "Updated Name"
        assert update.enabled is False
        assert update.cooldown_seconds == 600

    def test_automation_rule_update_all_optional(self):
        """Test all fields are optional for update"""
        update = AutomationRuleUpdate()

        assert update.name is None
        assert update.person_name is None
        assert update.enabled is None
        assert update.conditions is None
        assert update.actions is None
        assert update.cooldown_seconds is None

    def test_update_name_min_length(self):
        """Test update name validation"""
        with pytest.raises(ValidationError) as exc_info:
            AutomationRuleUpdate(name="")

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("name",) for error in errors)

    def test_update_actions_min_items(self):
        """Test update actions must have at least one item if provided"""
        with pytest.raises(ValidationError) as exc_info:
            AutomationRuleUpdate(actions=[])

        errors = exc_info.value.errors()
        assert any(error["loc"] == ("actions",) for error in errors)


class TestAutomationRuleResponse:
    """Test AutomationRuleResponse schema"""

    def test_valid_automation_rule_response(self):
        """Test valid automation rule response"""
        now = datetime.now()
        rule = AutomationRuleResponse(
            id=123,
            name="Test Rule",
            person_name="John",
            enabled=True,
            actions=[ActionSchema(type="notification")],
            cooldown_seconds=300,
            created_at=now,
            updated_at=now,
            trigger_count=5,
            last_triggered_at=now,
        )

        assert rule.id == 123
        assert rule.name == "Test Rule"
        assert rule.person_name == "John"
        assert rule.trigger_count == 5
        assert rule.last_triggered_at == now

    def test_automation_rule_response_defaults(self):
        """Test automation rule response with default values"""
        now = datetime.now()
        rule = AutomationRuleResponse(
            id=1,
            name="Test",
            person_name="Alice",
            actions=[ActionSchema(type="record")],
            created_at=now,
            updated_at=now,
        )

        assert rule.trigger_count == 0
        assert rule.last_triggered_at is None
        assert rule.enabled is True
        assert rule.cooldown_seconds == 300


class TestAutomationRuleList:
    """Test AutomationRuleList schema"""

    def test_valid_automation_rule_list(self):
        """Test valid automation rule list"""
        now = datetime.now()
        rules = [
            AutomationRuleResponse(
                id=1,
                name="Rule 1",
                person_name="John",
                actions=[ActionSchema(type="notification")],
                created_at=now,
                updated_at=now,
            ),
            AutomationRuleResponse(
                id=2,
                name="Rule 2",
                person_name="Alice",
                actions=[ActionSchema(type="record")],
                created_at=now,
                updated_at=now,
            ),
        ]

        rule_list = AutomationRuleList(rules=rules, total=2)

        assert len(rule_list.rules) == 2
        assert rule_list.total == 2
        assert rule_list.rules[0].name == "Rule 1"

    def test_empty_automation_rule_list(self):
        """Test empty automation rule list"""
        rule_list = AutomationRuleList(rules=[], total=0)

        assert len(rule_list.rules) == 0
        assert rule_list.total == 0


class TestAutomationRuleStats:
    """Test AutomationRuleStats schema"""

    def test_valid_automation_rule_stats(self):
        """Test valid automation rule statistics"""
        stats = AutomationRuleStats(
            total_rules=10,
            enabled_rules=8,
            disabled_rules=2,
            total_triggers=150,
            rules_by_person={"John": 3, "Alice": 5, "Bob": 2},
        )

        assert stats.total_rules == 10
        assert stats.enabled_rules == 8
        assert stats.disabled_rules == 2
        assert stats.total_triggers == 150
        assert stats.rules_by_person["John"] == 3


class TestAutomationTestRequest:
    """Test AutomationTestRequest schema"""

    def test_valid_automation_test_request(self):
        """Test valid automation test request"""
        request = AutomationTestRequest(
            camera_id="front_door",
            confidence=0.95,
            skip_cooldown=True,
        )

        assert request.camera_id == "front_door"
        assert request.confidence == 0.95
        assert request.skip_cooldown is True

    def test_automation_test_request_defaults(self):
        """Test automation test request default values"""
        request = AutomationTestRequest()

        assert request.camera_id is None
        assert request.confidence == 0.95
        assert request.skip_cooldown is False

    def test_confidence_range_validation(self):
        """Test confidence must be between 0.0 and 1.0"""
        # Valid values
        for value in [0.0, 0.5, 0.95, 1.0]:
            request = AutomationTestRequest(confidence=value)
            assert request.confidence == value

        # Invalid values
        for invalid_value in [-0.1, 1.1]:
            with pytest.raises(ValidationError) as exc_info:
                AutomationTestRequest(confidence=invalid_value)

            errors = exc_info.value.errors()
            assert any(error["loc"] == ("confidence",) for error in errors)


class TestAutomationTestResponse:
    """Test AutomationTestResponse schema"""

    def test_valid_automation_test_response_success(self):
        """Test valid automation test response (success)"""
        response = AutomationTestResponse(
            success=True,
            message="Test executed successfully",
            conditions_met=True,
            cooldown_active=False,
            actions_executed=[
                {"type": "notification", "status": "sent"},
                {"type": "record", "status": "started"},
            ],
        )

        assert response.success is True
        assert response.message == "Test executed successfully"
        assert response.conditions_met is True
        assert response.cooldown_active is False
        assert len(response.actions_executed) == 2
        assert response.errors is None

    def test_valid_automation_test_response_failure(self):
        """Test valid automation test response (failure)"""
        response = AutomationTestResponse(
            success=False,
            message="Test failed",
            conditions_met=False,
            cooldown_active=True,
            actions_executed=[],
            errors=["Cooldown period active", "Conditions not met"],
        )

        assert response.success is False
        assert response.message == "Test failed"
        assert response.conditions_met is False
        assert response.cooldown_active is True
        assert len(response.actions_executed) == 0
        assert len(response.errors) == 2
