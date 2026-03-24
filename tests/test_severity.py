"""Severity calibration tests (T06).

Validates severity assignments and small-region filtering.
"""

from __future__ import annotations

import numpy as np
import pytest

from godot_animation_verifier.detect_missing import (
    MissingAnimationConfig,
    detect_missing_animation,
)
from tests.helpers.easing import ease_out_cubic
from tests.helpers.frame_builder import FrameBuilder

W, H = 480, 270

BG = (30, 30, 30)


class TestSeverityCalibration:

    def test_large_node_disappear_severity_high(self):
        """48x48 node disappearing abruptly → severity 'high' (opacity change)."""
        frames = []
        for i in range(15):
            f = FrameBuilder.create_blank(W, H, BG)
            if i < 8:
                FrameBuilder.draw_rect(f, (200, 100), (48, 48), (0, 255, 0))
            frames.append(f)

        issues = detect_missing_animation(frames)
        assert len(issues) >= 1, "48x48 disappear should be flagged"
        assert any(i.severity == "high" for i in issues), (
            f"Expected severity 'high', got {[i.severity for i in issues]}"
        )

    def test_tiny_region_not_flagged(self):
        """3x3 region change is too small to trigger detection at all.

        A 3x3 pixel change produces local window mean delta < 3.0
        (9 changed pixels in a 32x32=1024 window), below the local spike threshold.
        """
        frames = []
        for i in range(15):
            f = FrameBuilder.create_blank(W, H, BG)
            if i < 8:
                FrameBuilder.draw_rect(f, (240, 135), (3, 3), (0, 255, 0))
            frames.append(f)

        issues = detect_missing_animation(frames)
        assert issues == [], f"3x3 region should not be flagged, got {issues}"

    def test_smooth_tween_large_nodes_not_flagged(self):
        """Two 48x48 nodes disappearing with smooth tweens → not flagged."""
        frames = []
        for i in range(15):
            t = i / 14
            alpha = 1.0 - ease_out_cubic(t)
            f = FrameBuilder.create_blank(W, H, BG)
            FrameBuilder.draw_rect(f, (100, 100), (48, 48), (0, 255, 0), alpha=alpha)
            FrameBuilder.draw_rect(f, (300, 100), (48, 48), (255, 0, 0), alpha=alpha)
            frames.append(f)

        issues = detect_missing_animation(frames)
        assert issues == [], f"Smooth tween of large nodes should pass, got {issues}"
