"""Orchestrator — runs all detectors and returns a unified DiagnosticResult."""

from __future__ import annotations

import numpy as np

from godot_animation_verifier.detect_missing import detect_missing_animation
from godot_animation_verifier.models import DiagnosticResult


def analyze(frames: list[np.ndarray]) -> DiagnosticResult:
    """Run all detectors on *frames* and return a single DiagnosticResult."""
    issues = detect_missing_animation(frames)

    return DiagnosticResult(
        pass_field=len(issues) == 0,
        issues=issues,
        frame_count=len(frames),
    )
