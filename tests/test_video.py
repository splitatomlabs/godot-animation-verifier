import math
from pathlib import Path

import cv2
import numpy as np
import pytest

from godot_animation_verifier.video import load_frames_from_video

# Video parameters used across tests
_WIDTH = 32
_HEIGHT = 32
_SOURCE_FPS = 30
_DURATION_SEC = 1  # 30 total frames at 30 fps


def make_synthetic_video(path: Path, fps: int = _SOURCE_FPS, duration_sec: int = _DURATION_SEC) -> Path:
    """Write a short AVI video with simple solid-colour frames using cv2.VideoWriter."""
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (_WIDTH, _HEIGHT))
    total_frames = fps * duration_sec
    for i in range(total_frames):
        # Each frame has a unique blue-channel value so frames are distinguishable
        color = int(i * 255 / max(total_frames - 1, 1))
        frame = np.full((_HEIGHT, _WIDTH, 3), [color, 0, 0], dtype=np.uint8)
        writer.write(frame)
    writer.release()
    return path


class TestLoadFramesFromVideoBasic:
    def test_returns_non_empty_list(self, tmp_path: Path) -> None:
        video_path = make_synthetic_video(tmp_path / "test.avi")
        frames = load_frames_from_video(video_path)
        assert len(frames) > 0

    def test_returns_list_of_ndarrays(self, tmp_path: Path) -> None:
        video_path = make_synthetic_video(tmp_path / "test.avi")
        frames = load_frames_from_video(video_path)
        assert isinstance(frames, list)
        assert all(isinstance(f, np.ndarray) for f in frames)

    def test_frame_shape(self, tmp_path: Path) -> None:
        video_path = make_synthetic_video(tmp_path / "test.avi")
        frames = load_frames_from_video(video_path)
        assert len(frames) > 0
        height, width, channels = frames[0].shape
        assert height == _HEIGHT
        assert width == _WIDTH
        assert channels == 3


class TestLoadFramesFromVideoErrors:
    def test_raises_value_error_on_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.avi"
        with pytest.raises(ValueError, match="missing|not found|cannot open|unreadable"):
            load_frames_from_video(missing)

    def test_accepts_path_object(self, tmp_path: Path) -> None:
        video_path = make_synthetic_video(tmp_path / "test.avi")
        # Path object (not str) must be accepted without raising
        frames = load_frames_from_video(video_path)
        assert len(frames) > 0


class TestLoadFramesFromVideoFpsSampling:
    def test_samples_at_15fps_from_30fps_source(self, tmp_path: Path) -> None:
        # Source is 30 fps for 1 second; hardcoded 15 fps sampling → ~15 frames
        video_path = make_synthetic_video(tmp_path / "test.avi", fps=_SOURCE_FPS)
        frames = load_frames_from_video(video_path)
        expected = _SOURCE_FPS * _DURATION_SEC * 15 / _SOURCE_FPS  # = 15
        assert math.isclose(len(frames), expected, abs_tol=2)

    def test_15fps_source_returns_all_frames(self, tmp_path: Path) -> None:
        # When source fps matches sample rate (15), every frame should be returned
        video_path = make_synthetic_video(tmp_path / "test.avi", fps=15)
        frames = load_frames_from_video(video_path)
        expected_total = 15 * _DURATION_SEC
        assert math.isclose(len(frames), expected_total, abs_tol=2)
