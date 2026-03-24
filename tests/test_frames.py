import numpy as np
import cv2
import pytest
from pathlib import Path

from godot_animation_verifier.frames import load_frames


def write_png(path: Path, array: np.ndarray) -> None:
    cv2.imwrite(str(path), array)


class TestLoadFrames:
    def test_loads_frames_in_filename_order(self, tmp_path: Path) -> None:
        # Create three small RGB frames with distinct values so order is verifiable
        for i, value in enumerate([10, 20, 30]):
            img = np.full((4, 4, 3), value, dtype=np.uint8)
            write_png(tmp_path / f"frame_{i:03d}.png", img)

        frames = load_frames(tmp_path)

        assert len(frames) == 3
        assert frames[0][0, 0, 0] == 10
        assert frames[1][0, 0, 0] == 20
        assert frames[2][0, 0, 0] == 30

    def test_sorts_by_filename_not_creation_order(self, tmp_path: Path) -> None:
        # Write in reverse order to verify sort is lexicographic on filename
        for i, value in enumerate([30, 20, 10]):
            img = np.full((4, 4, 3), value, dtype=np.uint8)
            name = f"frame_{(2 - i):03d}.png"
            write_png(tmp_path / name, img)

        frames = load_frames(tmp_path)

        assert len(frames) == 3
        assert frames[0][0, 0, 0] == 10
        assert frames[1][0, 0, 0] == 20
        assert frames[2][0, 0, 0] == 30

    def test_raises_value_error_on_empty_directory(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="No PNG files found"):
            load_frames(tmp_path)

    def test_ignores_non_png_files(self, tmp_path: Path) -> None:
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "data.jpg").write_bytes(b"")

        with pytest.raises(ValueError, match="No PNG files found"):
            load_frames(tmp_path)

    def test_loads_3_channel_rgb_png(self, tmp_path: Path) -> None:
        img = np.zeros((8, 8, 3), dtype=np.uint8)
        img[:, :, 0] = 100  # blue channel in BGR
        write_png(tmp_path / "frame_000.png", img)

        frames = load_frames(tmp_path)

        assert len(frames) == 1
        assert frames[0].ndim == 3
        assert frames[0].shape[2] == 3

    def test_loads_4_channel_rgba_png(self, tmp_path: Path) -> None:
        img = np.zeros((8, 8, 4), dtype=np.uint8)
        img[:, :, 3] = 128  # alpha channel
        write_png(tmp_path / "frame_000.png", img)

        frames = load_frames(tmp_path)

        assert len(frames) == 1
        assert frames[0].ndim == 3
        assert frames[0].shape[2] == 4

    def test_returns_numpy_ndarrays(self, tmp_path: Path) -> None:
        img = np.zeros((4, 4, 3), dtype=np.uint8)
        write_png(tmp_path / "frame_000.png", img)

        frames = load_frames(tmp_path)

        assert isinstance(frames, list)
        assert all(isinstance(f, np.ndarray) for f in frames)

    def test_accepts_path_object(self, tmp_path: Path) -> None:
        img = np.zeros((4, 4, 3), dtype=np.uint8)
        write_png(tmp_path / "frame_000.png", img)

        frames = load_frames(tmp_path)

        assert len(frames) == 1
