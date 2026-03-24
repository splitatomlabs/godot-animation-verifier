"""Region attribution tests (T07).

Validates bbox accuracy and screen_zone for nodes at known positions.
"""

from __future__ import annotations

import numpy as np
import pytest

from godot_animation_verifier.detect_missing import detect_missing_animation
from tests.helpers.frame_builder import FrameBuilder

W, H = 480, 270

BG = (30, 30, 30)
MARGIN = 10  # ±10px tolerance for bbox overlap


def _make_abrupt_disappear(node_pos, node_size, color=(0, 255, 0)):
    """15 frames: node visible 0-7, gone 8-14."""
    frames = []
    for i in range(15):
        f = FrameBuilder.create_blank(W, H, BG)
        if i < 8:
            FrameBuilder.draw_rect(f, node_pos, node_size, color)
        frames.append(f)
    return frames


def _bbox_overlaps(reported, expected_pos, expected_size, margin=MARGIN):
    """Check if reported bbox overlaps expected node position within margin."""
    rx, ry, rw, rh = reported["x"], reported["y"], reported["w"], reported["h"]
    ex, ey = expected_pos
    ew, eh = expected_size
    # Overlap check: reported rect (expanded by margin) must intersect expected rect
    return (
        rx - margin <= ex + ew  # reported left doesn't exceed expected right
        and rx + rw + margin >= ex  # reported right doesn't fall before expected left
        and ry - margin <= ey + eh
        and ry + rh + margin >= ey
    )


class TestRegionAttribution:

    def test_center_node(self):
        """Node at center → region bbox overlaps center, screen_zone = 'center'."""
        pos = (W // 2 - 24, H // 2 - 24)
        size = (48, 48)
        frames = _make_abrupt_disappear(pos, size)
        issues = detect_missing_animation(frames)
        assert len(issues) >= 1
        issue = issues[0]
        assert _bbox_overlaps(issue.region, pos, size), (
            f"Bbox {issue.region} should overlap node at {pos} size {size}"
        )
        assert issue.screen_zone == "center", f"Expected 'center', got {issue.screen_zone!r}"

    def test_top_left_node(self):
        """Node at top-left → region bbox overlaps, screen_zone = 'top-left'."""
        pos = (20, 10)
        size = (48, 48)
        frames = _make_abrupt_disappear(pos, size)
        issues = detect_missing_animation(frames)
        assert len(issues) >= 1
        issue = issues[0]
        assert _bbox_overlaps(issue.region, pos, size), (
            f"Bbox {issue.region} should overlap node at {pos} size {size}"
        )
        assert issue.screen_zone == "top-left", f"Expected 'top-left', got {issue.screen_zone!r}"

    def test_bottom_right_node(self):
        """Node at bottom-right → region bbox overlaps, screen_zone = 'bottom-right'."""
        pos = (W - 68, H - 58)
        size = (48, 48)
        frames = _make_abrupt_disappear(pos, size)
        issues = detect_missing_animation(frames)
        assert len(issues) >= 1
        issue = issues[0]
        assert _bbox_overlaps(issue.region, pos, size), (
            f"Bbox {issue.region} should overlap node at {pos} size {size}"
        )
        assert issue.screen_zone == "bottom-right", f"Expected 'bottom-right', got {issue.screen_zone!r}"

    def test_top_center_node(self):
        """Node at top-center → screen_zone = 'top-center'."""
        pos = (W // 2 - 24, 10)
        size = (48, 48)
        frames = _make_abrupt_disappear(pos, size)
        issues = detect_missing_animation(frames)
        assert len(issues) >= 1
        assert issues[0].screen_zone == "top-center", (
            f"Expected 'top-center', got {issues[0].screen_zone!r}"
        )
