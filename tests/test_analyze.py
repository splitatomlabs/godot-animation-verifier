"""Tests for the analyze() orchestrator."""

from pathlib import Path

import numpy as np

from godot_animation_verifier.analyze import analyze
from godot_animation_verifier.frames import load_frames
from godot_animation_verifier.models import DiagnosticResult, IssueType

FIXTURES = Path(__file__).parent / "fixtures"


class TestAnalyzePassCases:
    def test_static_scene_passes(self) -> None:
        frames = load_frames(FIXTURES / "missing_pass_static")
        result = analyze(frames)
        assert isinstance(result, DiagnosticResult)
        assert result.pass_field is True
        assert result.issues == []

    def test_smooth_slide_passes(self) -> None:
        frames = load_frames(FIXTURES / "missing_pass_smooth_slide")
        result = analyze(frames)
        assert isinstance(result, DiagnosticResult)
        assert result.pass_field is True

    def test_frame_count_matches(self) -> None:
        frames = load_frames(FIXTURES / "missing_pass_static")
        result = analyze(frames)
        assert result.frame_count == len(frames)


class TestAnalyzeFailCases:
    def test_teleport_detected(self) -> None:
        frames = load_frames(FIXTURES / "missing_fail_position_teleport")
        result = analyze(frames)
        assert result.pass_field is False
        assert len(result.issues) > 0
        assert any(i.type == IssueType.MISSING_ANIMATION for i in result.issues)
        # Validate enriched fields on first issue
        issue = result.issues[0]
        assert issue.change is not None
        assert issue.region is not None
        assert issue.screen_zone != ""
        assert "intensity_before" in issue.metrics
        assert len(issue.animation_suggestions) >= 2

class TestAnalyzeOutputSchema:
    def test_to_dict_schema(self) -> None:
        frames = load_frames(FIXTURES / "missing_fail_position_teleport")
        result = analyze(frames)
        d = result.to_dict()
        assert "pass" in d
        assert "issues" in d
        assert "frame_count" in d
        assert isinstance(d["pass"], bool)
        assert isinstance(d["issues"], list)
        assert isinstance(d["frame_count"], int)
        # Validate new fields in serialized output
        if d["issues"]:
            issue = d["issues"][0]
            assert "change" in issue
            assert "region" in issue
            assert "screen_zone" in issue
            assert "metrics" in issue
            assert "animation_suggestions" in issue


class TestAnalyzeEdgeCases:
    def test_single_frame_passes(self) -> None:
        frame = np.full((32, 32, 3), 128, dtype=np.uint8)
        result = analyze([frame])
        assert result.pass_field is True
        assert result.issues == []
        assert result.frame_count == 1

    def test_two_identical_frames_passes(self) -> None:
        frame = np.full((32, 32, 3), 128, dtype=np.uint8)
        result = analyze([frame, frame])
        assert result.pass_field is True
        assert result.issues == []

    def test_empty_list_passes(self) -> None:
        result = analyze([])
        assert result.pass_field is True
        assert result.issues == []
        assert result.frame_count == 0
