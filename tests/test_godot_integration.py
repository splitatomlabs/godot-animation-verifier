"""End-to-end CLI integration tests against real Godot scenes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from godot_animation_verifier.cli import app

runner = CliRunner()

GODOT_PROJECT = Path(__file__).parent / "godot_project"
SCENES_DIR = GODOT_PROJECT / "scenes"


@pytest.mark.godot
class TestGodotCLIEndToEnd:
    def test_pass_scene_exit_0(self, godot_binary: str, tmp_path: Path) -> None:
        scene = SCENES_DIR / "missing_pass_static.tscn"
        output = tmp_path / "pass.avi"
        result = runner.invoke(app, [
            "capture", str(scene),
            "-o", str(output),
            "--godot", godot_binary,
            "-n", "90",
            "--analyze",
        ])
        assert result.exit_code == 0
        lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        data = json.loads(lines[-1])
        assert data["pass"] is True

    def test_fail_scene_exit_1(self, godot_binary: str, tmp_path: Path) -> None:
        scene = SCENES_DIR / "missing_fail_position_teleport.tscn"
        output = tmp_path / "fail.avi"
        result = runner.invoke(app, [
            "capture", str(scene),
            "-o", str(output),
            "--godot", godot_binary,
            "-n", "90",
            "--analyze",
        ])
        assert result.exit_code == 1
        lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        data = json.loads(lines[-1])
        assert data["pass"] is False
        assert len(data["issues"]) > 0
