"""Scale test suite — Godot scenes mapping detector boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from godot_animation_verifier.detect_missing import detect_missing_animation
from godot_animation_verifier.video import load_frames_from_video

from tests.conftest import cached_capture

GODOT_PROJECT = Path(__file__).parent / "godot_project"
SCALE_SCENES_DIR = GODOT_PROJECT / "scenes" / "scale"
CAPTURE_FRAMES = 90


def _discover_scale_scenes() -> list[tuple[str, dict]]:
    """Discover all .tscn files in scale/ and pair with metadata."""
    scenes = []
    for tscn in sorted(SCALE_SCENES_DIR.glob("*.tscn")):
        meta_path = tscn.with_suffix(".metadata.json")
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
        else:
            meta = {"expected_pass": True, "category": "unknown", "description": tscn.stem}
        scenes.append((tscn.name, meta))
    return scenes


def _scene_ids() -> list[str]:
    """Generate test IDs from scene filenames."""
    return [name.removesuffix(".tscn") for name, _ in _discover_scale_scenes()]


@pytest.mark.godot
class TestScaleScenes:
    @pytest.mark.parametrize(
        "scene_name,metadata",
        _discover_scale_scenes(),
        ids=_scene_ids(),
    )
    def test_scene(
        self, scene_name: str, metadata: dict, godot_binary: str, tmp_path: Path,
        request: pytest.FixtureRequest,
    ) -> None:
        scene_path = SCALE_SCENES_DIR / scene_name
        output = tmp_path / f"{scene_name}.avi"
        refresh_cache = request.config.getoption("--refresh-cache")

        video = cached_capture(
            scene_path=scene_path,
            output_path=output,
            godot_binary=godot_binary,
            duration_frames=CAPTURE_FRAMES,
            refresh_cache=refresh_cache,
        )
        frames = load_frames_from_video(video)
        issues = detect_missing_animation(frames)

        expected_pass = metadata["expected_pass"]
        if expected_pass:
            assert issues == [], (
                f"{scene_name}: expected no issues, got {issues}"
            )
        else:
            assert len(issues) > 0, (
                f"{scene_name}: expected issues but got none"
            )
