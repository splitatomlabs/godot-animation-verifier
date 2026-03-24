"""Integration tests for Godot test scenes — capture and run detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from godot_animation_verifier.detect_missing import detect_missing_animation
from godot_animation_verifier.models import IssueType
from godot_animation_verifier.video import load_frames_from_video

from tests.conftest import cached_capture

GODOT_PROJECT = Path(__file__).parent / "godot_project"
SCENES_DIR = GODOT_PROJECT / "scenes"
CAPTURE_FRAMES = 90


def _capture_and_load(
    scene_name: str, godot_binary: str, tmp_path: Path, refresh_cache: bool = False
) -> list:
    """Capture frames via Godot --write-movie and load from video."""
    scene_path = SCENES_DIR / scene_name
    output = tmp_path / f"{scene_name}.avi"
    video = cached_capture(
        scene_path=scene_path,
        output_path=output,
        godot_binary=godot_binary,
        duration_frames=CAPTURE_FRAMES,
        refresh_cache=refresh_cache,
    )
    return load_frames_from_video(video)


# --- MISSING_ANIMATION pass scenes ---

PASS_SCENES = [
    "missing_pass_static.tscn",
    "missing_pass_smooth_slide.tscn",
    "missing_pass_smooth_fade.tscn",
]

FAIL_SCENES = [
    "missing_fail_position_teleport.tscn",
    "missing_fail_opacity_snap.tscn",
    "missing_fail_size_jump.tscn",
]


@pytest.mark.godot
class TestMissingAnimationPass:
    @pytest.mark.parametrize("scene", PASS_SCENES)
    def test_no_issues_detected(
        self, scene: str, godot_binary: str, tmp_path: Path, request: pytest.FixtureRequest
    ) -> None:
        refresh_cache = request.config.getoption("--refresh-cache")
        frames = _capture_and_load(scene, godot_binary, tmp_path, refresh_cache=refresh_cache)
        issues = detect_missing_animation(frames)
        assert issues == [], f"{scene}: expected no issues, got {issues}"


# --- MISSING_ANIMATION fail scenes ---


@pytest.mark.godot
class TestMissingAnimationFail:
    @pytest.mark.parametrize("scene", FAIL_SCENES)
    def test_issues_detected(
        self, scene: str, godot_binary: str, tmp_path: Path, request: pytest.FixtureRequest
    ) -> None:
        refresh_cache = request.config.getoption("--refresh-cache")
        frames = _capture_and_load(scene, godot_binary, tmp_path, refresh_cache=refresh_cache)
        issues = detect_missing_animation(frames)
        assert len(issues) > 0, f"{scene}: expected issues, got none"
        for issue in issues:
            assert issue.type == IssueType.MISSING_ANIMATION
