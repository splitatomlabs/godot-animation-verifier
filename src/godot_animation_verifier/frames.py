from pathlib import Path

import cv2
import numpy as np


def load_frames(directory: Path) -> list[np.ndarray]:
    """Load PNG frames from a directory, sorted by filename.

    Args:
        directory: Path to a directory containing PNG files.

    Returns:
        List of frames as numpy arrays, sorted lexicographically by filename.
        Both 3-channel (RGB) and 4-channel (RGBA) PNGs are supported.

    Raises:
        ValueError: If no PNG files are found in the directory.
    """
    png_paths = sorted(directory.glob("*.png"))

    if not png_paths:
        raise ValueError(f"No PNG files found in {directory}")

    frames: list[np.ndarray] = []
    for path in png_paths:
        frame = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if frame is None:
            raise ValueError(f"Failed to read image: {path}")
        frames.append(frame)

    return frames
