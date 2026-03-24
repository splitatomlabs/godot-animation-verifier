"""Synthetic fixture generator for Agentease test cases.

Generates PNG frame sequences under tests/fixtures/ for use as ground-truth
data in MISSING_ANIMATION detector tests.

Usage:
    python tests/generate_fixtures.py

Each fixture is a directory containing:
  - frame_000.png … frame_014.png  (15 frames, 480x270)
  - metadata.json  (expected_pass, detection_type, description)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FRAME_COUNT = 15
WIDTH = 480
HEIGHT = 270
BG_COLOR = (40, 40, 40)          # dark gray, BGR
RECT_COLOR = (64, 200, 64)       # bright green, BGR
RECT_COLOR_RGBA = (64, 200, 64, 255)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ease_in_out(t: float) -> float:
    """Cubic ease-in-out: 3t² - 2t³, for t in [0, 1]."""
    return 3 * t * t - 2 * t * t * t


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def make_rgb_frame(rect_x: int, rect_y: int, rect_w: int, rect_h: int) -> np.ndarray:
    """Return a 480x270 BGR frame with a colored rectangle."""
    frame = np.full((HEIGHT, WIDTH, 3), BG_COLOR, dtype=np.uint8)
    x1, y1 = rect_x, rect_y
    x2, y2 = rect_x + rect_w, rect_y + rect_h
    cv2.rectangle(frame, (x1, y1), (x2, y2), RECT_COLOR, thickness=-1)
    return frame


def make_rgba_frame(
    rect_x: int,
    rect_y: int,
    rect_w: int,
    rect_h: int,
    alpha: int,
) -> np.ndarray:
    """Return a 480x270 BGRA frame with a colored rectangle at given alpha."""
    frame = np.full((HEIGHT, WIDTH, 4), (*BG_COLOR, 255), dtype=np.uint8)
    x1, y1 = rect_x, rect_y
    x2, y2 = rect_x + rect_w, rect_y + rect_h
    color_bgra = (RECT_COLOR[0], RECT_COLOR[1], RECT_COLOR[2], alpha)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color_bgra, thickness=-1)
    return frame


def write_sequence(
    name: str,
    frames: list[np.ndarray],
    expected_pass: bool,
    detection_type: str,
    description: str,
) -> None:
    """Write a fixture directory with PNG frames and metadata.json."""
    out_dir = FIXTURES_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, frame in enumerate(frames):
        path = out_dir / f"frame_{i:03d}.png"
        cv2.imwrite(str(path), frame)

    metadata = {
        "expected_pass": expected_pass,
        "detection_type": detection_type,
        "description": description,
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    print(f"  wrote {len(frames)} frames -> {out_dir.relative_to(Path(__file__).parent.parent)}")


# ---------------------------------------------------------------------------
# MISSING_ANIMATION fixtures
# ---------------------------------------------------------------------------

def generate_missing_pass_static() -> None:
    """Rectangle stationary at center for all 15 frames."""
    cx, cy = WIDTH // 2 - 20, HEIGHT // 2 - 20  # top-left of 40x40 centered rect
    frames = [make_rgb_frame(cx, cy, 40, 40) for _ in range(FRAME_COUNT)]
    write_sequence(
        "missing_pass_static",
        frames,
        expected_pass=True,
        detection_type="MISSING_ANIMATION",
        description="Rectangle stationary at center — no animation needed, should pass.",
    )


def generate_missing_pass_smooth_slide() -> None:
    """Rectangle slides left-to-right with ease-in-out over 15 frames."""
    x_start, x_end = 40, 400
    y = HEIGHT // 2 - 20
    frames = []
    for i in range(FRAME_COUNT):
        t = i / (FRAME_COUNT - 1)
        x = int(_lerp(x_start, x_end, ease_in_out(t)))
        frames.append(make_rgb_frame(x, y, 40, 40))
    write_sequence(
        "missing_pass_smooth_slide",
        frames,
        expected_pass=True,
        detection_type="MISSING_ANIMATION",
        description="Rectangle slides left-to-right with ease-in-out curve — smooth transition, should pass.",
    )


def generate_missing_pass_smooth_fade() -> None:
    """Rectangle fades from full opacity to transparent with eased alpha."""
    cx, cy = WIDTH // 2 - 20, HEIGHT // 2 - 20
    frames = []
    for i in range(FRAME_COUNT):
        t = i / (FRAME_COUNT - 1)
        alpha = int(_lerp(255, 0, ease_in_out(t)))
        frames.append(make_rgba_frame(cx, cy, 40, 40, alpha))
    write_sequence(
        "missing_pass_smooth_fade",
        frames,
        expected_pass=True,
        detection_type="MISSING_ANIMATION",
        description="Rectangle fades out with ease-in-out alpha curve — smooth transition, should pass.",
    )


def generate_missing_fail_position_teleport() -> None:
    """Rectangle at (40,120) for frames 0-7, then jumps to (400,120) for 8-14."""
    y = 120
    frames = []
    for i in range(FRAME_COUNT):
        x = 40 if i < 8 else 400
        frames.append(make_rgb_frame(x, y, 40, 40))
    write_sequence(
        "missing_fail_position_teleport",
        frames,
        expected_pass=False,
        detection_type="MISSING_ANIMATION",
        description="Rectangle teleports from left to right with no transition — should fail.",
    )


def generate_missing_fail_opacity_snap() -> None:
    """Rectangle fully visible frames 0-7, then invisible frames 8-14."""
    cx, cy = WIDTH // 2 - 20, HEIGHT // 2 - 20
    frames = []
    for i in range(FRAME_COUNT):
        alpha = 255 if i < 8 else 0
        frames.append(make_rgba_frame(cx, cy, 40, 40, alpha))
    write_sequence(
        "missing_fail_opacity_snap",
        frames,
        expected_pass=False,
        detection_type="MISSING_ANIMATION",
        description="Rectangle snaps from fully visible to invisible with no fade — should fail.",
    )


def generate_missing_fail_size_jump() -> None:
    """Rectangle 40x40 for frames 0-7, then 120x120 for frames 8-14."""
    cx, cy = WIDTH // 2, HEIGHT // 2
    frames = []
    for i in range(FRAME_COUNT):
        size = 40 if i < 8 else 120
        # Center the rectangle at (cx, cy) regardless of size.
        x = cx - size // 2
        y = cy - size // 2
        frames.append(make_rgb_frame(x, y, size, size))
    write_sequence(
        "missing_fail_size_jump",
        frames,
        expected_pass=False,
        detection_type="MISSING_ANIMATION",
        description="Rectangle jumps from 40x40 to 120x120 with no scale transition — should fail.",
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

MISSING_ANIMATION_GENERATORS: list[Callable[[], None]] = [
    generate_missing_pass_static,
    generate_missing_pass_smooth_slide,
    generate_missing_pass_smooth_fade,
    generate_missing_fail_position_teleport,
    generate_missing_fail_opacity_snap,
    generate_missing_fail_size_jump,
]

def generate_all() -> None:
    """Generate all fixture sequences."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating MISSING_ANIMATION fixtures...")
    for fn in MISSING_ANIMATION_GENERATORS:
        fn()

    print("Done.")


if __name__ == "__main__":
    generate_all()
