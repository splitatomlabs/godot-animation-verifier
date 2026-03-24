"""Video frame extraction using OpenCV."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


_SAMPLE_FPS = 15


def load_frames_from_video(path: Path) -> list[np.ndarray]:
    """Extract frames from a video file, sampling at 15 fps.

    Returns:
        List of frames as numpy arrays (BGR, uint8).

    Raises:
        ValueError: If the file does not exist or cannot be opened.
    """
    path = Path(path)
    if not path.exists():
        raise ValueError(f"Video file not found: {path}")

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {path}")

    source_fps = cap.get(cv2.CAP_PROP_FPS)
    if source_fps <= 0:
        source_fps = _SAMPLE_FPS  # fallback: treat as 1:1

    # Compute frame interval for sampling
    interval = source_fps / _SAMPLE_FPS if _SAMPLE_FPS < source_fps else 1.0

    frames: list[np.ndarray] = []
    frame_idx = 0
    next_sample = 0.0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx >= next_sample:
            frames.append(frame)
            next_sample += interval
        frame_idx += 1

    cap.release()

    if not frames:
        raise ValueError(f"No frames could be read from: {path}")

    return frames
