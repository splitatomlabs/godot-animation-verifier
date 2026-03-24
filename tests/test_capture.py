"""Unit tests for capture_scene() and capture CLI subcommand."""

import subprocess
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from godot_animation_verifier.capture import capture_scene
from godot_animation_verifier.cli import app

runner = CliRunner()


@pytest.fixture()
def godot_project(tmp_path: Path) -> Path:
    """Create a minimal Godot project structure and return the scene path."""
    (tmp_path / "project.godot").write_text("config_version=5\n")
    scene = tmp_path / "main.tscn"
    scene.write_text('[gd_scene format=3]\n[node name="Root" type="Control"]\n')
    return scene


class TestDefaultArgs:
    def test_write_movie_flag_present(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            capture_scene(scene_path=godot_project, output_path=output)
            cmd = mock_run.call_args[0][0]
        assert "--write-movie" in cmd

    def test_scene_path_as_res_path(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            capture_scene(scene_path=godot_project, output_path=output)
            cmd = mock_run.call_args[0][0]
        assert "res://main.tscn" in cmd

    def test_default_godot_binary_is_godot(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            capture_scene(scene_path=godot_project, output_path=output)
            cmd = mock_run.call_args[0][0]
        assert cmd[0] == "godot"

    def test_output_path_follows_write_movie_flag(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            capture_scene(scene_path=godot_project, output_path=output)
            cmd = mock_run.call_args[0][0]
        idx = cmd.index("--write-movie")
        assert cmd[idx + 1] == str(output.resolve())

    def test_path_flag_points_to_project_root(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            capture_scene(scene_path=godot_project, output_path=output)
            cmd = mock_run.call_args[0][0]
        idx = cmd.index("--path")
        assert cmd[idx + 1] == str(godot_project.parent)

    def test_no_fixed_fps_by_default(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            capture_scene(scene_path=godot_project, output_path=output)
            cmd = mock_run.call_args[0][0]
        assert "--fixed-fps" not in cmd

    def test_fixed_fps_flag_when_fps_set(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            capture_scene(scene_path=godot_project, output_path=output, fps=30)
            cmd = mock_run.call_args[0][0]
        assert "--fixed-fps" in cmd
        idx = cmd.index("--fixed-fps")
        assert cmd[idx + 1] == "30"


class TestHeadlessFlag:
    def test_headless_true_warns(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                capture_scene(scene_path=godot_project, output_path=output, headless=True)
                assert len(w) == 1
                assert "incompatible" in str(w[0].message).lower()

    def test_headless_true_does_not_pass_flag(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                capture_scene(scene_path=godot_project, output_path=output, headless=True)
                cmd = mock_run.call_args[0][0]
        assert "--headless" not in cmd

    def test_headless_false_no_warning(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                capture_scene(scene_path=godot_project, output_path=output, headless=False)
                assert len(w) == 0


class TestCustomGodotPath:
    def test_custom_binary_used_as_first_arg(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        custom_godot = "/opt/godot4/godot"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            capture_scene(scene_path=godot_project, output_path=output, godot_binary=custom_godot)
            cmd = mock_run.call_args[0][0]
        assert cmd[0] == custom_godot

    def test_custom_binary_path_object_accepted(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        custom_godot = Path("/usr/local/bin/godot4")
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            capture_scene(scene_path=godot_project, output_path=output, godot_binary=custom_godot)
            cmd = mock_run.call_args[0][0]
        assert cmd[0] == str(custom_godot)


class TestDurationQuitAfter:
    def test_quit_after_flag_present(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            capture_scene(scene_path=godot_project, output_path=output, duration_frames=60)
            cmd = mock_run.call_args[0][0]
        assert "--quit-after" in cmd

    def test_quit_after_value_matches_duration(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            capture_scene(scene_path=godot_project, output_path=output, duration_frames=120)
            cmd = mock_run.call_args[0][0]
        idx = cmd.index("--quit-after")
        assert cmd[idx + 1] == "120"

    def test_default_duration_sets_quit_after(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            capture_scene(scene_path=godot_project, output_path=output)
            cmd = mock_run.call_args[0][0]
        assert "--quit-after" in cmd


class TestOutputPathReturned:
    def test_returns_path_object(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            result = capture_scene(scene_path=godot_project, output_path=output)
        assert isinstance(result, Path)

    def test_returned_path_matches_output_arg(self, godot_project: Path) -> None:
        output = godot_project.parent / "capture.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            result = capture_scene(scene_path=godot_project, output_path=output)
        assert result == output.resolve()


class TestNonZeroExitRaises:
    def test_raises_on_nonzero_returncode(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        mock_result = MagicMock(returncode=1)
        mock_result.check_returncode.side_effect = subprocess.CalledProcessError(1, "godot")
        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(subprocess.CalledProcessError):
                capture_scene(scene_path=godot_project, output_path=output)

    def test_raises_on_godot_error_exit(self, godot_project: Path) -> None:
        output = godot_project.parent / "out.avi"
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(255, "godot")):
            with pytest.raises(subprocess.CalledProcessError):
                capture_scene(scene_path=godot_project, output_path=output)


class TestProjectDiscovery:
    def test_raises_without_project_godot(self, tmp_path: Path) -> None:
        scene = tmp_path / "main.tscn"
        scene.write_text("[gd_scene format=3]\n")
        output = tmp_path / "out.avi"
        with pytest.raises(FileNotFoundError, match="project.godot"):
            capture_scene(scene_path=scene, output_path=output)

    def test_finds_project_in_parent_dir(self, tmp_path: Path) -> None:
        (tmp_path / "project.godot").write_text("config_version=5\n")
        subdir = tmp_path / "scenes"
        subdir.mkdir()
        scene = subdir / "test.tscn"
        scene.write_text("[gd_scene format=3]\n")
        output = tmp_path / "out.avi"
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            capture_scene(scene_path=scene, output_path=output)
            cmd = mock_run.call_args[0][0]
        idx = cmd.index("--path")
        assert cmd[idx + 1] == str(tmp_path)
        assert "res://scenes/test.tscn" in cmd


# --- CLI capture subcommand tests ---


class TestCaptureCLI:
    def test_capture_command_exists(self) -> None:
        result = runner.invoke(app, ["capture", "--help"])
        assert result.exit_code == 0
        assert "capture" in result.stdout.lower()

    def test_capture_calls_capture_scene(self, godot_project: Path) -> None:
        with patch("godot_animation_verifier.cli.capture_scene", return_value=godot_project.parent / "out.avi") as mock_cap:
            result = runner.invoke(app, ["capture", str(godot_project), "--output", str(godot_project.parent / "out.avi")])
        assert result.exit_code == 0
        mock_cap.assert_called_once()

    def test_capture_duration_option(self, godot_project: Path) -> None:
        with patch("godot_animation_verifier.cli.capture_scene", return_value=godot_project.parent / "out.avi") as mock_cap:
            runner.invoke(app, ["capture", str(godot_project), "--duration", "120"])
        assert mock_cap.call_args.kwargs["duration_frames"] == 120

    def test_capture_godot_option(self, godot_project: Path) -> None:
        with patch("godot_animation_verifier.cli.capture_scene", return_value=godot_project.parent / "out.avi") as mock_cap:
            runner.invoke(app, ["capture", str(godot_project), "--godot", "/usr/bin/godot4"])
        assert mock_cap.call_args.kwargs["godot_binary"] == "/usr/bin/godot4"

    def test_capture_exits_nonzero_on_error(self, godot_project: Path) -> None:
        with patch("godot_animation_verifier.cli.capture_scene", side_effect=subprocess.CalledProcessError(1, "godot")):
            result = runner.invoke(app, ["capture", str(godot_project)])
        assert result.exit_code != 0

    def test_capture_exits_nonzero_on_missing_project(self, godot_project: Path) -> None:
        with patch("godot_animation_verifier.cli.capture_scene", side_effect=FileNotFoundError("No project.godot")):
            result = runner.invoke(app, ["capture", str(godot_project)])
        assert result.exit_code != 0
