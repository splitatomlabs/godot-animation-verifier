"""Tests for false-positive suppression and genuine-missing detection.

Covers: smooth tweens (T02), simultaneous animations (T03),
subpixel artifacts (T04), genuinely missing animations (T05),
and metrics validation (T08).
"""

from __future__ import annotations

import cv2
import math
import numpy as np
import pytest

from godot_animation_verifier.detect_missing import detect_missing_animation
from godot_animation_verifier.models import ChangeType
from tests.helpers.easing import ease_out_cubic, trans_back, trans_elastic
from tests.helpers.frame_builder import FrameBuilder

W, H = 480, 270

BG = (30, 30, 30)


def _make_scale_tween_frames(
    num_frames: int = 10,
    easing=ease_out_cubic,
    scale_start: float = 0.01,
    scale_end: float = 1.0,
) -> list[np.ndarray]:
    """Circle scales from scale_start to scale_end over num_frames."""
    frames = []
    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)
        s = scale_start + (scale_end - scale_start) * easing(t)
        frame = FrameBuilder.create_blank(W, H, BG)
        FrameBuilder.draw_circle(frame, (W // 2, H // 2), 40, (0, 255, 0), scale=s)
        frames.append(frame)
    return frames


def _make_rotation_tween_frames(num_frames: int = 8, angle_rad: float = 0.5) -> list[np.ndarray]:
    """Square rotates smoothly over num_frames."""
    frames = []
    size = 40
    cx, cy = W // 2, H // 2
    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)
        angle = angle_rad * ease_out_cubic(t)
        frame = FrameBuilder.create_blank(W, H, BG)
        # Rotated rectangle via rotation matrix
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        half = size // 2
        corners = [(-half, -half), (half, -half), (half, half), (-half, half)]
        pts = []
        for dx, dy in corners:
            rx = int(cx + dx * cos_a - dy * sin_a)
            ry = int(cy + dx * sin_a + dy * cos_a)
            pts.append([rx, ry])
        pts_arr = np.array(pts, dtype=np.int32)
        cv2.fillPoly(frame, [pts_arr], (0, 200, 200))
        frames.append(frame)
    return frames


def _make_overshoot_tween_frames(num_frames: int = 10) -> list[np.ndarray]:
    """Circle scales with TRANS_BACK (overshoots to ~1.2 then settles to 1.0)."""
    frames = []
    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)
        s = max(0.01, trans_back(t))
        frame = FrameBuilder.create_blank(W, H, BG)
        FrameBuilder.draw_circle(frame, (W // 2, H // 2), 40, (0, 255, 0), scale=s)
        frames.append(frame)
    return frames


def _make_combined_fade_scale_frames(num_frames: int = 15) -> list[np.ndarray]:
    """Alpha 1→0 + scale 1→0 simultaneously over num_frames (linear for uniform deltas)."""
    frames = []
    for i in range(num_frames):
        t = i / max(num_frames - 1, 1)
        alpha = 1.0 - t
        scale = max(0.01, 1.0 - t)
        frame = FrameBuilder.create_blank(W, H, BG)
        # Draw circle at scale, then blend with alpha
        overlay = FrameBuilder.create_blank(W, H, BG)
        FrameBuilder.draw_circle(overlay, (W // 2, H // 2), 40, (0, 255, 0), scale=scale)
        # Alpha-blend overlay onto frame
        frame = cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0)
        frames.append(frame)
    return frames


# ── T02: Smooth tween pass tests ─────────────────────────────────


class TestSmoothTweenDetection:
    """Smooth tweens should not be flagged as missing animations."""

    def test_scale_tween_ease_out_cubic(self):
        frames = _make_scale_tween_frames(num_frames=15)
        issues = detect_missing_animation(frames)
        assert issues == [], f"Scale tween should pass, got {issues}"

    def test_rotation_tween(self):
        frames = _make_rotation_tween_frames(num_frames=15, angle_rad=0.5)
        issues = detect_missing_animation(frames)
        assert issues == [], f"Rotation tween should pass, got {issues}"

    def test_trans_back_overshoot(self):
        frames = _make_overshoot_tween_frames(num_frames=15)
        issues = detect_missing_animation(frames)
        assert issues == [], f"TRANS_BACK overshoot should pass, got {issues}"

    def test_combined_alpha_and_scale(self):
        frames = _make_combined_fade_scale_frames(num_frames=15)
        issues = detect_missing_animation(frames)
        assert issues == [], f"Combined alpha+scale tween should pass, got {issues}"

    def test_scale_bump_with_content_change(self):
        """Circle scales up, color snaps at peak, then scales back.

        Mirrors the Godot score-label pattern: scale tween → abrupt content
        change at peak scale → scale tween back. The color snap creates a large
        per-frame delta, but surrounding motion (scale animation) proves it is
        embedded in an animation and should not be flagged.

        This test FAILS before T02 adds _has_following_motion suppression.
        """
        frames = []
        cx, cy = W // 2, H // 2
        base_radius = 40

        # Frames 0-3: static circle at scale 1.0, green
        for _ in range(4):
            frame = FrameBuilder.create_blank(W, H, BG)
            FrameBuilder.draw_circle(frame, (cx, cy), base_radius, (0, 255, 0), scale=1.0)
            frames.append(frame)

        # Frames 4-7: circle scales 1.0→1.2 via ease_out_cubic, green
        for i in range(4):
            t = (i + 1) / 4  # t goes 0.25, 0.5, 0.75, 1.0
            s = 1.0 + 0.2 * ease_out_cubic(t)
            frame = FrameBuilder.create_blank(W, H, BG)
            FrameBuilder.draw_circle(frame, (cx, cy), base_radius, (0, 255, 0), scale=s)
            frames.append(frame)

        # Frame 8: color snaps green→yellow at peak scale 1.2
        frame = FrameBuilder.create_blank(W, H, BG)
        FrameBuilder.draw_circle(frame, (cx, cy), base_radius, (0, 255, 255), scale=1.2)
        frames.append(frame)

        # Frames 9-14: circle scales 1.2→1.0 via trans_back, yellow
        for i in range(6):
            t = (i + 1) / 6  # t goes ~0.167..1.0
            s = max(0.01, 1.2 - 0.2 * trans_back(t))
            frame = FrameBuilder.create_blank(W, H, BG)
            FrameBuilder.draw_circle(frame, (cx, cy), base_radius, (0, 255, 255), scale=s)
            frames.append(frame)

        assert len(frames) == 15
        issues = detect_missing_animation(frames)
        assert issues == [], (
            f"Scale-bump with content change at peak should not be flagged, got {issues}"
        )


# ── T03: Simultaneous independent animations ─────────────────────


class TestSimultaneousAnimations:
    """Multiple simultaneous smooth animations should not be flagged."""

    def test_two_nodes_fade_out(self):
        """Two nodes at different positions both fade out over 15 frames."""
        frames = []
        for i in range(15):
            t = i / 14
            alpha = 1.0 - ease_out_cubic(t)
            frame = FrameBuilder.create_blank(W, H, BG)
            # Node 1: top-left area
            FrameBuilder.draw_rect(frame, (50, 30), (40, 40), (0, 255, 0), alpha=alpha)
            # Node 2: bottom-right area
            FrameBuilder.draw_rect(frame, (380, 200), (40, 40), (255, 0, 0), alpha=alpha)
            frames.append(frame)
        issues = detect_missing_animation(frames)
        assert issues == [], f"Two simultaneous fades should pass, got {issues}"

    def test_three_simultaneous_events(self):
        """One appears, one disappears, one changes color — all tweened."""
        frames = []
        for i in range(15):
            t = i / 14
            eased = ease_out_cubic(t)
            frame = FrameBuilder.create_blank(W, H, BG)
            # Node 1: appears (alpha 0→1)
            FrameBuilder.draw_rect(frame, (50, 30), (40, 40), (0, 255, 0), alpha=eased)
            # Node 2: disappears (alpha 1→0)
            FrameBuilder.draw_rect(frame, (380, 200), (40, 40), (255, 0, 0), alpha=1.0 - eased)
            # Node 3: color transition (blue → yellow)
            r = int(0 + 255 * eased)
            g = int(0 + 255 * eased)
            b = int(255 - 255 * eased)
            FrameBuilder.draw_rect(frame, (200, 110), (40, 40), (b, g, r))
            frames.append(frame)
        issues = detect_missing_animation(frames)
        assert issues == [], f"Three simultaneous tweened events should pass, got {issues}"


# ── T04: Subpixel artifact filtering ─────────────────────────────


class TestSubpixelFiltering:
    """Small anti-aliased artifacts from smooth motion should not be flagged."""

    def test_moving_node_antialiased(self):
        """Circle moving at ~5px/frame with anti-aliased edges."""
        frames = []
        for i in range(15):
            x = 50 + i * 5
            frame = FrameBuilder.create_blank(W, H, BG)
            FrameBuilder.draw_circle(frame, (x, H // 2), 20, (0, 255, 0), anti_alias=True)
            frames.append(frame)
        issues = detect_missing_animation(frames)
        assert issues == [], f"Smooth moving node should pass, got {issues}"

    def test_polygon_circle_diagonal_motion(self):
        """12-segment polygon circle moving diagonally — subpixel artifacts suppressed."""
        frames = []
        for i in range(15):
            cx = 80 + i * 6
            cy = 50 + i * 4
            frame = FrameBuilder.create_blank(W, H, BG)
            # Draw 12-segment polygon approximation of circle
            radius = 15
            pts = []
            for k in range(12):
                angle = 2 * math.pi * k / 12
                px = int(cx + radius * math.cos(angle))
                py = int(cy + radius * math.sin(angle))
                pts.append([px, py])
            pts_arr = np.array(pts, dtype=np.int32)
            cv2.fillPoly(frame, [pts_arr], (0, 200, 200), lineType=cv2.LINE_AA)
            frames.append(frame)
        issues = detect_missing_animation(frames)
        assert issues == [], f"Polygon moving diagonally should pass, got {issues}"


# ── T05: Genuinely missing animations (should fail) ──────────────


class TestGenuinelyMissing:
    """Abrupt single-frame changes must be detected."""

    def _make_abrupt_frames(self, before_fn, after_fn, snap_frame: int = 8):
        """Make 15 frames: before_fn for 0..snap_frame-1, after_fn for snap_frame..14."""
        frames = []
        for i in range(15):
            if i < snap_frame:
                frames.append(before_fn())
            else:
                frames.append(after_fn())
        return frames

    def test_visible_to_invisible(self):
        """Node snaps from visible to invisible in 1 frame → DISAPPEAR."""
        def before():
            f = FrameBuilder.create_blank(W, H, BG)
            FrameBuilder.draw_rect(f, (200, 100), (48, 48), (0, 255, 0))
            return f

        def after():
            return FrameBuilder.create_blank(W, H, BG)

        frames = self._make_abrupt_frames(before, after)
        issues = detect_missing_animation(frames)
        assert len(issues) >= 1, "visible→invisible should be flagged"
        assert any(i.change == ChangeType.DISAPPEAR for i in issues), (
            f"Expected DISAPPEAR, got {[i.change for i in issues]}"
        )

    def test_node_removed(self):
        """Node drawn then blank in 1 frame → DISAPPEAR."""
        def before():
            f = FrameBuilder.create_blank(W, H, BG)
            FrameBuilder.draw_circle(f, (240, 135), 24, (255, 100, 0))
            return f

        def after():
            return FrameBuilder.create_blank(W, H, BG)

        frames = self._make_abrupt_frames(before, after)
        issues = detect_missing_animation(frames)
        assert len(issues) >= 1, "Node removal should be flagged"
        assert any(i.change == ChangeType.DISAPPEAR for i in issues)

    def test_position_jump(self):
        """Node jumps 200px in 1 frame → flagged (DISAPPEAR+APPEAR for separate regions)."""
        def before():
            f = FrameBuilder.create_blank(W, H, BG)
            FrameBuilder.draw_rect(f, (50, 110), (48, 48), (0, 200, 200))
            return f

        def after():
            f = FrameBuilder.create_blank(W, H, BG)
            FrameBuilder.draw_rect(f, (250, 110), (48, 48), (0, 200, 200))
            return f

        frames = self._make_abrupt_frames(before, after)
        issues = detect_missing_animation(frames)
        assert len(issues) >= 1, "200px position jump should be flagged"
        # Large jump creates two separate regions → DISAPPEAR at old pos + APPEAR at new pos
        change_types = {i.change for i in issues}
        assert change_types & {ChangeType.DISAPPEAR, ChangeType.APPEAR, ChangeType.POSITION_JUMP}, (
            f"Expected position-related changes, got {change_types}"
        )

    def test_color_snap(self):
        """Node changes color abruptly in 1 frame → COLOR_CHANGE.

        Uses equiluminant colors (grayscale diff < 30) so the classifier
        falls through to COLOR_CHANGE instead of DISAPPEAR/APPEAR.
        """
        # BGR (50, 150, 200) ≈ gray 153.5 ;  BGR (200, 150, 50) ≈ gray 125.8
        # Grayscale diff ≈ 27.7 < 30  →  COLOR_CHANGE
        def before():
            f = FrameBuilder.create_blank(W, H, BG)
            FrameBuilder.draw_rect(f, (200, 100), (48, 48), (50, 150, 200))
            return f

        def after():
            f = FrameBuilder.create_blank(W, H, BG)
            FrameBuilder.draw_rect(f, (200, 100), (48, 48), (200, 150, 50))
            return f

        frames = self._make_abrupt_frames(before, after)
        issues = detect_missing_animation(frames)
        assert len(issues) >= 1, "Color snap should be flagged"
        assert any(i.change == ChangeType.COLOR_CHANGE for i in issues), (
            f"Expected COLOR_CHANGE, got {[i.change for i in issues]}"
        )


# ── T08: Metrics validation ──────────────────────────────────────


class TestMetricsValidation:
    """Validate metrics dict fields on fail cases."""

    def test_disappear_metrics(self):
        """48x48 node disappearing: verify intensity, area, and transition_frames."""
        frames = []
        for i in range(15):
            f = FrameBuilder.create_blank(W, H, BG)
            if i < 8:
                FrameBuilder.draw_rect(f, (200, 100), (48, 48), (0, 255, 0))
            frames.append(f)

        issues = detect_missing_animation(frames)
        assert len(issues) >= 1
        m = issues[0].metrics

        # intensity_before should be high (green rect), intensity_after low (background)
        assert m["intensity_before"] > 50, f"intensity_before too low: {m['intensity_before']}"
        assert m["intensity_after"] < 80, f"intensity_after too high: {m['intensity_after']}"

        # region_area_px should be roughly the rect area (48*48=2304) ± morphological expansion
        assert 500 <= m["region_area_px"] <= 5000, f"Unexpected area: {m['region_area_px']}"

        # transition_frames = 1 for abrupt changes
        assert m["transition_frames"] == 1

    def test_concurrent_events_count(self):
        """Two nodes disappearing at the same frame → concurrent_events = 1 each."""
        frames = []
        for i in range(15):
            f = FrameBuilder.create_blank(W, H, BG)
            if i < 8:
                FrameBuilder.draw_rect(f, (50, 50), (48, 48), (0, 255, 0))
                FrameBuilder.draw_rect(f, (350, 180), (48, 48), (255, 0, 0))
            frames.append(f)

        issues = detect_missing_animation(frames)
        assert len(issues) >= 2, f"Expected 2+ issues, got {len(issues)}"
        for issue in issues:
            assert issue.metrics["concurrent_events"] == 1, (
                f"Expected concurrent_events == 1 for 2 simultaneous issues, got {issue.metrics['concurrent_events']}"
            )

    def test_color_snap_metrics(self):
        """Color snap: intensity_before and intensity_after within expected range."""
        def before():
            f = FrameBuilder.create_blank(W, H, BG)
            FrameBuilder.draw_rect(f, (200, 100), (48, 48), (50, 150, 200))
            return f

        def after():
            f = FrameBuilder.create_blank(W, H, BG)
            FrameBuilder.draw_rect(f, (200, 100), (48, 48), (200, 150, 50))
            return f

        frames = []
        for i in range(15):
            frames.append(before() if i < 8 else after())

        issues = detect_missing_animation(frames)
        assert len(issues) >= 1
        m = issues[0].metrics
        # Both intensities should be moderate (equiluminant colors)
        assert 50 <= m["intensity_before"] <= 200, f"Unexpected before: {m['intensity_before']}"
        assert 50 <= m["intensity_after"] <= 200, f"Unexpected after: {m['intensity_after']}"
        assert m["transition_frames"] == 1
