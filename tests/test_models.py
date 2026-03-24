"""Tests for godot_animation_verifier data models."""

import json
import pytest
from godot_animation_verifier.models import IssueType, ChangeType, Issue, DiagnosticResult


class TestIssueType:
    def test_missing_animation_value(self):
        assert IssueType.MISSING_ANIMATION.value == "MISSING_ANIMATION"

    def test_enum_members(self):
        members = list(IssueType)
        assert len(members) == 1
        assert IssueType.MISSING_ANIMATION in members


class TestIssue:
    def test_construction(self):
        issue = Issue(
            node="HBoxContainer",
            timestamp_ms=120,
            type=IssueType.MISSING_ANIMATION,
            severity="error",
            hint="No animation found for state change",
        )
        assert issue.node == "HBoxContainer"
        assert issue.timestamp_ms == 120
        assert issue.type == IssueType.MISSING_ANIMATION
        assert issue.severity == "error"
        assert issue.hint == "No animation found for state change"

    def test_to_dict_keys(self):
        issue = Issue(
            node="Button",
            timestamp_ms=50,
            type=IssueType.MISSING_ANIMATION,
            severity="warning",
            hint="No transition detected",
        )
        d = issue.to_dict()
        assert set(d.keys()) == {
            "node", "timestamp_ms", "type", "severity", "hint",
            "change", "region", "screen_zone", "metrics", "animation_suggestions",
        }

    def test_to_dict_type_is_string(self):
        issue = Issue(
            node="Panel",
            timestamp_ms=0,
            type=IssueType.MISSING_ANIMATION,
            severity="error",
            hint="Abrupt transition",
        )
        d = issue.to_dict()
        assert d["type"] == "MISSING_ANIMATION"
        assert isinstance(d["type"], str)

    def test_to_dict_values(self):
        issue = Issue(
            node="Label",
            timestamp_ms=200,
            type=IssueType.MISSING_ANIMATION,
            severity="error",
            hint="Abrupt position change",
        )
        d = issue.to_dict()
        assert d["node"] == "Label"
        assert d["timestamp_ms"] == 200
        assert d["type"] == "MISSING_ANIMATION"
        assert d["severity"] == "error"
        assert d["hint"] == "Abrupt position change"

    def test_to_dict_is_json_serializable(self):
        issue = Issue(
            node="VBoxContainer",
            timestamp_ms=300,
            type=IssueType.MISSING_ANIMATION,
            severity="error",
            hint="Missing fade-in",
        )
        # Should not raise
        json.dumps(issue.to_dict())


    def test_new_fields_defaults(self):
        issue = Issue(
            node="X",
            timestamp_ms=0,
            type=IssueType.MISSING_ANIMATION,
            severity="high",
            hint="h",
        )
        assert issue.change is None
        assert issue.region is None
        assert issue.screen_zone == ""
        assert issue.metrics == {}
        assert issue.animation_suggestions == []

    def test_new_fields_populated(self):
        issue = Issue(
            node="X",
            timestamp_ms=0,
            type=IssueType.MISSING_ANIMATION,
            severity="high",
            hint="h",
            change=ChangeType.DISAPPEAR,
            region={"x": 10, "y": 20, "w": 30, "h": 40},
            screen_zone="top-left",
            metrics={"intensity_before": 100.0},
            animation_suggestions=[{"style": "fade", "description": "Fade out", "fits": "HUD"}],
        )
        d = issue.to_dict()
        assert d["change"] == "disappear"
        assert d["region"] == {"x": 10, "y": 20, "w": 30, "h": 40}
        assert d["screen_zone"] == "top-left"
        assert d["metrics"] == {"intensity_before": 100.0}
        assert len(d["animation_suggestions"]) == 1

    def test_change_none_serializes_as_none(self):
        issue = Issue(
            node="X", timestamp_ms=0, type=IssueType.MISSING_ANIMATION,
            severity="high", hint="h",
        )
        d = issue.to_dict()
        assert d["change"] is None


