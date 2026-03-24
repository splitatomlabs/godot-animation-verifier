"""Launch Godot with --write-movie to capture rendered frames as video."""

from __future__ import annotations

import subprocess
import warnings
from pathlib import Path


def _find_project_root(scene_path: Path) -> Path:
    """Walk up from scene_path to find the directory containing project.godot."""
    current = scene_path.resolve().parent
    while current != current.parent:
        if (current / "project.godot").exists():
            return current
        current = current.parent
    raise FileNotFoundError(
        f"No project.godot found in ancestors of {scene_path}"
    )


def capture_scene(
    scene_path: str | Path,
    output_path: str | Path,
    godot_binary: str | Path = "godot",
    duration_frames: int = 60,
    headless: bool = False,
    fps: int | None = None,
    extra_args: list[str] | None = None,
) -> Path:
    """Capture a Godot scene to video using --write-movie.

    Args:
        scene_path: Path to a .tscn file inside a Godot project.
        output_path: Where to write the AVI file.
        godot_binary: Path to the Godot 4.x binary.
        duration_frames: Number of frames to capture.
        headless: Ignored — --headless is incompatible with --write-movie.
        fps: Fixed frame rate for capture. When None, Godot runs at
            its natural frame rate (no ``--fixed-fps`` flag).
        extra_args: Additional arguments appended to the Godot command line.
            These are passed as user args (after ``--``) so the game can
            read them via ``OS.get_cmdline_user_args()``.

    Returns the Path to the written video file.
    Raises subprocess.CalledProcessError on non-zero exit.
    Raises FileNotFoundError if no project.godot is found.
    """
    if headless:
        warnings.warn(
            "--headless is incompatible with --write-movie (Godot's dummy "
            "renderer cannot produce frames). The headless flag will be ignored.",
            stacklevel=2,
        )

    scene_path = Path(scene_path)
    output_path = Path(output_path).resolve()
    project_root = _find_project_root(scene_path)

    # Convert scene filesystem path to res:// path
    try:
        rel = scene_path.resolve().relative_to(project_root)
        res_path = f"res://{rel}"
    except ValueError:
        res_path = str(scene_path)

    cmd: list[str] = [
        str(godot_binary),
        "--path",
        str(project_root),
        "--write-movie",
        str(output_path),
        "--quit-after",
        str(duration_frames),
        res_path,
    ]

    if fps is not None:
        cmd.insert(-1, "--fixed-fps")
        cmd.insert(-1, str(fps))

    if extra_args:
        cmd.append("--")
        cmd.extend(extra_args)

    timeout = 30 + duration_frames  # generous timeout: ~1s per frame + 30s startup
    result = subprocess.run(cmd, timeout=timeout)
    result.check_returncode()
    return output_path
