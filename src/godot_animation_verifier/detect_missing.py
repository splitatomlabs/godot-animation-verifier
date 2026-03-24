"""MISSING_ANIMATION detector — detects abrupt visual state changes with no transition."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from godot_animation_verifier.models import ChangeType, Issue, IssueType
from godot_animation_verifier.suggestions import get_animation_suggestions


@dataclass
class MissingAnimationConfig:
    """Configuration for MISSING_ANIMATION detection."""

    delta_threshold: float | None = None
    min_region_area: int = 16
    lookback_frames: int = 5
    median_filter_size: int = 3
    scene_transition_threshold: float = 0.40


def _flatten_to_gray(frame: np.ndarray) -> np.ndarray:
    """Convert a frame to grayscale, compositing BGRA onto black background."""
    if frame.ndim == 2:
        return frame
    if frame.shape[2] == 4:
        bgr = frame[:, :, :3].astype(np.float32)
        alpha = frame[:, :, 3:4].astype(np.float32) / 255.0
        composited = (bgr * alpha).astype(np.uint8)
        return cv2.cvtColor(composited, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


# ---------------------------------------------------------------------------
# T02: Frame delta magnitude computation
# ---------------------------------------------------------------------------


def _median_filter_1d(arr: np.ndarray, size: int) -> np.ndarray:
    """Apply a 1D median filter with reflect-padding (no scipy dependency)."""
    half = size // 2
    padded = np.pad(arr, half, mode="reflect")
    return np.array([np.median(padded[i : i + size]) for i in range(len(arr))])


def _compute_delta_magnitudes(frames: list[np.ndarray], median_filter_size: int = 3) -> np.ndarray:
    """Compute per-frame-pair delta magnitudes.

    Returns array of length len(frames)-1 where each element is the mean
    absolute difference between consecutive grayscale frames.
    The median filter smooths the baseline for threshold computation but
    spike detection uses the raw signal to avoid suppressing single-frame events.
    """
    grays = [_flatten_to_gray(f) for f in frames]
    mags = np.array(
        [cv2.absdiff(grays[i], grays[i + 1]).mean() for i in range(len(grays) - 1)],
        dtype=np.float64,
    )
    return mags


# ---------------------------------------------------------------------------
# T03: Delta spike detection
# ---------------------------------------------------------------------------

ABSOLUTE_FLOOR = 0.8  # minimum threshold regardless of signal statistics


def _find_delta_spikes(magnitudes: np.ndarray, threshold: float | None = None, median_filter_size: int = 3) -> list[int]:
    """Find frame indices where magnitude exceeds threshold.

    Default threshold: max(mean + 3*std, ABSOLUTE_FLOOR) computed on the
    median-filtered signal (to get a stable baseline), applied to the raw signal.
    """
    if len(magnitudes) == 0:
        return []
    if threshold is None:
        # Use median-filtered signal for stable baseline statistics
        if len(magnitudes) >= median_filter_size and median_filter_size > 1:
            smoothed = _median_filter_1d(magnitudes, median_filter_size)
        else:
            smoothed = magnitudes
        mean = smoothed.mean()
        std = smoothed.std()
        threshold = max(mean + 3 * std, ABSOLUTE_FLOOR)
    # Detect spikes in the raw (unfiltered) signal
    return sorted(int(i) for i in np.where(magnitudes > threshold)[0])


def _max_local_delta(gray1: np.ndarray, gray2: np.ndarray, window_size: int = 32) -> float:
    """Compute the maximum mean delta across all sliding windows."""
    diff = cv2.absdiff(gray1, gray2)
    h, w = diff.shape
    max_local = 0.0
    step = window_size // 2
    for y in range(0, h - window_size + 1, step):
        for x in range(0, w - window_size + 1, step):
            local_mean = float(diff[y:y + window_size, x:x + window_size].mean())
            if local_mean > max_local:
                max_local = local_mean
    return max_local


def _find_motion_embedded_spikes(
    magnitudes: np.ndarray,
    global_spikes: list[int],
    window: int = 3,
    ratio_threshold: float = 2.0,
) -> list[int]:
    """Find spikes embedded in smooth motion that global thresholding misses.

    For each frame not already in global_spikes, compare its delta to the
    median of its preceding neighbors (backward window). This catches spikes
    co-occurring with ongoing motion where symmetric windows would include
    post-spike elevated frames and inflate the median.

    A secondary forward check requires delta > 1.2 × following median to
    filter out smooth acceleration ramps (where each frame is naturally higher
    than its predecessors).

    Flag if delta > ratio_threshold × preceding median AND delta > 1.2 ×
    following median, or if the preceding baseline is near-zero (< 0.1).
    """
    spike_set = set(global_spikes)
    extra: list[int] = []
    n = len(magnitudes)

    for i in range(n):
        if i in spike_set:
            continue
        if magnitudes[i] < ABSOLUTE_FLOOR:
            continue

        # Backward window: preceding neighbors only
        lo = max(0, i - window)
        preceding = [magnitudes[j] for j in range(lo, i)]
        if not preceding:
            # No preceding context — skip; first-frame spikes are handled by
            # global detection and don't need embedded spike logic.
            continue

        pre_median = float(np.median(preceding))

        if pre_median < 0.1 or magnitudes[i] > ratio_threshold * pre_median:
            # Either near-zero baseline (spike isolated above floor) or
            # spike exceeds ratio threshold vs preceding median.
            # Apply forward check to filter smooth acceleration ramps
            # (where following frames are >= current, e.g. ease-in).
            hi = min(n, i + 1 + window)
            following = [magnitudes[j] for j in range(i + 1, hi)]
            if not following:
                extra.append(i)
            else:
                fwd_median = float(np.median(following))
                if fwd_median < 0.1 or magnitudes[i] > 1.2 * fwd_median:
                    extra.append(i)

    return extra


def _find_local_region_spikes(
    frames: list[np.ndarray],
    global_spikes: list[int],
    window_size: int = 32,
) -> list[int]:
    """Find additional spikes where a local region has a large delta even if global mean is low.

    Uses a sliding window to detect small-object teleports lost in global averaging.
    Only triggers when the local spike is temporally isolated (not part of smooth motion).
    Returns frame indices not already in global_spikes.
    """
    spike_set = set(global_spikes)
    extra_spikes = []
    grays = [_flatten_to_gray(f) for f in frames]
    n = len(grays) - 1

    # Pre-compute max local deltas for all pairs
    local_deltas = [_max_local_delta(grays[i], grays[i + 1], window_size) for i in range(n)]

    for i in range(n):
        if i in spike_set:
            continue
        ld = local_deltas[i]
        if ld < 3.0:
            continue
        # Check temporal isolation: spike must be >3x the max neighbor
        # within a ±3 window (wider than ±1 to avoid false positives from
        # residual jitter after nearby smooth motion).
        lo = max(0, i - 3)
        hi = min(n, i + 4)
        max_neighbor = max(
            (local_deltas[j] for j in range(lo, hi) if j != i),
            default=0.0,
        )
        max_neighbor = max(max_neighbor, 0.01)
        if ld > 3.0 * max_neighbor:
            extra_spikes.append(i)

    return extra_spikes


# ---------------------------------------------------------------------------
# T04: Motion region extraction
# ---------------------------------------------------------------------------


def _color_aware_diff(frame_before: np.ndarray, frame_after: np.ndarray) -> np.ndarray:
    """Compute per-channel absdiff and take max across channels.

    Returns a single-channel (grayscale) diff image that captures hue-only
    changes that grayscale conversion would miss.
    """
    # Handle grayscale inputs (or mismatched channels)
    if frame_before.ndim == 2 or frame_after.ndim == 2:
        return cv2.absdiff(_flatten_to_gray(frame_before), _flatten_to_gray(frame_after))

    # Composite BGRA onto black if needed
    def _to_bgr(f: np.ndarray) -> np.ndarray:
        if f.shape[2] == 4:
            bgr = f[:, :, :3].astype(np.float32)
            alpha = f[:, :, 3:4].astype(np.float32) / 255.0
            return (bgr * alpha).astype(np.uint8)
        return f[:, :, :3]

    bgr_before = _to_bgr(frame_before)
    bgr_after = _to_bgr(frame_after)

    # Per-channel absdiff, take max across B, G, R
    diff = cv2.absdiff(bgr_before, bgr_after)
    return np.max(diff, axis=2)


def _extract_motion_regions(
    frame_before: np.ndarray,
    frame_after: np.ndarray,
    min_area: int = 16,
) -> list[dict]:
    """Extract motion regions between two frames via connected components."""
    gray_before = _flatten_to_gray(frame_before)
    gray_after = _flatten_to_gray(frame_after)

    diff = _color_aware_diff(frame_before, frame_after)
    otsu_thresh, binary = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Fall back to a low fixed threshold if Otsu picks too high (e.g. noisy backgrounds)
    if otsu_thresh > 50:
        _, binary = cv2.threshold(diff, 15, 255, cv2.THRESH_BINARY)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    binary = cv2.dilate(binary, kernel, iterations=1)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary)

    regions = []
    for label_id in range(1, num_labels):  # skip background
        area = int(stats[label_id, cv2.CC_STAT_AREA])
        if area < min_area:
            continue
        x = int(stats[label_id, cv2.CC_STAT_LEFT])
        y = int(stats[label_id, cv2.CC_STAT_TOP])
        w = int(stats[label_id, cv2.CC_STAT_WIDTH])
        h = int(stats[label_id, cv2.CC_STAT_HEIGHT])
        cx, cy = float(centroids[label_id][0]), float(centroids[label_id][1])

        mask = (labels == label_id)
        mean_before = float(gray_before[mask].mean())
        mean_after = float(gray_after[mask].mean())

        regions.append({
            "bbox": (x, y, w, h),
            "centroid": (cx, cy),
            "area": area,
            "mean_intensity_before": mean_before,
            "mean_intensity_after": mean_after,
        })

    # Contour-based fallback for irregular shapes missed by connected components
    if not regions:
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area = int(cv2.contourArea(contour))
            if area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            moments = cv2.moments(contour)
            if moments["m00"] > 0:
                cx = float(moments["m10"] / moments["m00"])
                cy = float(moments["m01"] / moments["m00"])
            else:
                cx, cy = float(x + w / 2), float(y + h / 2)
            mask = np.zeros(binary.shape, dtype=np.uint8)
            cv2.drawContours(mask, [contour], -1, 255, -1)
            contour_mask = mask > 0
            mean_before = float(gray_before[contour_mask].mean()) if contour_mask.any() else 0.0
            mean_after = float(gray_after[contour_mask].mean()) if contour_mask.any() else 0.0
            regions.append({
                "bbox": (x, y, w, h),
                "centroid": (cx, cy),
                "area": area,
                "mean_intensity_before": mean_before,
                "mean_intensity_after": mean_after,
            })

    return regions


# ---------------------------------------------------------------------------
# T05: Temporal validation
# ---------------------------------------------------------------------------


def _has_preceding_motion(
    frames: list[np.ndarray],
    spike_idx: int,
    region_bbox: tuple,
    lookback: int = 5,
) -> bool:
    """Check if there was gradual motion in the region before the spike.

    spike_idx is a delta index (transition between frame spike_idx and spike_idx+1).
    Returns True if preceding frames show gradual ramp-up (i.e., NOT a snap).
    """
    x, y, w, h = region_bbox

    # We need at least 2 preceding frames to measure ramp-up
    start = max(0, spike_idx - lookback)
    if spike_idx - start < 2:
        return False

    # Measure cumulative delta in the region across preceding frames (grayscale + color)
    preceding_deltas = []
    preceding_color_deltas = []
    for i in range(start, spike_idx):
        g1 = _flatten_to_gray(frames[i])[y : y + h, x : x + w]
        g2 = _flatten_to_gray(frames[i + 1])[y : y + h, x : x + w]
        delta = cv2.absdiff(g1, g2).mean()
        preceding_deltas.append(delta)
        # Color-aware delta for the region
        c1 = _color_aware_diff(frames[i], frames[i + 1])
        preceding_color_deltas.append(float(c1[y : y + h, x : x + w].mean()))

    # Measure the spike delta itself
    g_spike_before = _flatten_to_gray(frames[spike_idx])[y : y + h, x : x + w]
    g_spike_after = _flatten_to_gray(frames[spike_idx + 1])[y : y + h, x : x + w]
    spike_delta = cv2.absdiff(g_spike_before, g_spike_after).mean()

    # Color-aware spike delta
    c_spike = _color_aware_diff(frames[spike_idx], frames[spike_idx + 1])
    spike_color_delta = float(c_spike[y : y + h, x : x + w].mean())

    if spike_delta < 1e-6 and spike_color_delta < 1e-6:
        return False

    cumulative_preceding = sum(preceding_deltas)
    max_preceding = max(preceding_deltas) if preceding_deltas else 0.0
    max_preceding_color = max(preceding_color_deltas) if preceding_color_deltas else 0.0

    # If the spike is >3x the max preceding delta, it's a snap regardless
    if max_preceding > 0 and spike_delta > 3.0 * max_preceding:
        return False

    # If the color spike is >3x the max preceding color delta, it's a color snap
    if max_preceding_color > 0 and spike_color_delta > 3.0 * max_preceding_color:
        return False

    return cumulative_preceding > 0.10 * spike_delta


def _has_following_motion(
    frames: list[np.ndarray],
    spike_idx: int,
    region_bbox: tuple,
    lookforward: int = 5,
) -> bool:
    """Check if there is gradual motion in the region after the spike.

    spike_idx is a delta index (transition between frame spike_idx and spike_idx+1).
    Returns True if following frames show gradual continuation (i.e., NOT a snap).
    """
    x, y, w, h = region_bbox

    # We need at least 2 following frames to measure wind-down
    end = min(len(frames) - 1, spike_idx + 1 + lookforward)
    if end - (spike_idx + 1) < 2:
        return False

    # Measure cumulative delta in the region across following frames (grayscale + color)
    following_deltas = []
    following_color_deltas = []
    for i in range(spike_idx + 1, end):
        g1 = _flatten_to_gray(frames[i])[y : y + h, x : x + w]
        g2 = _flatten_to_gray(frames[i + 1])[y : y + h, x : x + w]
        delta = cv2.absdiff(g1, g2).mean()
        following_deltas.append(delta)
        # Color-aware delta for the region
        c1 = _color_aware_diff(frames[i], frames[i + 1])
        following_color_deltas.append(float(c1[y : y + h, x : x + w].mean()))

    # Measure the spike delta itself
    g_spike_before = _flatten_to_gray(frames[spike_idx])[y : y + h, x : x + w]
    g_spike_after = _flatten_to_gray(frames[spike_idx + 1])[y : y + h, x : x + w]
    spike_delta = cv2.absdiff(g_spike_before, g_spike_after).mean()

    # Color-aware spike delta
    c_spike = _color_aware_diff(frames[spike_idx], frames[spike_idx + 1])
    spike_color_delta = float(c_spike[y : y + h, x : x + w].mean())

    if spike_delta < 1e-6 and spike_color_delta < 1e-6:
        return False

    cumulative_following = sum(following_deltas)
    max_following = max(following_deltas) if following_deltas else 0.0
    max_following_color = max(following_color_deltas) if following_color_deltas else 0.0

    # If the spike dominates in BOTH grayscale AND color, it's a snap regardless.
    # If either channel shows proportional motion, the spike is likely embedded
    # in an animation (e.g., color change during a scale tween).
    gray_ratio_too_high = max_following > 0 and spike_delta > 3.0 * max_following
    color_ratio_too_high = max_following_color > 0 and spike_color_delta > 3.0 * max_following_color
    if gray_ratio_too_high and color_ratio_too_high:
        return False

    # Use the dominant spike channel so pure-color snaps aren't suppressed
    effective_spike = max(spike_delta, spike_color_delta)
    cumulative_following_color = sum(following_color_deltas)
    effective_following = max(cumulative_following, cumulative_following_color)
    return effective_following > 0.10 * effective_spike


# ---------------------------------------------------------------------------
# T06: Property-specific classification
# ---------------------------------------------------------------------------


def _classify_change(region: dict) -> tuple[str, str]:
    """Classify the type of change and generate an actionable hint.

    Returns (property_name, hint).
    """
    bbox = region["bbox"]
    mean_before = region["mean_intensity_before"]
    mean_after = region["mean_intensity_after"]
    area = region["area"]
    _, _, w, h = bbox

    intensity_diff = abs(mean_after - mean_before)
    bbox_area = w * h
    fill_ratio = area / bbox_area if bbox_area > 0 else 1.0

    # Position change: region is elongated / low fill ratio (covers old + new positions)
    if fill_ratio < 0.6:
        return (
            "position",
            f"Position jumps abruptly (region bbox {bbox}). "
            "Add a Tween with ease-out over ~300ms.",
        )

    # Opacity change: significant intensity difference, compact region
    if intensity_diff > 30:
        direction = "appears" if mean_after > mean_before else "disappears"
        return (
            "opacity",
            f"Element {direction} abruptly (intensity {mean_before:.0f} → {mean_after:.0f}). "
            "Add a Tween to fade alpha over ~300ms.",
        )

    # Size change: large area with decent fill ratio
    if area > 200 and fill_ratio >= 0.6:
        return (
            "size",
            f"Size changes abruptly (region area {area}px). "
            "Add a Tween to scale over ~300ms with ease-out.",
        )

    # Fallback
    return (
        "visual",
        f"Abrupt visual change detected (region bbox {bbox}). "
        "Add a Tween with easing over ~300ms.",
    )


def _compute_change_type(region: dict) -> ChangeType:
    """Derive a ChangeType from region properties.

    Maps the property classification to enum values:
    - opacity + intensity drop → disappear
    - opacity + intensity rise → appear
    - position → position_jump
    - size → size_change
    - visual / color diff → color_change
    """
    bbox = region["bbox"]
    mean_before = region["mean_intensity_before"]
    mean_after = region["mean_intensity_after"]
    area = region["area"]
    _, _, w, h = bbox

    intensity_diff = abs(mean_after - mean_before)
    bbox_area = w * h
    fill_ratio = area / bbox_area if bbox_area > 0 else 1.0

    if fill_ratio < 0.6:
        return ChangeType.POSITION_JUMP

    if intensity_diff > 30:
        return ChangeType.DISAPPEAR if mean_after < mean_before else ChangeType.APPEAR

    # Note: region "area" is changed-pixel count from diff analysis, not element
    # size before/after, so true size-change detection is not possible with this
    # data. Fall through to COLOR_CHANGE for all remaining cases.
    return ChangeType.COLOR_CHANGE


def _estimate_node_identity(frame: np.ndarray, bbox: tuple) -> str:
    """Estimate node identity from dominant color in the region.

    Extracts the region from the frame, computes mean BGR, converts to HSV
    for color naming, and returns a descriptive label like
    "bright yellow element (48x48)" or "dark element (48x48)".
    Falls back to "unknown" if region is empty or extraction fails.
    """
    x, y, w, h = bbox
    if w <= 0 or h <= 0:
        return "unknown"

    # Clamp bbox to frame bounds to avoid silent NumPy slice clipping
    frame_h_bound = frame.shape[0]
    frame_w_bound = frame.shape[1] if frame.ndim >= 2 else 0
    x2 = min(x + w, frame_w_bound)
    y2 = min(y + h, frame_h_bound)
    if x >= frame_w_bound or y >= frame_h_bound or x2 <= x or y2 <= y:
        return "unknown"
    actual_w, actual_h = x2 - x, y2 - y

    # Handle different channel counts
    if frame.ndim == 2:
        region = frame[y:y2, x:x2]
        if region.size == 0:
            return "unknown"
        mean_val = float(region.mean())
        brightness = "bright" if mean_val > 127 else "dark"
        return f"{brightness} gray element ({actual_w}x{actual_h})"

    # Composite BGRA onto black if needed
    if frame.shape[2] == 4:
        bgr = frame[y:y2, x:x2, :3].astype(np.float32)
        alpha = frame[y:y2, x:x2, 3:4].astype(np.float32) / 255.0
        region_bgr = (bgr * alpha).astype(np.uint8)
    else:
        region_bgr = frame[y:y2, x:x2, :3]

    if region_bgr.size == 0:
        return "unknown"

    mean_bgr = region_bgr.mean(axis=(0, 1))
    b, g, r = mean_bgr

    # Convert mean BGR to hex
    hex_color = f"#{int(r):02x}{int(g):02x}{int(b):02x}"

    # Convert to HSV for color naming
    pixel = np.uint8([[[int(b), int(g), int(r)]]])
    hsv = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)[0][0]
    hue, sat, val = int(hsv[0]), int(hsv[1]), int(hsv[2])

    # Determine brightness
    if val < 50:
        return f"dark element ({actual_w}x{actual_h})"
    if sat < 30:
        brightness = "bright" if val > 180 else "dim"
        return f"{brightness} gray element ({actual_w}x{actual_h})"

    # Color naming by HSV hue ranges (OpenCV hue: 0-179)
    if hue < 10 or hue >= 170:
        color = "red"
    elif hue < 25:
        color = "orange"
    elif hue < 35:
        color = "yellow"
    elif hue < 80:
        color = "green"
    elif hue < 130:
        color = "blue"
    elif hue < 170:
        color = "purple"
    else:
        color = "red"

    brightness = "bright" if val > 180 else ""
    label = f"{brightness} {color}".strip()
    return f"{label} element ({actual_w}x{actual_h})"


_CHANGE_VERBS = {
    ChangeType.APPEAR: "appears",
    ChangeType.DISAPPEAR: "vanishes",
    ChangeType.COLOR_CHANGE: "changes color",
    ChangeType.POSITION_JUMP: "jumps position",
    ChangeType.SIZE_CHANGE: "changes size",
}


def _generate_hint(
    node_identity: str,
    change_type: ChangeType,
    screen_zone: str,
    suggestions: list[dict],
) -> str:
    """Generate a rich, actionable hint using change context."""
    verb = _CHANGE_VERBS.get(change_type, "changes abruptly")
    zone_label = screen_zone.replace("-", " ") if screen_zone else "the screen"

    hint = f"A {node_identity} {verb} in 1 frame in the {zone_label}."

    if suggestions:
        top = suggestions[0]
        hint += f" Consider a {top['style']} animation ({top['description']})."

    return hint


def _compute_screen_zone(bbox: tuple, frame_width: int, frame_height: int) -> str:
    """Compute screen zone from bbox center vs frame dimensions.

    Returns one of 9 zones in a 3x3 grid:
    top-left, top-center, top-right, center-left, center, center-right,
    bottom-left, bottom-center, bottom-right.
    """
    x, y, w, h = bbox
    cx = x + w / 2
    cy = y + h / 2

    third_w = frame_width / 3
    third_h = frame_height / 3

    if cx < third_w:
        col = "left"
    elif cx < 2 * third_w:
        col = "center"
    else:
        col = "right"

    if cy < third_h:
        row = "top"
    elif cy < 2 * third_h:
        row = "center"
    else:
        row = "bottom"

    if row == "center" and col == "center":
        return "center"
    if row == "center":
        return f"center-{col}"
    if col == "center":
        return f"{row}-center"
    return f"{row}-{col}"


# ---------------------------------------------------------------------------
# T07: Orchestrator
# ---------------------------------------------------------------------------

FPS = 15


def detect_missing_animation(
    frames: list[np.ndarray],
    config: MissingAnimationConfig | None = None,
) -> list[Issue]:
    """Detect abrupt visual state changes with no preceding transition.

    Returns a list of Issue objects for each detected snap/teleport/jump.
    """
    if config is None:
        config = MissingAnimationConfig()

    if len(frames) < 2:
        return []

    magnitudes = _compute_delta_magnitudes(frames, config.median_filter_size)
    spikes = _find_delta_spikes(magnitudes, threshold=config.delta_threshold, median_filter_size=config.median_filter_size)

    # Secondary detection: find local-region spikes missed by global averaging
    extra_spikes = _find_local_region_spikes(frames, spikes)
    all_spikes = sorted(set(spikes) | set(extra_spikes))

    # Tertiary detection: find spikes embedded in smooth motion
    embedded_spikes = _find_motion_embedded_spikes(magnitudes, all_spikes)
    embedded_set = set(embedded_spikes)
    all_spikes = sorted(set(all_spikes) | embedded_set)

    issues: list[Issue] = []

    for spike_idx in all_spikes:
        frame_before = frames[spike_idx]
        frame_after = frames[spike_idx + 1]

        regions = _extract_motion_regions(frame_before, frame_after, config.min_region_area)

        # Scene transition filter: skip if too much of the frame changed
        frame_area = frame_before.shape[0] * frame_before.shape[1]
        total_changed_area = sum(r["area"] for r in regions)
        if total_changed_area > config.scene_transition_threshold * frame_area:
            continue

        frame_h, frame_w = frame_before.shape[:2]

        # Embedded spikes use a shorter temporal window (2 frames) since they
        # co-occur with ongoing motion. The full lookback would see the broader
        # animation and incorrectly suppress the snap.
        temporal_lookback = 2 if spike_idx in embedded_set else config.lookback_frames

        for region in regions:
            if _has_preceding_motion(frames, spike_idx, region["bbox"], temporal_lookback):
                continue
            if _has_following_motion(frames, spike_idx, region["bbox"], temporal_lookback):
                continue

            prop_name, _old_hint = _classify_change(region)
            change_type = _compute_change_type(region)
            bbox = region["bbox"]
            x, y, w, h = bbox
            screen_zone = _compute_screen_zone(bbox, frame_w, frame_h)
            suggestions = get_animation_suggestions(change_type, screen_zone)
            node_identity = _estimate_node_identity(frame_before, bbox)
            hint = _generate_hint(node_identity, change_type, screen_zone, suggestions)

            timestamp_ms = int((spike_idx + 1) * 1000 / FPS)

            metrics = {
                "intensity_before": region["mean_intensity_before"],
                "intensity_after": region["mean_intensity_after"],
                "region_area_px": region["area"],
                "transition_frames": 1,
                "concurrent_events": 0,  # filled in post-processing
            }

            issues.append(
                Issue(
                    node=node_identity,
                    timestamp_ms=timestamp_ms,
                    type=IssueType.MISSING_ANIMATION,
                    severity="high" if prop_name in ("position", "opacity") else "medium",
                    hint=hint,
                    change=change_type,
                    region={"x": x, "y": y, "w": w, "h": h},
                    screen_zone=screen_zone,
                    metrics=metrics,
                    animation_suggestions=suggestions,
                )
            )

    # Post-processing: compute concurrent_events (issues at same timestamp_ms)
    from collections import Counter
    ts_counts = Counter(issue.timestamp_ms for issue in issues)
    for issue in issues:
        issue.metrics["concurrent_events"] = ts_counts[issue.timestamp_ms] - 1

    return issues
