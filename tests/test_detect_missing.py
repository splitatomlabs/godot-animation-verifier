"""Tests for detect_missing_animation against MISSING_ANIMATION fixtures."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from godot_animation_verifier.frames import load_frames
from godot_animation_verifier.models import IssueType
from godot_animation_verifier.models import ChangeType, Issue
from godot_animation_verifier.detect_missing import (
    MissingAnimationConfig,
    detect_missing_animation,
    _compute_delta_magnitudes,
    _find_delta_spikes,
    _find_motion_embedded_spikes,
    _extract_motion_regions,
    _color_aware_diff,
    _has_preceding_motion,
    _classify_change,
    _compute_change_type,
    _compute_screen_zone,
    _estimate_node_identity,
    _flatten_to_gray,
    _median_filter_1d,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# At 15 fps, frame index 8 (0-based) is at 8/15 * 1000 ≈ 533 ms.
SNAP_FRAME_MS_LOW = 400
SNAP_FRAME_MS_HIGH = 700


# ---------------------------------------------------------------------------
# Pass fixtures — no MISSING_ANIMATION issues should be returned
# ---------------------------------------------------------------------------


@pytest.mark.fixtures
def test_pass_static_returns_no_issues() -> None:
    frames = load_frames(FIXTURES_DIR / "missing_pass_static")
    issues = detect_missing_animation(frames)
    assert issues == [], f"Expected no issues for static scene, got {issues}"


@pytest.mark.fixtures
def test_pass_smooth_slide_returns_no_issues() -> None:
    frames = load_frames(FIXTURES_DIR / "missing_pass_smooth_slide")
    issues = detect_missing_animation(frames)
    assert issues == [], f"Expected no issues for smooth slide, got {issues}"


@pytest.mark.fixtures
def test_pass_smooth_fade_returns_no_issues() -> None:
    frames = load_frames(FIXTURES_DIR / "missing_pass_smooth_fade")
    issues = detect_missing_animation(frames)
    assert issues == [], f"Expected no issues for smooth fade, got {issues}"


# ---------------------------------------------------------------------------
# Fail fixtures — at least one MISSING_ANIMATION issue must be returned
# ---------------------------------------------------------------------------


def _assert_missing_animation_issue(issues: list, fixture_name: str) -> None:
    """Assert that the issue list contains at least one valid MISSING_ANIMATION issue."""
    assert len(issues) >= 1, f"Expected at least one issue for {fixture_name}, got none"

    missing_issues = [i for i in issues if i.type == IssueType.MISSING_ANIMATION]
    assert missing_issues, (
        f"Expected at least one MISSING_ANIMATION issue for {fixture_name}, "
        f"got types: {[i.type for i in issues]}"
    )

    for issue in missing_issues:
        assert issue.severity in ("high", "medium"), (
            f"Severity must be 'high' or 'medium', got {issue.severity!r}"
        )
        assert isinstance(issue.hint, str) and issue.hint.strip(), (
            f"hint must be a non-empty string, got {issue.hint!r}"
        )
        assert SNAP_FRAME_MS_LOW <= issue.timestamp_ms <= SNAP_FRAME_MS_HIGH, (
            f"timestamp_ms {issue.timestamp_ms} is outside expected range "
            f"[{SNAP_FRAME_MS_LOW}, {SNAP_FRAME_MS_HIGH}] ms for {fixture_name}"
        )
        # Validate new enriched fields
        assert isinstance(issue.change, ChangeType), (
            f"change must be a ChangeType, got {issue.change!r}"
        )
        assert isinstance(issue.region, dict), (
            f"region must be a dict, got {issue.region!r}"
        )
        assert all(k in issue.region for k in ("x", "y", "w", "h")), (
            f"region must have x, y, w, h keys, got {issue.region!r}"
        )
        assert isinstance(issue.screen_zone, str) and issue.screen_zone, (
            f"screen_zone must be a non-empty string, got {issue.screen_zone!r}"
        )
        assert isinstance(issue.metrics, dict) and "intensity_before" in issue.metrics, (
            f"metrics must contain intensity_before, got {issue.metrics!r}"
        )
        assert isinstance(issue.animation_suggestions, list) and len(issue.animation_suggestions) >= 2, (
            f"animation_suggestions must have >=2 entries, got {issue.animation_suggestions!r}"
        )
        assert issue.node != "unknown", (
            f"node should be estimated identity, got {issue.node!r}"
        )


@pytest.mark.fixtures
def test_fail_position_teleport_returns_issue() -> None:
    frames = load_frames(FIXTURES_DIR / "missing_fail_position_teleport")
    issues = detect_missing_animation(frames)
    _assert_missing_animation_issue(issues, "missing_fail_position_teleport")


@pytest.mark.fixtures
def test_fail_opacity_snap_returns_issue() -> None:
    frames = load_frames(FIXTURES_DIR / "missing_fail_opacity_snap")
    issues = detect_missing_animation(frames)
    _assert_missing_animation_issue(issues, "missing_fail_opacity_snap")


@pytest.mark.fixtures
def test_fail_size_jump_returns_issue() -> None:
    frames = load_frames(FIXTURES_DIR / "missing_fail_size_jump")
    issues = detect_missing_animation(frames)
    _assert_missing_animation_issue(issues, "missing_fail_size_jump")


# ---------------------------------------------------------------------------
# Config smoke test — passing a MissingAnimationConfig should not error
# ---------------------------------------------------------------------------


@pytest.mark.fixtures
def test_config_accepted_without_error() -> None:
    frames = load_frames(FIXTURES_DIR / "missing_pass_static")
    config = MissingAnimationConfig()
    issues = detect_missing_animation(frames, config=config)
    assert isinstance(issues, list)


# ---------------------------------------------------------------------------
# T02: _compute_delta_magnitudes unit tests
# ---------------------------------------------------------------------------


class TestSceneTransitionFilter:
    def test_full_frame_flash_suppressed(self) -> None:
        """A full-frame color change (scene transition) should produce no issues."""
        black = np.zeros((100, 100, 3), dtype=np.uint8)
        white = np.full((100, 100, 3), 255, dtype=np.uint8)
        frames = [black] * 5 + [white] * 5
        issues = detect_missing_animation(frames)
        assert issues == [], f"Full-frame flash should be suppressed, got {issues}"

    def test_partial_frame_snap_detected(self) -> None:
        """A small region snapping should still be detected."""
        bg = np.zeros((100, 100, 3), dtype=np.uint8)
        snap = bg.copy()
        cv2.rectangle(snap, (10, 10), (40, 40), (200, 200, 200), -1)
        frames = [bg] * 5 + [snap] * 5
        issues = detect_missing_animation(frames)
        assert len(issues) >= 1, "Partial-frame snap should be detected"


class TestComputeDeltaMagnitudes:
    def test_static_frames_produce_zero_magnitudes(self) -> None:
        frame = np.full((10, 10, 3), 128, dtype=np.uint8)
        mags = _compute_delta_magnitudes([frame, frame, frame])
        assert len(mags) == 2
        assert np.allclose(mags, 0.0)

    def test_jump_produces_spike(self) -> None:
        black = np.zeros((10, 10, 3), dtype=np.uint8)
        white = np.full((10, 10, 3), 255, dtype=np.uint8)
        mags = _compute_delta_magnitudes([black, black, white, white])
        assert len(mags) == 3
        assert mags[0] < 1.0  # static
        assert mags[1] > 100.0  # jump
        assert mags[2] < 1.0  # static

    def test_rgba_frames_handled(self) -> None:
        frame_a = np.full((10, 10, 4), (128, 128, 128, 255), dtype=np.uint8)
        frame_b = np.full((10, 10, 4), (128, 128, 128, 0), dtype=np.uint8)
        mags = _compute_delta_magnitudes([frame_a, frame_b])
        assert len(mags) == 1
        assert mags[0] > 0


# ---------------------------------------------------------------------------
# T03: _find_delta_spikes unit tests
# ---------------------------------------------------------------------------


class TestFindDeltaSpikes:
    def test_finds_spike_in_flat_signal(self) -> None:
        mags = np.array([0.0, 0.0, 0.0, 10.0, 0.0, 0.0])
        spikes = _find_delta_spikes(mags)
        assert spikes == [3]

    def test_no_spikes_in_constant_signal(self) -> None:
        mags = np.array([1.0, 1.0, 1.0, 1.0])
        spikes = _find_delta_spikes(mags)
        assert spikes == []

    def test_explicit_threshold(self) -> None:
        mags = np.array([1.0, 2.0, 5.0, 1.0])
        spikes = _find_delta_spikes(mags, threshold=3.0)
        assert spikes == [2]

    def test_empty_magnitudes(self) -> None:
        assert _find_delta_spikes(np.array([])) == []


# ---------------------------------------------------------------------------
# T04: _extract_motion_regions unit tests
# ---------------------------------------------------------------------------


class TestColorAwareDiff:
    def test_hue_only_change_detected(self) -> None:
        """Two frames differing only in hue (same grayscale) should produce nonzero diff."""
        green = np.zeros((50, 50, 3), dtype=np.uint8)
        green[10:40, 10:40] = (0, 200, 0)  # green rectangle
        red = np.zeros((50, 50, 3), dtype=np.uint8)
        red[10:40, 10:40] = (0, 0, 200)  # red rectangle (same luminance area)
        diff = _color_aware_diff(green, red)
        assert diff[25, 25] > 100, "Color-aware diff should detect hue change"

    def test_identical_frames_zero_diff(self) -> None:
        frame = np.full((50, 50, 3), 128, dtype=np.uint8)
        diff = _color_aware_diff(frame, frame)
        assert np.all(diff == 0)


class TestExtractMotionRegions:
    def test_extracts_moved_rectangle(self) -> None:
        before = np.zeros((100, 100, 3), dtype=np.uint8)
        after = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.rectangle(before, (10, 10), (40, 40), (200, 200, 200), -1)
        cv2.rectangle(after, (50, 10), (80, 40), (200, 200, 200), -1)

        regions = _extract_motion_regions(before, after, min_area=50)
        assert len(regions) >= 1
        for r in regions:
            assert "bbox" in r
            assert "centroid" in r
            assert "area" in r
            assert r["area"] >= 50

    def test_no_regions_for_identical_frames(self) -> None:
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        regions = _extract_motion_regions(frame, frame)
        assert regions == []

    def test_filters_small_regions(self) -> None:
        before = np.zeros((100, 100, 3), dtype=np.uint8)
        after = np.zeros((100, 100, 3), dtype=np.uint8)
        # Small 3x3 change — should be filtered out with min_area=50
        after[10:13, 10:13] = 255
        regions = _extract_motion_regions(before, after, min_area=50)
        assert regions == []

    def test_detects_15x15_object_teleport(self) -> None:
        """A 15x15 object teleporting should be detected with min_area=16."""
        before = np.zeros((100, 100, 3), dtype=np.uint8)
        after = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.rectangle(before, (10, 10), (25, 25), (200, 200, 200), -1)
        cv2.rectangle(after, (60, 60), (75, 75), (200, 200, 200), -1)
        regions = _extract_motion_regions(before, after, min_area=16)
        assert len(regions) >= 1, "15x15 object teleport should be detected"

    def test_detects_snap_on_checkerboard_background(self) -> None:
        """Opacity snap on a complex checkerboard background should be detected."""
        # Create checkerboard background
        bg = np.zeros((100, 100, 3), dtype=np.uint8)
        for r in range(0, 100, 10):
            for c in range(0, 100, 10):
                if (r // 10 + c // 10) % 2 == 0:
                    bg[r:r+10, c:c+10] = (180, 180, 180)
        before = bg.copy()
        after = bg.copy()
        # Add an element that appears abruptly (opacity snap)
        cv2.rectangle(after, (30, 30), (70, 70), (0, 0, 255), -1)
        regions = _extract_motion_regions(before, after, min_area=16)
        assert len(regions) >= 1, "Snap on checkerboard background should be detected"

    def test_detects_8x8_object_teleport(self) -> None:
        """An 8x8 object teleporting should be detected with min_area=16."""
        before = np.zeros((100, 100, 3), dtype=np.uint8)
        after = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.rectangle(before, (10, 10), (18, 18), (200, 200, 200), -1)
        cv2.rectangle(after, (60, 60), (68, 68), (200, 200, 200), -1)
        regions = _extract_motion_regions(before, after, min_area=16)
        assert len(regions) >= 1, "8x8 object teleport should be detected"


# ---------------------------------------------------------------------------
# T05: _has_preceding_motion unit tests
# ---------------------------------------------------------------------------


class TestHasPrecedingMotion:
    def test_returns_false_for_abrupt_snap(self) -> None:
        # 10 identical frames, then a jump at index 7→8
        static = np.zeros((50, 100, 3), dtype=np.uint8)
        cv2.rectangle(static, (10, 10), (30, 30), (200, 200, 200), -1)
        jumped = np.zeros((50, 100, 3), dtype=np.uint8)
        cv2.rectangle(jumped, (60, 10), (80, 30), (200, 200, 200), -1)

        frames = [static] * 8 + [jumped] * 2
        result = _has_preceding_motion(frames, spike_idx=7, region_bbox=(0, 0, 100, 50))
        assert not result

    def test_returns_true_for_gradual_motion(self) -> None:
        # Frames with gradually increasing change
        frames = []
        for i in range(10):
            f = np.zeros((50, 100, 3), dtype=np.uint8)
            x = 10 + i * 8  # gradual movement
            cv2.rectangle(f, (x, 10), (x + 20, 30), (200, 200, 200), -1)
            frames.append(f)
        result = _has_preceding_motion(frames, spike_idx=7, region_bbox=(0, 0, 100, 50))
        assert result


# ---------------------------------------------------------------------------
# T06: _classify_change unit tests
# ---------------------------------------------------------------------------


class TestClassifyChange:
    def test_position_change(self) -> None:
        region = {
            "bbox": (10, 10, 400, 40),
            "centroid": (210.0, 30.0),
            "area": 1600,  # fill_ratio = 1600 / (400*40) = 0.1
            "mean_intensity_before": 100.0,
            "mean_intensity_after": 100.0,
        }
        prop, hint = _classify_change(region)
        assert prop == "position"
        assert "Tween" in hint

    def test_opacity_change(self) -> None:
        region = {
            "bbox": (10, 10, 40, 40),
            "centroid": (30.0, 30.0),
            "area": 1600,  # fill_ratio = 1.0
            "mean_intensity_before": 128.0,
            "mean_intensity_after": 10.0,
        }
        prop, hint = _classify_change(region)
        assert prop == "opacity"
        assert "fade" in hint.lower() or "alpha" in hint.lower()

    def test_size_change(self) -> None:
        region = {
            "bbox": (10, 10, 50, 50),
            "centroid": (35.0, 35.0),
            "area": 2000,  # fill_ratio = 2000/2500 = 0.8
            "mean_intensity_before": 100.0,
            "mean_intensity_after": 105.0,
        }
        prop, hint = _classify_change(region)
        assert prop == "size"
        assert "scale" in hint.lower() or "Tween" in hint


# ---------------------------------------------------------------------------
# T03: _flatten_to_gray unit tests
# ---------------------------------------------------------------------------


class TestComputeChangeType:
    def test_position_jump(self) -> None:
        region = {
            "bbox": (10, 10, 400, 40),
            "centroid": (210.0, 30.0),
            "area": 1600,
            "mean_intensity_before": 100.0,
            "mean_intensity_after": 100.0,
        }
        assert _compute_change_type(region) == ChangeType.POSITION_JUMP

    def test_disappear(self) -> None:
        region = {
            "bbox": (10, 10, 40, 40),
            "centroid": (30.0, 30.0),
            "area": 1600,
            "mean_intensity_before": 128.0,
            "mean_intensity_after": 10.0,
        }
        assert _compute_change_type(region) == ChangeType.DISAPPEAR

    def test_appear(self) -> None:
        region = {
            "bbox": (10, 10, 40, 40),
            "centroid": (30.0, 30.0),
            "area": 1600,
            "mean_intensity_before": 10.0,
            "mean_intensity_after": 128.0,
        }
        assert _compute_change_type(region) == ChangeType.APPEAR

    def test_large_area_falls_through_to_color_change(self) -> None:
        """Large changed-pixel area without intensity diff → COLOR_CHANGE (not SIZE_CHANGE)."""
        region = {
            "bbox": (10, 10, 50, 50),
            "centroid": (35.0, 35.0),
            "area": 2000,
            "mean_intensity_before": 100.0,
            "mean_intensity_after": 105.0,
        }
        assert _compute_change_type(region) == ChangeType.COLOR_CHANGE

    def test_color_change_fallback(self) -> None:
        region = {
            "bbox": (10, 10, 10, 10),
            "centroid": (15.0, 15.0),
            "area": 80,  # fill_ratio = 80/100 = 0.8, area <= 200, intensity_diff <= 30
            "mean_intensity_before": 100.0,
            "mean_intensity_after": 105.0,
        }
        assert _compute_change_type(region) == ChangeType.COLOR_CHANGE


class TestEstimateNodeIdentity:
    def test_bright_yellow_element(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[10:58, 10:58] = (0, 255, 255)  # yellow in BGR
        result = _estimate_node_identity(frame, (10, 10, 48, 48))
        assert "yellow" in result
        assert "48x48" in result

    def test_dark_element(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[10:30, 10:30] = (10, 10, 10)
        result = _estimate_node_identity(frame, (10, 10, 20, 20))
        assert "dark" in result

    def test_red_element(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        frame[10:30, 10:30] = (0, 0, 200)  # red in BGR
        result = _estimate_node_identity(frame, (10, 10, 20, 20))
        assert "red" in result

    def test_unknown_for_empty_region(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        assert _estimate_node_identity(frame, (10, 10, 0, 0)) == "unknown"

    def test_grayscale_frame(self) -> None:
        frame = np.full((100, 100), 200, dtype=np.uint8)
        result = _estimate_node_identity(frame, (10, 10, 20, 20))
        assert "bright" in result
        assert "gray" in result

    def test_rgba_frame(self) -> None:
        frame = np.zeros((100, 100, 4), dtype=np.uint8)
        frame[10:30, 10:30] = (255, 0, 0, 255)  # blue in BGRA
        result = _estimate_node_identity(frame, (10, 10, 20, 20))
        assert "blue" in result

    def test_edge_clipping_uses_actual_dimensions(self) -> None:
        """bbox extending past frame edge should use clamped dimensions."""
        frame = np.full((50, 50, 3), (0, 200, 200), dtype=np.uint8)  # yellow
        result = _estimate_node_identity(frame, (40, 40, 20, 20))
        assert "10x10" in result  # clamped from 20x20

    def test_fully_out_of_bounds_returns_unknown(self) -> None:
        frame = np.zeros((50, 50, 3), dtype=np.uint8)
        assert _estimate_node_identity(frame, (60, 60, 10, 10)) == "unknown"


class TestComputeScreenZone:
    def test_top_left(self) -> None:
        assert _compute_screen_zone((0, 0, 10, 10), 300, 300) == "top-left"

    def test_top_center(self) -> None:
        assert _compute_screen_zone((120, 0, 10, 10), 300, 300) == "top-center"

    def test_top_right(self) -> None:
        assert _compute_screen_zone((250, 0, 10, 10), 300, 300) == "top-right"

    def test_center_left(self) -> None:
        assert _compute_screen_zone((0, 120, 10, 10), 300, 300) == "center-left"

    def test_center(self) -> None:
        assert _compute_screen_zone((120, 120, 10, 10), 300, 300) == "center"

    def test_center_right(self) -> None:
        assert _compute_screen_zone((250, 120, 10, 10), 300, 300) == "center-right"

    def test_bottom_left(self) -> None:
        assert _compute_screen_zone((0, 250, 10, 10), 300, 300) == "bottom-left"

    def test_bottom_center(self) -> None:
        assert _compute_screen_zone((120, 250, 10, 10), 300, 300) == "bottom-center"

    def test_bottom_right(self) -> None:
        assert _compute_screen_zone((250, 250, 10, 10), 300, 300) == "bottom-right"

    def test_exact_center_of_frame(self) -> None:
        # bbox centered at (150, 150) in 300x300 frame
        assert _compute_screen_zone((145, 145, 10, 10), 300, 300) == "center"

    def test_boundary_at_third(self) -> None:
        # cx = 100, exactly at first third boundary of 300px → center column
        assert _compute_screen_zone((95, 95, 10, 10), 300, 300) == "center"


class TestFlattenToGray:
    def test_3_channel_passthrough(self) -> None:
        bgr = np.full((10, 10, 3), (100, 150, 200), dtype=np.uint8)
        gray = _flatten_to_gray(bgr)
        expected = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        np.testing.assert_array_equal(gray, expected)

    def test_4_channel_opaque_same_as_rgb(self) -> None:
        bgr = np.full((10, 10, 3), (100, 150, 200), dtype=np.uint8)
        bgra = np.dstack([bgr, np.full((10, 10), 255, dtype=np.uint8)])
        gray_bgr = _flatten_to_gray(bgr)
        gray_bgra = _flatten_to_gray(bgra)
        np.testing.assert_array_equal(gray_bgra, gray_bgr)

    def test_4_channel_transparent_is_black(self) -> None:
        bgra = np.full((10, 10, 4), (100, 150, 200, 0), dtype=np.uint8)
        gray = _flatten_to_gray(bgra)
        assert np.all(gray == 0)

    def test_4_channel_partial_alpha_blended(self) -> None:
        bgra = np.full((10, 10, 4), (200, 200, 200, 128), dtype=np.uint8)
        gray = _flatten_to_gray(bgra)
        # Partial alpha should produce values between 0 and full-opaque gray
        full_opaque = _flatten_to_gray(np.full((10, 10, 4), (200, 200, 200, 255), dtype=np.uint8))
        assert np.all(gray < full_opaque)
        assert np.all(gray > 0)

    def test_single_channel_passthrough(self) -> None:
        gray_in = np.full((10, 10), 128, dtype=np.uint8)
        gray_out = _flatten_to_gray(gray_in)
        np.testing.assert_array_equal(gray_out, gray_in)


# ---------------------------------------------------------------------------
# T04: _median_filter_1d unit tests
# ---------------------------------------------------------------------------


class TestMedianFilter:
    def test_odd_kernel_smoothing(self) -> None:
        arr = np.array([1.0, 100.0, 1.0, 1.0, 1.0])
        result = _median_filter_1d(arr, size=3)
        # The spike at index 1 should be smoothed
        assert result[1] < 100.0
        assert len(result) == len(arr)

    def test_even_length_array(self) -> None:
        arr = np.array([1.0, 2.0, 3.0, 4.0])
        result = _median_filter_1d(arr, size=3)
        assert len(result) == len(arr)

    def test_single_element_array(self) -> None:
        arr = np.array([42.0])
        result = _median_filter_1d(arr, size=3)
        assert len(result) == 1
        assert result[0] == 42.0

    def test_preserves_array_length(self) -> None:
        arr = np.arange(20, dtype=np.float64)
        result = _median_filter_1d(arr, size=5)
        assert len(result) == len(arr)


# ---------------------------------------------------------------------------
# _find_motion_embedded_spikes unit tests
# ---------------------------------------------------------------------------


class TestFindMotionEmbeddedSpikes:
    def test_spike_above_near_zero_neighbors_detected(self) -> None:
        """A spike 5x above near-zero neighbors should be detected."""
        mags = np.array([0.01, 0.02, 0.01, 5.0, 0.02, 0.01, 0.01])
        global_spikes: list[int] = []
        result = _find_motion_embedded_spikes(mags, global_spikes)
        assert 3 in result

    def test_spike_above_motion_baseline_detected(self) -> None:
        """A spike 2.5x above a motion baseline should be detected."""
        # Simulate smooth motion at ~2.0, with a snap at index 5 of ~5.0
        mags = np.array([2.0, 2.1, 1.9, 2.0, 2.1, 5.0, 2.0, 1.9, 2.0, 2.1])
        global_spikes: list[int] = []
        result = _find_motion_embedded_spikes(mags, global_spikes)
        assert 5 in result

    def test_small_spike_not_detected(self) -> None:
        """A spike only 1.3x above neighbors should NOT be detected."""
        mags = np.array([2.0, 2.1, 1.9, 2.6, 2.0, 2.1, 1.9])
        global_spikes: list[int] = []
        result = _find_motion_embedded_spikes(mags, global_spikes)
        assert 3 not in result

    def test_already_detected_global_spikes_not_duplicated(self) -> None:
        """Frames already in global_spikes should be skipped."""
        mags = np.array([0.01, 0.02, 0.01, 5.0, 0.02, 0.01, 0.01])
        global_spikes = [3]
        result = _find_motion_embedded_spikes(mags, global_spikes)
        assert 3 not in result
