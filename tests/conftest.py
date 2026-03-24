"""Pytest configuration — auto-generate fixtures on first run."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FRAME_CACHE_DIR = Path(__file__).parent / ".frame_cache"
EXPECTED_DIRS = 6
EXPECTED_FRAMES = 15


def _fixtures_present() -> bool:
    """Return True if all 12 fixture directories exist with correct frame counts."""
    if not FIXTURES_DIR.is_dir():
        return False
    dirs = [d for d in FIXTURES_DIR.iterdir() if d.is_dir()]
    if len(dirs) < EXPECTED_DIRS:
        return False
    return all(
        len(list(d.glob("*.png"))) == EXPECTED_FRAMES for d in dirs
    )



@pytest.fixture(scope="session", autouse=True)
def ensure_fixtures() -> None:
    """Generate test fixtures if missing or incomplete."""
    if _fixtures_present():
        return
    from tests.generate_fixtures import generate_all

    generate_all()
    assert _fixtures_present(), "Fixture generation failed"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--refresh-cache",
        action="store_true",
        default=False,
        help="Bypass the frame cache and re-capture all Godot scenes.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "fixtures: tests that depend on generated fixtures")
    config.addinivalue_line("markers", "scale: scale test suite (120 scenes, requires Godot)")
    config.addinivalue_line("markers", "godot: tests that require a running Godot binary")


def cached_capture(
    scene_path: str | Path,
    output_path: str | Path,
    godot_binary: str | Path,
    duration_frames: int,
    refresh_cache: bool = False,
) -> Path:
    """Capture a Godot scene to AVI, using a content-addressed cache to skip redundant captures.

    Args:
        scene_path: Path to the .tscn file.
        output_path: Destination path for the AVI file.
        godot_binary: Path to the Godot binary.
        duration_frames: Number of frames to capture (passed to capture_scene).
        refresh_cache: When True, bypass the cache and always re-capture.

    Returns:
        Path to the output AVI file.
    """
    from godot_animation_verifier.capture import capture_scene

    scene_path = Path(scene_path)
    output_path = Path(output_path)

    # Build a stable hash from scene content + duration_frames.
    content = scene_path.read_bytes()
    digest = hashlib.sha256(content + b"\x00" + str(duration_frames).encode()).hexdigest()
    FRAME_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached_avi = FRAME_CACHE_DIR / f"{digest}.avi"

    if not refresh_cache and cached_avi.exists():
        shutil.copy2(cached_avi, output_path)
        return output_path

    # Cache miss (or refresh forced): run capture, then store result.
    capture_scene(scene_path, output_path, godot_binary, duration_frames)
    shutil.copy2(output_path, cached_avi)
    return output_path


@pytest.fixture(scope="session")
def godot_binary() -> str:
    """Return path to Godot binary, or skip if not found."""
    path = os.environ.get("GODOT_PATH") or shutil.which("godot")
    if not path:
        pytest.skip("godot binary not found (set GODOT_PATH or add godot to PATH)")
    return path
