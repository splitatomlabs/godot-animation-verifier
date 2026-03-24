"""Unit tests for test helper modules (easing + frame_builder)."""

import numpy as np
import pytest

from tests.helpers.easing import ease_out_cubic, trans_back, trans_elastic
from tests.helpers.frame_builder import FrameBuilder


# ── Easing functions ──────────────────────────────────────────────


class TestEaseOutCubic:
    def test_boundaries(self):
        assert ease_out_cubic(0.0) == pytest.approx(0.0)
        assert ease_out_cubic(1.0) == pytest.approx(1.0)

    def test_midpoint_above_linear(self):
        # Ease-out should be above 0.5 at t=0.5 (fast start)
        assert ease_out_cubic(0.5) > 0.5

    def test_monotonic(self):
        values = [ease_out_cubic(t / 100) for t in range(101)]
        for a, b in zip(values, values[1:]):
            assert b >= a


class TestTransBack:
    def test_boundaries(self):
        assert trans_back(0.0) == pytest.approx(0.0, abs=1e-6)
        assert trans_back(1.0) == pytest.approx(1.0, abs=1e-6)

    def test_overshoots(self):
        # Should exceed 1.0 somewhere in (0.5, 1.0)
        values = [trans_back(t / 100) for t in range(50, 100)]
        assert max(values) > 1.0

    def test_settles_to_one(self):
        assert trans_back(1.0) == pytest.approx(1.0, abs=1e-6)


class TestTransElastic:
    def test_boundaries(self):
        assert trans_elastic(0.0) == pytest.approx(0.0)
        assert trans_elastic(1.0) == pytest.approx(1.0)

    def test_oscillates(self):
        # Should oscillate around 1.0 in the middle range
        values = [trans_elastic(t / 100) for t in range(1, 100)]
        assert max(values) > 1.0  # overshoots
        # Early values may undershoot
        assert min(values) < 1.0


# ── FrameBuilder ──────────────────────────────────────────────────


class TestFrameBuilder:
    def test_create_blank(self):
        frame = FrameBuilder.create_blank(480, 270, (30, 30, 30))
        assert frame.shape == (270, 480, 3)
        assert frame.dtype == np.uint8
        np.testing.assert_array_equal(frame[0, 0], [30, 30, 30])

    def test_draw_circle(self):
        frame = FrameBuilder.create_blank()
        FrameBuilder.draw_circle(frame, (240, 135), 20, (0, 255, 0))
        # Center pixel should be green
        assert frame[135, 240, 1] == 255

    def test_draw_circle_scale(self):
        frame = FrameBuilder.create_blank()
        FrameBuilder.draw_circle(frame, (240, 135), 20, (0, 255, 0), scale=0.5)
        # Pixel at radius 15 from center should still be background
        assert frame[135, 240 + 15, 1] != 255

    def test_draw_rect(self):
        frame = FrameBuilder.create_blank(480, 270, (0, 0, 0))
        FrameBuilder.draw_rect(frame, (100, 100), (50, 50), (255, 0, 0))
        np.testing.assert_array_equal(frame[125, 125], [255, 0, 0])

    def test_draw_rect_alpha(self):
        frame = FrameBuilder.create_blank(480, 270, (0, 0, 0))
        FrameBuilder.draw_rect(frame, (100, 100), (50, 50), (200, 0, 0), alpha=0.5)
        # Should be ~100 due to 50% blend with black
        assert 90 <= frame[125, 125, 0] <= 110

    def test_composite_region(self):
        base = FrameBuilder.create_blank(480, 270, (0, 0, 0))
        overlay = np.full((20, 20, 3), 200, dtype=np.uint8)
        FrameBuilder.composite_region(base, overlay, (10, 10), alpha=1.0)
        np.testing.assert_array_equal(base[15, 15], [200, 200, 200])

    def test_composite_region_alpha(self):
        base = FrameBuilder.create_blank(480, 270, (100, 100, 100))
        overlay = np.full((20, 20, 3), 200, dtype=np.uint8)
        FrameBuilder.composite_region(base, overlay, (10, 10), alpha=0.5)
        # Should be ~150 (midpoint of 100 and 200)
        assert 140 <= base[15, 15, 0] <= 160
