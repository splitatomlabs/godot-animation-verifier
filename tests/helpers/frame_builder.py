"""Builder utilities for compositing animated regions onto synthetic frames."""

import cv2
import numpy as np


class FrameBuilder:
    """Helper for constructing synthetic BGR test frames."""

    @staticmethod
    def create_blank(w: int = 480, h: int = 270, color: tuple[int, int, int] = (30, 30, 30)) -> np.ndarray:
        """Create a blank BGR frame filled with *color*."""
        frame = np.empty((h, w, 3), dtype=np.uint8)
        frame[:] = color
        return frame

    @staticmethod
    def draw_circle(
        frame: np.ndarray,
        center: tuple[int, int],
        radius: int,
        color: tuple[int, int, int] = (0, 255, 0),
        scale: float = 1.0,
        anti_alias: bool = False,
    ) -> np.ndarray:
        """Draw a filled circle on *frame* (mutates and returns it).

        *scale* multiplies the radius (useful for tween animations).
        """
        r = max(1, int(radius * scale))
        line_type = cv2.LINE_AA if anti_alias else cv2.LINE_8
        cv2.circle(frame, center, r, color, thickness=-1, lineType=line_type)
        return frame

    @staticmethod
    def draw_rect(
        frame: np.ndarray,
        pos: tuple[int, int],
        size: tuple[int, int],
        color: tuple[int, int, int] = (0, 255, 0),
        alpha: float = 1.0,
    ) -> np.ndarray:
        """Draw a filled rectangle with optional alpha blending (mutates and returns)."""
        x, y = pos
        w, h = size
        x1, y1 = max(0, x), max(0, y)
        x2 = min(frame.shape[1], x + w)
        y2 = min(frame.shape[0], y + h)
        if x2 <= x1 or y2 <= y1:
            return frame

        if alpha >= 1.0:
            frame[y1:y2, x1:x2] = color
        else:
            overlay = frame[y1:y2, x1:x2].astype(np.float32)
            overlay = overlay * (1.0 - alpha) + np.array(color, dtype=np.float32) * alpha
            frame[y1:y2, x1:x2] = np.clip(overlay, 0, 255).astype(np.uint8)
        return frame

    @staticmethod
    def composite_region(
        base: np.ndarray,
        overlay: np.ndarray,
        pos: tuple[int, int],
        alpha: float = 1.0,
    ) -> np.ndarray:
        """Composite *overlay* onto *base* at *pos* with alpha blending (mutates base)."""
        x, y = pos
        oh, ow = overlay.shape[:2]
        x1, y1 = max(0, x), max(0, y)
        x2 = min(base.shape[1], x + ow)
        y2 = min(base.shape[0], y + oh)
        ox1 = x1 - x
        oy1 = y1 - y
        ox2 = ox1 + (x2 - x1)
        oy2 = oy1 + (y2 - y1)
        if x2 <= x1 or y2 <= y1:
            return base

        region = base[y1:y2, x1:x2].astype(np.float32)
        over = overlay[oy1:oy2, ox1:ox2].astype(np.float32)
        blended = region * (1.0 - alpha) + over * alpha
        base[y1:y2, x1:x2] = np.clip(blended, 0, 255).astype(np.uint8)
        return base