class TestChangeType:
    def test_enum_values(self):
        assert ChangeType.APPEAR.value == "appear"
        assert ChangeType.DISAPPEAR.value == "disappear"
        assert ChangeType.COLOR_CHANGE.value == "color_change"
        assert ChangeType.POSITION_JUMP.value == "position_jump"
        assert ChangeType.SIZE_CHANGE.value == "size_change"

    def test_enum_member_count(self):
        assert len(list(ChangeType)) == 5


class TestDiagnosticResult:
    def test_construction_pass(self):
        result = DiagnosticResult(pass_field=True, issues=[], frame_count=30)
        assert result.pass_field is True
        assert result.issues == []
        assert result.frame_count == 30

    def test_construction_fail(self):
        issue = Issue(
            node="Control",
            timestamp_ms=10,
            type=IssueType.MISSING_ANIMATION,
            severity="error",
            hint="No transition",
        )
        result = DiagnosticResult(pass_field=False, issues=[issue], frame_count=15)
        assert result.pass_field is False
        assert len(result.issues) == 1

    def test_to_dict_pass_serializes_as_pass(self):
        result = DiagnosticResult(pass_field=True, issues=[], frame_count=10)
        d = result.to_dict()
        assert "pass" in d
        assert "pass_field" not in d

    def test_to_dict_keys(self):
        result = DiagnosticResult(pass_field=False, issues=[], frame_count=5)
        d = result.to_dict()
        assert set(d.keys()) == {"pass", "issues", "frame_count"}

    def test_to_dict_values_no_issues(self):
        result = DiagnosticResult(pass_field=True, issues=[], frame_count=24)
        d = result.to_dict()
        assert d["pass"] is True
        assert d["issues"] == []
        assert d["frame_count"] == 24

    def test_to_dict_values_with_issues(self):
        issue = Issue(
            node="Sprite",
            timestamp_ms=100,
            type=IssueType.MISSING_ANIMATION,
            severity="error",
            hint="No transition found",
        )
        result = DiagnosticResult(pass_field=False, issues=[issue], frame_count=60)
        d = result.to_dict()
        assert d["pass"] is False
        assert d["frame_count"] == 60
        assert len(d["issues"]) == 1
        assert d["issues"][0]["node"] == "Sprite"
        assert d["issues"][0]["type"] == "MISSING_ANIMATION"

    def test_to_dict_matches_prd_schema(self):
        issue = Issue(
            node="AnimationPlayer",
            timestamp_ms=500,
            type=IssueType.MISSING_ANIMATION,
            severity="error",
            hint="Add tween for visibility change",
        )
        result = DiagnosticResult(pass_field=False, issues=[issue], frame_count=90)
        d = result.to_dict()

        # Validate top-level PRD schema
        assert isinstance(d["pass"], bool)
        assert isinstance(d["issues"], list)
        assert isinstance(d["frame_count"], int)

        # Validate issue schema
        issue_dict = d["issues"][0]
        assert isinstance(issue_dict["node"], str)
        assert isinstance(issue_dict["timestamp_ms"], int)
        assert isinstance(issue_dict["type"], str)
        assert isinstance(issue_dict["severity"], str)
        assert isinstance(issue_dict["hint"], str)
        # New fields present (may be defaults)
        assert "change" in issue_dict
        assert "region" in issue_dict
        assert "screen_zone" in issue_dict
        assert "metrics" in issue_dict
        assert "animation_suggestions" in issue_dict

    def test_to_dict_is_json_serializable(self):
        issue = Issue(
            node="TextureRect",
            timestamp_ms=250,
            type=IssueType.MISSING_ANIMATION,
            severity="error",
            hint="Abrupt visibility change",
        )
        result = DiagnosticResult(pass_field=False, issues=[issue], frame_count=45)
        # Should not raise
        payload = json.dumps(result.to_dict())
        parsed = json.loads(payload)
        assert parsed["pass"] is False
        assert parsed["frame_count"] == 45
        assert parsed["issues"][0]["type"] == "MISSING_ANIMATION"
