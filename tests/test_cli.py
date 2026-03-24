"""CLI integration tests using typer.testing.CliRunner."""

import json
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np
from typer.testing import CliRunner

from godot_animation_verifier.cli import app

runner = CliRunner()

FIXTURES = Path(__file__).parent / "fixtures"


def _make_video(path: Path) -> Path:
    """Create a minimal synthetic video for CLI testing."""
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    writer = cv2.VideoWriter(str(path), fourcc, 30, (32, 32))
    for i in range(30):
        color = int(i * 255 / 29)
        frame = np.full((32, 32, 3), [color, 0, 0], dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return path


class TestAnalyzeWithPngDir:
    def test_pass_case_exit_code_0(self) -> None:
        result = runner.invoke(app, ["analyze", str(FIXTURES / "missing_pass_static")])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["pass"] is True

    def test_fail_case_exit_code_1(self) -> None:
        result = runner.invoke(app, ["analyze", str(FIXTURES / "missing_fail_position_teleport")])
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert data["pass"] is False
        assert len(data["issues"]) > 0
        # Validate enriched fields in JSON output
        issue = data["issues"][0]
        assert "change" in issue
        assert "region" in issue
        assert "screen_zone" in issue
        assert "metrics" in issue
        assert "animation_suggestions" in issue

    def test_output_is_valid_json(self) -> None:
        result = runner.invoke(app, ["analyze", str(FIXTURES / "missing_pass_static")])
        data = json.loads(result.stdout)
        assert "pass" in data
        assert "issues" in data
        assert "frame_count" in data


class TestAnalyzeWithVideo:
    def test_video_file_accepted(self, tmp_path: Path) -> None:
        video_path = _make_video(tmp_path / "test.avi")
        result = runner.invoke(app, ["analyze", str(video_path)])
        assert result.exit_code in (0, 1)
        data = json.loads(result.stdout)
        assert "pass" in data



class TestAnalyzeErrorPaths:
    def test_nonexistent_path_exit_2(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["analyze", str(tmp_path / "nonexistent")])
        assert result.exit_code == 2
        assert "Error" in result.stderr

    def test_empty_directory_exit_2(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["analyze", str(tmp_path)])
        assert result.exit_code == 2
        assert "Error" in result.stderr


class TestPrettyFlag:
    def test_pretty_output_is_indented(self) -> None:
        result = runner.invoke(app, ["analyze", "--pretty", str(FIXTURES / "missing_pass_static")])
        assert result.exit_code == 0
        lines = result.stdout.strip().split("\n")
        # Pretty JSON should have multiple lines with indentation
        assert len(lines) > 1
        assert any(line.startswith("  ") or line.startswith("    ") for line in lines)

    def test_default_output_is_compact(self) -> None:
        result = runner.invoke(app, ["analyze", str(FIXTURES / "missing_pass_static")])
        assert result.exit_code == 0
        # Compact JSON should be a single line
        non_empty = [l for l in result.stdout.strip().split("\n") if l.strip()]
        assert len(non_empty) == 1


class TestCaptureCmd:
    def test_successful_capture_prints_path(self, tmp_path: Path) -> None:
        scene = tmp_path / "test.tscn"
        scene.touch()
        output = tmp_path / "out.avi"
        with patch("godot_animation_verifier.cli.capture_scene", return_value=output):
            result = runner.invoke(app, ["capture", str(scene), "-o", str(output)])
        assert result.exit_code == 0
        assert str(output) in result.stdout

    def test_capture_failure_exit_2(self, tmp_path: Path) -> None:
        scene = tmp_path / "test.tscn"
        scene.touch()
        with patch(
            "godot_animation_verifier.cli.capture_scene",
            side_effect=FileNotFoundError("godot not found"),
        ):
            result = runner.invoke(app, ["capture", str(scene)])
        assert result.exit_code == 2
        assert "Error" in result.stderr

    def test_capture_with_analyze_outputs_json(self, tmp_path: Path) -> None:
        scene = tmp_path / "test.tscn"
        scene.touch()
        video = _make_video(tmp_path / "out.avi")
        static_frame = np.full((32, 32, 3), 128, dtype=np.uint8)
        with patch("godot_animation_verifier.cli.capture_scene", return_value=video), \
             patch("godot_animation_verifier.cli.load_frames_from_video", return_value=[static_frame] * 10):
            result = runner.invoke(app, ["capture", str(scene), "-o", str(video), "--analyze"])
        assert result.exit_code in (0, 1)
        # Second line of output should be JSON (first is "Captured to ...")
        lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        json_line = lines[-1]
        data = json.loads(json_line)
        assert "pass" in data

    def test_capture_analyze_exit_1_on_issues(self, tmp_path: Path) -> None:
        scene = tmp_path / "test.tscn"
        scene.touch()
        video = tmp_path / "out.avi"
        # Create frames with an abrupt snap (static then jump)
        black = np.zeros((32, 32, 3), dtype=np.uint8)
        snap = np.full((32, 32, 3), 255, dtype=np.uint8)
        # Small region snap to trigger detection
        snap_frame = black.copy()
        cv2.rectangle(snap_frame, (5, 5), (20, 20), (255, 255, 255), -1)
        frames = [black] * 5 + [snap_frame] * 5
        with patch("godot_animation_verifier.cli.capture_scene", return_value=video), \
             patch("godot_animation_verifier.cli.load_frames_from_video", return_value=frames):
            result = runner.invoke(app, ["capture", str(scene), "-o", str(video), "--analyze"])
        assert result.exit_code == 1
        lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        data = json.loads(lines[-1])
        assert data["pass"] is False
        assert len(data["issues"]) > 0


class TestEnrichedJsonOutput:
    """End-to-end integration test validating full enriched JSON schema."""

    def test_full_json_schema_on_fail_fixture(self) -> None:
        result = runner.invoke(app, ["analyze", str(FIXTURES / "missing_fail_position_teleport")])
        assert result.exit_code == 1
        data = json.loads(result.stdout)

        # Top-level schema
        assert isinstance(data["pass"], bool)
        assert isinstance(data["issues"], list)
        assert isinstance(data["frame_count"], int)
        assert data["pass"] is False
        assert len(data["issues"]) >= 1

        for issue in data["issues"]:
            # Original fields
            assert isinstance(issue["node"], str) and issue["node"]
            assert isinstance(issue["timestamp_ms"], int)
            assert issue["type"] == "MISSING_ANIMATION"
            assert issue["severity"] in ("high", "medium")
            assert isinstance(issue["hint"], str) and issue["hint"]

            # New enriched fields
            assert issue["change"] in (
                "appear", "disappear", "color_change", "position_jump", "size_change",
            )
            assert isinstance(issue["region"], dict)
            assert all(k in issue["region"] for k in ("x", "y", "w", "h"))
            for k in ("x", "y", "w", "h"):
                assert isinstance(issue["region"][k], int)

            valid_zones = {
                "top-left", "top-center", "top-right",
                "center-left", "center", "center-right",
                "bottom-left", "bottom-center", "bottom-right",
            }
            assert issue["screen_zone"] in valid_zones

            assert isinstance(issue["metrics"], dict)
            for mk in ("intensity_before", "intensity_after", "region_area_px",
                        "transition_frames", "concurrent_events"):
                assert mk in issue["metrics"], f"Missing metric key: {mk}"

            assert isinstance(issue["animation_suggestions"], list)
            assert len(issue["animation_suggestions"]) >= 2
            for s in issue["animation_suggestions"]:
                assert "style" in s
                assert "description" in s
                assert "fits" in s
